"""Readers / writers for the HR datasets.

Inputs are always read with an explicit all-string schema (the legacy feeds are untyped CSV and
the legacy jobs cast explicitly); casting happens in hr_transforms. Outputs follow the published
file contract from legacy/README.md: header row, decimals rendered with 2 dp, empty string for null.
"""
import glob
import os
import shutil

from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

INPUT_COLUMNS = {
    "employees": [
        "emp_id", "first_name", "last_name", "dept_id", "job_title", "employment_type", "pay_type",
        "hourly_rate", "hire_date", "term_date", "term_reason", "location", "manager_id",
        "effective_date", "record_source",
    ],
    "departments": ["dept_id", "dept_name", "cost_center", "division", "region", "is_active"],
    "timecards": [
        "timecard_id", "emp_id", "work_date", "pay_code", "hours", "approved_flag", "submitted_ts",
        "source_system",
    ],
}

EMPLOYEE_SOURCE_ORDER = "_source_order"


def input_schema(dataset):
    return StructType([StructField(c, StringType(), True) for c in INPUT_COLUMNS[dataset]])


def read_dataset(spark, path, dataset):
    """Read single-line landing CSVs with explicit schemas and empty strings for blanks.

    Employees are read per file, carrying (file path, line position) provenance for SCD ties.
    Each employee file must fit in executor memory; files are ordered lexically, then by line.
    """
    if dataset == "employees":
        lines = (
            spark.read.format("binaryFile").load(path)
            .select("path", F.posexplode(F.split(F.decode("content", "UTF-8"), r"\r\n|\n|\r"))
                    .alias("_line_number", "_csv"))
            .filter((F.col("_line_number") > 0) & F.col("_csv").rlike(r"\S"))
        )
        records = lines.select(
            F.from_csv("_csv", input_schema(dataset).simpleString(), {"mode": "FAILFAST"}).alias("_record"),
            F.struct(F.col("path").alias("file"), F.col("_line_number").alias("row"))
            .alias(EMPLOYEE_SOURCE_ORDER),
        )
        return records.select(
            [F.coalesce(F.col("_record." + c), F.lit("")).alias(c) for c in INPUT_COLUMNS[dataset]]
            + [F.col(EMPLOYEE_SOURCE_ORDER)]
        )
    df = (
        spark.read.option("header", "true")
        .option("mode", "FAILFAST")
        .schema(input_schema(dataset))
        .csv(path)
    )
    return df.select([F.coalesce(F.col(c), F.lit("")).alias(c) for c in INPUT_COLUMNS[dataset]])


def to_published(df, columns):
    """Project exactly ``columns`` (in order) and render every value as its published string."""
    return df.select([F.coalesce(F.col(c).cast("string"), F.lit("")).alias(c) for c in columns])


def write_csv(df, out_dir, dataset, columns):
    """Write ``df`` as a single, sorted ``<out_dir>/<dataset>.csv`` (local / validation sink)."""
    pub = to_published(df, columns).orderBy(*columns)
    tmp = os.path.join(out_dir, "_tmp_" + dataset)
    (
        pub.coalesce(1).write.mode("overwrite")
        .option("header", "true")
        .option("emptyValue", "")
        .option("nullValue", "")
        .csv(tmp)
    )
    part = glob.glob(os.path.join(tmp, "part-*.csv"))
    if len(part) != 1:
        raise RuntimeError("expected exactly one part file in %s, found %d" % (tmp, len(part)))
    final = os.path.join(out_dir, dataset + ".csv")
    os.makedirs(out_dir, exist_ok=True)
    shutil.move(part[0], final)
    shutil.rmtree(tmp)
    return final


def write_table(df, table_fqn, columns):
    """Cluster sink: managed table (Delta by default on Databricks)."""
    df.select(*columns).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table_fqn)
    return table_fqn


def write_output(df, sink, out_dir, table_prefix, dataset, columns):
    if sink == "csv":
        return write_csv(df, out_dir, dataset, columns)
    if sink == "table":
        return write_table(df, "%s.%s" % (table_prefix, dataset), columns)
    raise ValueError("unknown output sink %r (expected csv|table)" % sink)
