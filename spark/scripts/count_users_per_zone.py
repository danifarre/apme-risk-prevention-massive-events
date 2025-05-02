from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, when, to_json, struct, current_timestamp, count, lit, row_number
from pyspark.sql.types import StructType, StructField, FloatType, TimestampType, StringType
from pyspark.sql.window import Window


def process_batch(batch_df, batch_id):
    window_spec = Window.partitionBy("user_id").orderBy(col("timestamp").desc())
    batch_df = batch_df.withColumn("row_number", row_number().over(window_spec)) \
        .filter(col("row_number") == 1) \
        .drop("row_number")

    agg_df = batch_df.withColumn("zone",
                                 when(
                                     (col("lat") > 0) & (col("lat") <= 150) & (col("lon") > 80) & (col("lon") <= 340),
                                     lit("Baños (Izq)")
                                 ).when(
                                     (col("lat") > 650) & (col("lat") <= 800) & (col("lon") > 80) & (col("lon") <= 340),
                                     lit("Baños (Der)")
                                 ).when(
                                     (col("lat") > 0) & (col("lat") <= 150) & (col("lon") > 340) & (col("lon") <= 600),
                                     lit("Bar (Izq)")
                                 ).when(
                                     (col("lat") > 650) & (col("lat") <= 800) & (col("lon") > 340) & (
                                                 col("lon") <= 600),
                                     lit("Bar (Der)")
                                 ).otherwise(lit("Pista"))
                                 )
    agg_df = agg_df.groupBy("zone").agg(count("*").alias("count_zone"))
    agg_with_ts = agg_df.withColumn("timestamp", current_timestamp())
    result_df = agg_with_ts.select(to_json(struct("zone", "count_zone", "timestamp")).alias("value"))
    result_df.write.format("kafka") \
        .option("kafka.bootstrap.servers", "broker-1:19092,broker-1:29092,broker-1:39092") \
        .option("topic", "zone-count") \
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

    query = parsed_df.writeStream.trigger(processingTime="3 seconds") \
        .foreachBatch(process_batch) \
        .start()

    query.awaitTermination()


if __name__ == '__main__':
    main()
