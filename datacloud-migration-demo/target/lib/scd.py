"""Employee SCD2 dimension + the "employed on day" predicate (MIGRATION_STANDARDS.md section 5).

Legacy re-implemented both in Hive (emp_metrics_daily, turnover_snapshot) and Java (CohortTagger).
"""
import datetime as dt

from pyspark.sql import Window
from pyspark.sql import functions as F

OPEN_END_DATE = dt.date(9999, 12, 31)
ISO_DATE_FORMAT = "yyyy-MM-dd"


def parse_iso_date(col_name):
    """``yyyy-MM-dd`` string -> date; malformed or blank -> null (never fails under ANSI mode)."""
    return F.try_to_timestamp(F.col(col_name), F.lit(ISO_DATE_FORMAT)).cast("date")


def scd2_versions(employees, as_of_date):
    """Type-2 versions of every employee record effective on/before ``as_of_date``.

    Mirrors Hive ``SELECT DISTINCT`` + ``ROW_NUMBER() OVER (ORDER BY emp_id, effective_date)`` +
    ``LEAD(effective_date)``: exact duplicate rows collapse, ``employee_sk`` is a deterministic
    1-based key, ``eff_end_date`` is the day before the next version (``9999-12-31`` when open) and
    ``is_current`` is ``Y`` for the open version. Both windows share one total ordering so distinct
    same-day records are versioned deterministically. Adds employee_sk, eff_start_date, eff_end_date
    (dates) and is_current to the input columns.
    """
    cols = employees.columns
    tiebreak = [c for c in cols if c not in ("emp_id", "effective_date")]
    by_emp = Window.partitionBy("emp_id").orderBy("effective_date", *tiebreak)
    total = Window.orderBy("emp_id", "effective_date", *tiebreak)
    next_start = F.lead(parse_iso_date("effective_date")).over(by_emp)
    return (
        employees.dropDuplicates()
        .filter(F.col("effective_date") <= F.lit(as_of_date.isoformat()))
        .withColumn("employee_sk", F.row_number().over(total))
        .withColumn("eff_start_date", parse_iso_date("effective_date"))
        .withColumn("eff_end_date", F.coalesce(F.date_sub(next_start, 1), F.lit(OPEN_END_DATE)))
        .withColumn("is_current", F.when(next_start.isNull(), F.lit("Y")).otherwise(F.lit("N")))
    )


def valid_on(day_col, start_col="eff_start_date", end_col="eff_end_date"):
    """SCD2 version window contains ``day_col`` (both ends inclusive)."""
    day = F.col(day_col) if isinstance(day_col, str) else day_col
    return (F.col(start_col) <= day) & (F.col(end_col) >= day)


def employed_on(day_col, terminated_on_day_is_active=False, hire_col="hire_date", term_col="term_date"):
    """Hired on/before the day and not yet terminated (blank ``term_date`` = still employed).

    Two legacy definitions of "active" exist (legacy/README.md, Known quirks):
    * ``emp_metrics_daily`` / ``CohortTagger``: ``term_date > day`` (default)
    * ``turnover_snapshot``: ``term_date >= day`` -> ``terminated_on_day_is_active=True``

    Like the legacy SQL, ``hire_date`` / ``term_date`` are compared as ISO strings (no parsing), so a
    malformed HR date never aborts the batch.
    """
    day = (F.col(day_col) if isinstance(day_col, str) else day_col).cast("string")
    term = F.col(term_col)
    still_employed = (term >= day) if terminated_on_day_is_active else (term > day)
    return (F.col(hire_col) <= day) & ((term == "") | still_employed)
