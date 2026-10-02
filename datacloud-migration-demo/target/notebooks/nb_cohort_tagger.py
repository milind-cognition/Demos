# Databricks notebook source
# MAGIC %md
# MAGIC # nb_cohort_tagger
# MAGIC
# MAGIC Tag active employees with fiscal hire cohort, completed tenure and weekly OT segment for
# MAGIC the Workforce Cohorts workbook and retention feature store.
# MAGIC **Migrated from** `legacy/java/CohortTagger.java` (`run_daily.sh` step 3).
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Inputs | `employees`, `timecards` (landing CSV) |
# MAGIC | Outputs | `employee_cohorts` |
# MAGIC | Workflow | `target/workflows/cohort_tagger.json` |
# MAGIC | Owner | hr-data-eng |
# MAGIC
# MAGIC **Legacy behaviour preserved on purpose** (see `legacy/README.md` → *Known quirks*):
# MAGIC * employee version current at `run_date`; same-date ties retain the first CSV record
# MAGIC * active means blank termination or `term_date > run_date`
# MAGIC * no hire-date cutoff; unknown departments (`D999`) kept without a department join
# MAGIC * latest timecard correction wins before approval/date filtering; codes are trimmed and uppercased
# MAGIC * OT = OT + DT over the Mon–Fri pay week; employees without matching cards have `0.00` OT
# MAGIC * tenure counts completed month/day anniversaries; leap-day hires wait until March in non-leap years
# MAGIC * tenure bands use thresholds 1, 3 and 5 years; fiscal year starts July 1 and uses two-digit years
# MAGIC * `SALARY` is always `EXEMPT` (OT hours still retained); otherwise `HIGH_OT` starts at 8 hours
# MAGIC * OT decimals publish with exactly two decimal places; cohort tag joins cohort, band and segment
# MAGIC
# MAGIC Local run / validation (from `datacloud-migration-demo/`):
# MAGIC ```
# MAGIC python target/notebooks/nb_cohort_tagger.py --validate
# MAGIC python scripts/validate.py cohort_tagger
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

from target.lib import cohort_transforms as cohort, dates, hr_transforms as hr, io, params, paths, validation
from target.lib.spark import get_spark

JOB = "cohort_tagger"

# COMMAND ----------

# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("run_date", "2024-03-15", "Run date (yyyy-MM-dd)")
dbutils.widgets.text("period_start", "", "OT window start override (blank = Monday of run_date week)")
dbutils.widgets.text("period_end", "", "OT window end override (blank = Friday of run_date week)")
dbutils.widgets.text("input_root", "", "Input root (blank = legacy/sample_data)")
dbutils.widgets.text("output_root", "", "Output root (blank = target/output)")
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

employees = io.read_dataset(spark, paths.input_path(input_root, "employees"), "employees", preserve_source_order=True)
timecards = io.read_dataset(spark, paths.input_path(input_root, "timecards"), "timecards")

# COMMAND ----------

# MAGIC %md ## Transform

# COMMAND ----------

emp_ot = hr.bucket_hours(hr.clean_timecards(timecards, period_start, period_end), ["emp_id"]).select(
    "emp_id", "ot_hours",
)
active_employees = (
    hr.current_employee_version(employees, run_date)
    .filter(cohort.active_on_day(run_date))
    .select("emp_id", "dept_id", "pay_type", F.to_date("hire_date").alias("hire_date"))
)

employee_cohorts = (
    active_employees.join(emp_ot, on="emp_id", how="left")
    .withColumn("ot_hours", F.coalesce(F.col("ot_hours"), F.lit(0).cast(hr.HOURS)).cast(hr.HOURS))
    .withColumn("tenure_years", cohort.full_years_between(F.col("hire_date"), run_date))
    .withColumn("tenure_band", cohort.tenure_band(F.col("tenure_years")))
    .withColumn("hire_cohort", cohort.fiscal_cohort(F.col("hire_date")))
    .withColumn("ot_segment", cohort.ot_segment(F.col("pay_type"), F.col("ot_hours")))
    .withColumn("cohort_tag", F.concat_ws("_", "hire_cohort", "tenure_band", "ot_segment"))
)

COHORT_COLS = [
    "emp_id", "dept_id", "pay_type", "hire_date", "tenure_years", "tenure_band", "hire_cohort",
    "ot_hours", "ot_segment", "cohort_tag",
]

# COMMAND ----------

# MAGIC %md ## Load

# COMMAND ----------

written = [io.write_output(employee_cohorts, output_sink, out_dir, table_prefix, "employee_cohorts", COHORT_COLS)]
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
