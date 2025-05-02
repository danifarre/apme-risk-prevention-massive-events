from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, countDistinct, to_json, struct, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType


def process_batch(batch_df, batch_id):
    agg_df = batch_df.agg(countDistinct("user_id").alias("users_count"))
    agg_with_ts = agg_df.withColumn("timestamp", current_timestamp())
    result_df = agg_with_ts.select(to_json(struct("users_count", "timestamp")).alias("value"))
    result_df.write.format("kafka") \
        .option("kafka.bootstrap.servers", "broker-1:19092,broker-1:29092,broker-1:39092") \
        .option("topic", "users-count") \
        .save()


def main():
    spark = SparkSession.builder \
        .appName("CountGlobalUsers") \
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

    schema = StructType([StructField("user_id", StringType(), True)])

    parsed_df = json_df.withColumn("data", from_json(col("json_string"), schema)) \
        .select("data.user_id")

    query = parsed_df.writeStream.trigger(processingTime="3 seconds") \
        .foreachBatch(process_batch) \
        .start()

    query.awaitTermination()


if __name__ == '__main__':
    main()
