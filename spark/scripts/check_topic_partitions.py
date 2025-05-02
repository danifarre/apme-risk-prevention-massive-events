from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit

topic = "users-info"
spark = SparkSession.builder \
    .appName("CountUsersPerPartition") \
    .master("spark://spark-master:7077") \
    .config("spark.cores.max", "4") \
    .config("spark.executor.cores", "2") \
    .config("spark.dynamicAllocation.enable", "false") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "broker-1:19092,broker-1:29092,broker-1:39092") \
    .option("subscribe", topic) \
    .load()


def show_partition_distribution(batch_df, batch_id):
    print(f"\n--- Batch ID: {batch_id} ---")
    batch_df.groupBy("partition").count().orderBy("partition").show()


# 4. Ejecutar stream con foreachBatch
query = df.writeStream \
    .foreachBatch(show_partition_distribution) \
    .outputMode("append") \
    .start()

query.awaitTermination()
