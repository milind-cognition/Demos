# Databricks notebook source
# MAGIC %md
# MAGIC # nb_emp_metrics_daily
# MAGIC
# MAGIC Type-2 employee dimension plus the daily headcount / hours / overtime fact by department.
# MAGIC **Migrated from** `legacy/hive/emp_metrics_daily.sql` (Oozie `hr_daily_wf` → action `emp_metrics_daily`).
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Inputs | `employees`, `departments`, `timecards` (landing CSV) |
# MAGIC | Outputs | `dim_employee` (full SCD2 rebuild), `fct_emp_metrics_daily` (one row per work_date x dept_id) |
# MAGIC | Workflow | `target/workflows/emp_metrics_daily.json` |
# MAGIC | Owner | hr-data-eng |
# MAGIC
# MAGIC **Legacy behaviour preserved on purpose** (see `legacy/README.md` → *Known quirks*):
# MAGIC * pay week = Mon–Fri of `run_date` (was the hard-coded `2024-03-11..2024-03-15`); dimension as-of =
# MAGIC   `run_date` (was the hard-coded `effective_date <= '2024-03-15'`)
# MAGIC * `dim_employee` is a full rebuild; exact duplicate HR rows collapse (Hive `SELECT DISTINCT`);
# MAGIC   `employee_sk` = `ROW_NUMBER() OVER (ORDER BY emp_id, effective_date)`
# MAGIC * "active" on a day = SCD2 version valid on the day, `hire_date <= day` and `term_date > day`
# MAGIC   (the emp_metrics / CohortTagger definition, **not** turnover's `>=`)
# MAGIC * hours use the SCD2 version valid on each work day (not pay-period end like `payroll_join`)
# MAGIC * day spine = only days that have at least one clean (approved, latest-correction) timecard
# MAGIC * departments LEFT joined: orphan `D999` employees still count, with blank `dept_name` / `cost_center`
# MAGIC * `ot_pct` = `ROUND(ot * 100 / total, 2)` HALF_UP, `0.00` when the department logged no hours
# MAGIC
# MAGIC Local run / validation (from `datacloud-migration-demo/`):
# MAGIC ```
# MAGIC python target/notebooks/nb_emp_metrics_daily.py --run_date=2024-03-15 --validate
# MAGIC python scripts/validate.py emp_metrics_daily
# MAGIC ```

# COMMAND ----------

import json
import os
import sys

_NB_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_DEMO_ROOT = os.path.abspath(os.path.join(_NB_DIR, "..", ".."))
if _DEMO_ROOT not in sys.path:
    sys.path.insert(0, _DEMO_ROOT)

try:
    dbutils  # noqa: F821 -- injected by Databricks
except NameError:
    from target.lib.dbutils_shim import dbutils

from pyspark.sql import functions as F

from target.lib import dates, hr_transforms as hr, io, params, paths, scd, validation
from target.lib.spark import get_spark

JOB = "emp_metrics_daily"
PCT = "decimal(5,2)"

# COMMAND ----------

# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("run_date", "2024-03-15", "Run date (yyyy-MM-dd)")
dbutils.widgets.text("period_start", "", "Fact window start override (blank = Monday of run_date week)")
dbutils.widgets.text("period_end", "", "Fact window end override (blank = Friday of run_date week)")
dbutils.widgets.text("as_of_date", "", "dim_employee as-of override (blank = run_date)")
dbutils.widgets.text("input_root", "", "Input root (blank = legacy/sample_data)")
dbutils.widgets.text("output_root", "", "CSV output root (blank = target/output)")
dbutils.widgets.dropdown("output_sink", "csv", ["csv", "table"], "Sink: csv (local/validation) | table (UC)")
dbutils.widgets.text("table_prefix", "hr_dev.hr", "catalog.schema for output_sink=table")
dbutils.widgets.dropdown("validate", "false", ["true", "false"], "Diff output vs legacy/expected_outputs")

run_date = params.get_date(dbutils, "run_date")
default_start, default_end = dates.pay_week(run_date)
period_start = params.get_optional_date(dbutils, "period_start") or default_start
period_end = params.get_optional_date(dbutils, "period_end") or default_end
as_of_date = params.get_optional_date(dbutils, "as_of_date") or run_date
input_root = paths.resolve(params.get_str(dbutils, "input_root"), paths.SAMPLE_DATA_DIR)
output_root = paths.resolve(params.get_str(dbutils, "output_root"), paths.LOCAL_OUTPUT_DIR)
output_sink = params.get_str(dbutils, "output_sink")
table_prefix = params.get_str(dbutils, "table_prefix")
validate = params.get_bool(dbutils, "validate")
if validate and output_sink != "csv":
    raise ValueError("--validate requires output_sink=csv")

out_dir = paths.job_output_dir(output_root, JOB)
print("[%s] run_date=%s period=%s..%s as_of=%s input_root=%s sink=%s"
      % (JOB, run_date, period_start, period_end, as_of_date, input_root, output_sink))

# COMMAND ----------

# MAGIC %md ## Extract

# COMMAND ----------

spark = get_spark("hr_daily." + JOB)

employees = io.read_dataset(spark, paths.input_path(input_root, "employees"), "employees")
departments = io.read_dataset(spark, paths.input_path(input_root, "departments"), "departments")
timecards = io.read_dataset(spark, paths.input_path(input_root, "timecards"), "timecards")

# COMMAND ----------

# MAGIC %md ## Transform — 1. `dim_employee` (SCD2)

# COMMAND ----------

DIM_EMPLOYEE_COLS = [
    "employee_sk", "emp_id", "full_name", "dept_id", "job_title", "employment_type", "pay_type",
    "hourly_rate", "hire_date", "term_date", "eff_start_date", "eff_end_date", "is_current",
]
dim_employee = scd.scd2_versions(employees, as_of_date).select(
    "employee_sk",
    "emp_id",
    hr.full_name().alias("full_name"),
    "dept_id",
    "job_title",
    "employment_type",
    "pay_type",
    F.col("hourly_rate").cast(hr.RATE).alias("hourly_rate"),
    "hire_date",
    "term_date",
    "eff_start_date",
    "eff_end_date",
    "is_current",
)

# COMMAND ----------

# MAGIC %md ## Transform — 2. clean timecards, hours per employee per day

# COMMAND ----------

clean_tc = hr.clean_timecards(timecards, period_start, period_end)
emp_day_hours = hr.bucket_hours(clean_tc, ["emp_id", "work_date"])

# COMMAND ----------

# MAGIC %md ## Transform — 3. active employee x day, 4. daily department fact

# COMMAND ----------

day_spine = clean_tc.select("work_date").distinct()
emp_day_active = (
    day_spine.crossJoin(dim_employee.select("emp_id", "dept_id", "hire_date", "term_date",
                                            "eff_start_date", "eff_end_date"))
    .filter(scd.valid_on("work_date") & scd.employed_on("work_date"))
    .select("work_date", "emp_id", "dept_id")
)

dept_dim = departments.select("dept_id", "dept_name", "cost_center")
zero = F.lit(0).cast(hr.HOURS)


def _hours_sum(col):
    return F.sum(F.coalesce(F.col(col), zero)).cast(hr.HOURS)


FCT_COLS = [
    "work_date", "dept_id", "dept_name", "cost_center", "headcount", "reg_hours", "ot_hours", "pto_hours",
    "total_hours", "ot_pct", "employees_with_ot",
]
fct_emp_metrics_daily = (
    emp_day_active.join(emp_day_hours, ["emp_id", "work_date"], "left")
    .join(dept_dim, "dept_id", "left")  # left: D999 "unassigned" employees still count
    .groupBy("work_date", "dept_id", "dept_name", "cost_center")
    .agg(
        F.countDistinct("emp_id").alias("headcount"),
        _hours_sum("reg_hours").alias("reg_hours"),
        _hours_sum("ot_hours").alias("ot_hours"),
        _hours_sum("pto_hours").alias("pto_hours"),
        _hours_sum("total_hours").alias("total_hours"),
        F.countDistinct(F.when(F.col("ot_hours") > 0, F.col("emp_id"))).alias("employees_with_ot"),
    )
    .withColumn(
        "ot_pct",
        F.when(F.col("total_hours") > 0, F.round(F.col("ot_hours") * 100 / F.col("total_hours"), 2))
        .otherwise(F.lit(0))
        .cast(PCT),
    )
    .select(*FCT_COLS)
)

# COMMAND ----------

# MAGIC %md ## Load

# COMMAND ----------

written = [
    io.write_output(dim_employee, output_sink, out_dir, table_prefix, "dim_employee", DIM_EMPLOYEE_COLS),
    io.write_output(fct_emp_metrics_daily, output_sink, out_dir, table_prefix, "fct_emp_metrics_daily", FCT_COLS),
]
for w in written:
    print("[%s] wrote %s" % (JOB, w))

# COMMAND ----------

# MAGIC %md ## Validate (`--validate`)

# COMMAND ----------

summary = {"job": JOB, "run_date": dates.iso(run_date), "outputs": written, "validated": validate}
if validate:
    results = validation.compare_job(out_dir, paths.expected_dir(JOB))
    print(validation.format_report(JOB, results))
    summary["validation"] = "PASS" if validation.all_match(results) else "FAIL"
    if summary["validation"] != "PASS":
        raise AssertionError("[%s] output does not match legacy/expected_outputs/%s" % (JOB, JOB))

dbutils.notebook.exit(json.dumps(summary))
