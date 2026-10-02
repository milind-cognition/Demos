"""SparkSession factory: returns the cluster session on Databricks, a tuned local one elsewhere."""
import os

from pyspark.sql import SparkSession


def get_spark(app_name):
    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", "python3")
    spark = (
        SparkSession.builder.appName(app_name)
        .master(os.environ.get("HRDP_SPARK_MASTER", "local[2]"))
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "true")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark
