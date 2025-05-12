from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, from_json, when, to_json, struct, current_timestamp, count, lit, max, min, row_number
from pyspark.sql.types import StructType, StructField, FloatType, TimestampType, StringType


def process_batch(batch_df, batch_id):
    window_spec = Window.partitionBy("user_id").orderBy(col("timestamp").desc())
    batch_df = batch_df.withColumn("time_id", row_number().over(window_spec))

    x_start, x_end = 150, 650
    y_start, y_end = 500, 600

    cols = 4
    rows = 5

    cell_width = (x_end - x_start) // cols  # 125
    cell_height = (y_end - y_start) // rows  # 20

    zone_expr = None
    counter = 1

    for row in range(rows):
        for col_idx in range(cols):
            x1 = x_start + col_idx * cell_width
            x2 = x1 + cell_width
            y1 = y_start + row * cell_height
            y2 = y1 + cell_height

            condition = (col("lat") > y1) & (col("lat") <= y2) & (col("lon") > x1) & (col("lon") <= x2)

            if zone_expr is None:
                zone_expr = when(condition, lit(f"Zona {counter}"))
            else:
                zone_expr = zone_expr.when(condition, lit(f"Zona {counter}"))

            counter += 1

    zone_expr = zone_expr.otherwise(lit(None))

    batch_df = batch_df.withColumn("zone", zone_expr) \
        .filter(col("zone").isNotNull())

    count_zone = batch_df.groupBy("zone", "time_id") \
        .agg(count("zone").alias("count_zone"))

    max_zone = count_zone.groupBy("zone") \
        .agg(max("count_zone").alias("max_zone"))

    min_zone = count_zone.groupBy("zone") \
        .agg(min("count_zone").alias("min_zone"))

    batch_df = max_zone.join(min_zone, ["zone"]) \
        .withColumn("diff_zone", col("max_zone") - col("min_zone")) \
        .withColumn("massive_movement", when((col("max_zone") >= 20) & ((col("diff_zone") / col("max_zone")) > 0.80), lit(1)).otherwise(lit(0)))

    batch_df = batch_df.withColumn("timestamp", current_timestamp())
    result_df = batch_df.select(to_json(struct("zone", "massive_movement", "timestamp")).alias("value"))
    result_df.write.format("kafka") \
        .option("kafka.bootstrap.servers", "broker-1:19092,broker-1:29092,broker-1:39092") \
        .option("topic", "dangerous-movements") \
        .save()


def main():
    spark = SparkSession.builder \
        .appName("CountUsersPerZone") \
        .master("spark://spark-master:7077") \
        .config("spark.cores.max", "4") \
        .config("spark.executor.cores", "2") \
        .config("spark.dynamicAllocation.enable", "false") \
        .getOrCreate()

    kafka_df = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", "broker-1:19092,broker-1:29092,broker-1:39092") \
        .option("subscribe", "users-info") \
        .load()

    json_df = kafka_df.selectExpr("CAST(value AS STRING) AS json_string")

    schema = StructType([
        StructField("user_id", StringType(), True),
        StructField("lat", FloatType(), True),
        StructField("lon", FloatType(), True),
        StructField("timestamp", TimestampType(), True),
    ])

    parsed_df = json_df.withColumn("data", from_json(col("json_string"), schema)) \
        .select("data.user_id", "data.lat", "data.lon", "data.timestamp")

    query = parsed_df.writeStream.trigger(processingTime="5 seconds") \
        .foreachBatch(process_batch) \
        .start()

    query.awaitTermination()


if __name__ == '__main__':
    main()
