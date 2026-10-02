"""The ONE implementation of the HR business rules that legacy copy-pasted into Hive, Pig and Java.

Every migrated notebook must call these instead of re-deriving them (MIGRATION_STANDARDS.md §5).
All hours / money are DecimalType -- never double -- so results are bit-for-bit reproducible.
"""
from pyspark.sql import Window
from pyspark.sql import functions as F

from target.lib.io import EMPLOYEE_SOURCE_ORDER

HOURS = "decimal(9,2)"
MONEY = "decimal(18,2)"
RATE = "decimal(9,2)"

REG_CODES = ("REG",)
OT_CODES = ("OT", "DT")
PTO_CODES = ("PTO", "HOL")

OT_PREMIUM = "1.5"  # DT is paid at 1.5x pending PAY-1123 -- see legacy/README.md


def clean_timecards(timecards, start_date, end_date):
    """Latest correction per timecard_id -> approved only -> work_date in [start, end] -> codes.

    Returns: timecard_id, emp_id, work_date (date), pay_code (normalised), hours (decimal).
    """
    latest = Window.partitionBy("timecard_id").orderBy(F.col("submitted_ts").desc())
    return (
        timecards.withColumn("_rn", F.row_number().over(latest))
        .filter(F.col("_rn") == 1)
        .filter(F.col("approved_flag") == "Y")
        .withColumn("work_date", F.to_date("work_date", "MM/dd/yyyy"))
        .filter(F.col("work_date").between(F.lit(start_date), F.lit(end_date)))
        .select(
            "timecard_id",
            "emp_id",
            "work_date",
            F.upper(F.trim("pay_code")).alias("pay_code"),
            F.col("hours").cast(HOURS).alias("hours"),
        )
    )


def _bucket(codes):
    return F.sum(F.when(F.col("pay_code").isin(*codes), F.col("hours")).otherwise(F.lit(0).cast(HOURS)))


def bucket_hours(clean_tc, group_cols):
    """REG -> reg_hours, OT+DT -> ot_hours, PTO+HOL -> pto_hours, all codes -> total_hours."""
    return clean_tc.groupBy(*group_cols).agg(
        _bucket(REG_CODES).cast(HOURS).alias("reg_hours"),
        _bucket(OT_CODES).cast(HOURS).alias("ot_hours"),
        _bucket(PTO_CODES).cast(HOURS).alias("pto_hours"),
        F.sum("hours").cast(HOURS).alias("total_hours"),
    )


def current_employee_version(employees, as_of_date):
    """Latest eligible SCD record; reader provenance breaks date ties by first CSV occurrence."""
    ordering = [F.col("effective_date").desc()]
    if EMPLOYEE_SOURCE_ORDER in employees.columns:
        columns = [c for c in employees.columns if c != EMPLOYEE_SOURCE_ORDER]
        employees = employees.groupBy(*columns).agg(
            F.min(EMPLOYEE_SOURCE_ORDER).alias(EMPLOYEE_SOURCE_ORDER),
        )
        ordering.append(F.col(EMPLOYEE_SOURCE_ORDER).asc())
    else:
        employees = employees.dropDuplicates()
    w = Window.partitionBy("emp_id").orderBy(*ordering)
    return (
        employees
        .filter(F.col("effective_date") <= F.lit(as_of_date.isoformat()))
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn", EMPLOYEE_SOURCE_ORDER)
    )


def full_name(first_col="first_name", last_col="last_name"):
    return F.concat_ws(" ", F.trim(F.col(first_col)), F.trim(F.col(last_col)))


def round_money(col):
    """HALF_UP to 2 dp (Spark ``round`` is HALF_UP; ``bround`` would be HALF_EVEN -- don't)."""
    return F.round(col, 2).cast(MONEY)
