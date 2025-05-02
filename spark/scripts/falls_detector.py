from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, max, to_json, struct, current_timestamp, when
from pyspark.sql.types import StructType, StructField, FloatType, TimestampType, StringType
from pyspark.sql.window import Window


def process_batch(batch_df, batch_id):
    window_spec = Window.partitionBy("user_id")
    batch_df = batch_df.withColumn("max_height", max("height").over(window_spec)) \
        .withColumn("max_speed", max("speed").over(window_spec))

    batch_df = batch_df.filter((col("max_speed") > 4.0) & (col("max_height") < 2.0)) \
        .dropDuplicates(["user_id"])

    agg_with_ts = batch_df.withColumn("timestamp", current_timestamp())
    result_df = agg_with_ts.select(to_json(struct("user_id", "lat", "lon", "timestamp")).alias("value"))
    result_df.write.format("kafka") \
        .option("kafka.bootstrap.servers", "broker-1:19092,broker-1:29092,broker-1:39092") \
        .option("topic", "falls") \
        .save()


def main():
    spark = SparkSession.builder \
        .appName("FallsDetection") \
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
        StructField("height", FloatType(), True),
        StructField("speed", FloatType(), True),
        StructField("timestamp", TimestampType(), True),
    ])

    parsed_df = json_df.withColumn("data", from_json(col("json_string"), schema)) \
        .select("data.user_id", "data.lat", "data.lon", "data.height", "data.speed", "data.timestamp")

    query = parsed_df.writeStream.trigger(processingTime="3 seconds") \
        .foreachBatch(process_batch) \
        .start()

    query.awaitTermination()


if __name__ == '__main__':
    main()
