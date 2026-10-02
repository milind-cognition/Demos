# Databricks notebook source
# MAGIC %md
# MAGIC # nb_payroll_join
# MAGIC
# MAGIC Weekly gross-pay estimate per hourly associate plus the cost-center rollup that feeds the GL
# MAGIC accrual. **Migrated from** `legacy/pig/payroll_join.pig` (Oozie `hr_daily_wf` → action `payroll_join`).
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Inputs | `employees`, `departments`, `timecards` (landing CSV) |
# MAGIC | Outputs | `payroll_by_employee`, `payroll_by_cost_center` |
# MAGIC | Workflow | `target/workflows/payroll_join.json` |
# MAGIC | Owner | payroll-analytics / hr-data-eng |
# MAGIC
# MAGIC **Legacy behaviour preserved on purpose** (see `legacy/README.md` → *Known quirks*):
# MAGIC * pay week = Mon–Fri of `run_date` (was the hard-coded `2024-03-11..2024-03-15`)
# MAGIC * rate = HR record current at pay-period end, not per work day
# MAGIC * `(REG + PTO/HOL) * rate + (OT + DT) * rate * 1.5`; JURY counts toward hours but is unpaid
# MAGIC * terminated employees kept (final-check estimate); unknown departments (`D999`) dropped by inner join
# MAGIC * cost-center `gross_pay` sums the already-rounded employee amounts
# MAGIC
# MAGIC Local run / validation (from `datacloud-migration-demo/`):
# MAGIC ```
# MAGIC python target/notebooks/nb_payroll_join.py --run_date=2024-03-15 --validate
# MAGIC python scripts/validate.py payroll_join
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

from target.lib import dates, hr_transforms as hr, io, params, paths, validation
from target.lib.spark import get_spark

JOB = "payroll_join"

# COMMAND ----------

# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("run_date", "2024-03-15", "Run date (yyyy-MM-dd)")
dbutils.widgets.text("period_start", "", "Pay period start override (blank = Monday of run_date week)")
dbutils.widgets.text("period_end", "", "Pay period end override (blank = Friday of run_date week)")
dbutils.widgets.text("input_root", "", "Input root (blank = legacy/sample_data)")
dbutils.widgets.text("output_root", "", "CSV output root (blank = target/output)")
dbutils.widgets.dropdown("output_sink", "csv", ["csv", "table"], "Sink: csv (local/validation) | table (UC)")
dbutils.widgets.text("table_prefix", "hr_dev.hr", "catalog.schema for output_sink=table")
dbutils.widgets.dropdown("validate", "false", ["true", "false"], "Diff output vs legacy/expected_outputs")

run_date = params.get_date(dbutils, "run_date")
default_start, default_end = dates.pay_week(run_date)
period_start = params.get_optional_date(dbutils, "period_start") or default_start
period_end = params.get_optional_date(dbutils, "period_end") or default_end
input_root = paths.resolve(params.get_str(dbutils, "input_root"), paths.SAMPLE_DATA_DIR)
output_root = paths.resolve(params.get_str(dbutils, "output_root"), paths.LOCAL_OUTPUT_DIR)
output_sink = params.get_str(dbutils, "output_sink")
table_prefix = params.get_str(dbutils, "table_prefix")
validate = params.get_bool(dbutils, "validate")
if validate and output_sink != "csv":
    raise ValueError("--validate requires output_sink=csv")

out_dir = paths.job_output_dir(output_root, JOB)
print("[%s] run_date=%s period=%s..%s input_root=%s sink=%s"
      % (JOB, run_date, period_start, period_end, input_root, output_sink))

# COMMAND ----------

# MAGIC %md ## Extract

# COMMAND ----------

spark = get_spark("hr_daily." + JOB)

employees = io.read_dataset(spark, paths.input_path(input_root, "employees"), "employees")
departments = io.read_dataset(spark, paths.input_path(input_root, "departments"), "departments")
timecards = io.read_dataset(spark, paths.input_path(input_root, "timecards"), "timecards")

# COMMAND ----------

# MAGIC %md ## Transform

# COMMAND ----------

emp_hours = hr.bucket_hours(hr.clean_timecards(timecards, period_start, period_end), ["emp_id"])

hourly_emps = (
    hr.current_employee_version(employees, period_end)
    .filter(F.col("pay_type") == "HOURLY")
    .select(
        "emp_id",
        hr.full_name().alias("full_name"),
        "dept_id",
        F.col("hourly_rate").cast(hr.RATE).alias("hourly_rate"),
    )
)

dept_dim = departments.select("dept_id", "dept_name", "cost_center", "region")

premium = F.lit(hr.OT_PREMIUM).cast("decimal(3,1)")
payroll = (
    emp_hours.join(hourly_emps, "emp_id", "inner")
    .join(dept_dim, "dept_id", "inner")
    .withColumn("pay_period_start", F.lit(dates.iso(period_start)))
    .withColumn("pay_period_end", F.lit(dates.iso(period_end)))
    .withColumn(
        "gross_pay",
        hr.round_money(
            (F.col("reg_hours") + F.col("pto_hours")) * F.col("hourly_rate")
            + F.col("ot_hours") * F.col("hourly_rate") * premium
        ),
    )
    .withColumn("ot_flag", F.when(F.col("ot_hours") > 0, F.lit("Y")).otherwise(F.lit("N")))
)

BY_EMPLOYEE_COLS = [
    "pay_period_start", "pay_period_end", "emp_id", "full_name", "dept_id", "dept_name", "cost_center",
    "hourly_rate", "reg_hours", "ot_hours", "pto_hours", "total_hours", "gross_pay", "ot_flag",
]
by_employee = payroll.select(*BY_EMPLOYEE_COLS)

BY_COST_CENTER_COLS = [
    "pay_period_start", "pay_period_end", "cost_center", "region", "employee_count", "total_hours",
    "ot_hours", "gross_pay",
]
by_cost_center = payroll.groupBy("pay_period_start", "pay_period_end", "cost_center", "region").agg(
    F.count("emp_id").alias("employee_count"),
    F.sum("total_hours").cast(hr.HOURS).alias("total_hours"),
    F.sum("ot_hours").cast(hr.HOURS).alias("ot_hours"),
    hr.round_money(F.sum("gross_pay")).alias("gross_pay"),
)

# COMMAND ----------

# MAGIC %md ## Load

# COMMAND ----------

written = [
    io.write_output(by_employee, output_sink, out_dir, table_prefix, "payroll_by_employee", BY_EMPLOYEE_COLS),
    io.write_output(by_cost_center, output_sink, out_dir, table_prefix, "payroll_by_cost_center",
                    BY_COST_CENTER_COLS),
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
