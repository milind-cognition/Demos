# Databricks notebook source
# MAGIC %md
# MAGIC # nb_turnover_snapshot
# MAGIC
# MAGIC Monthly turnover by department for every month of `run_date`'s calendar quarter (month close /
# MAGIC people-analytics board deck). **Migrated from** `legacy/hive/turnover_snapshot.sql` (not in Oozie;
# MAGIC `legacy/shell/run_daily.sh` step 4 runs it on the 1st of the month or with `FORCE_TURNOVER=1`).
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Inputs | `employees`, `departments` (landing CSV) |
# MAGIC | Outputs | `turnover_snapshot` (one row per `snapshot_month` x `dept_id`; table sink replaces this quarter) |
# MAGIC | Workflow | `target/workflows/turnover_snapshot.json` |
# MAGIC | Owner | hr-data-eng / people-analytics |
# MAGIC
# MAGIC **Legacy behaviour preserved on purpose** (see `legacy/README.md` → *Known quirks*):
# MAGIC * months = the three months of `run_date`'s quarter (was three copy-pasted Jan/Feb/Mar 2024 blocks
# MAGIC   UNIONed together, HRDE-402) -- now a loop over `dates.quarter_months(run_date)`
# MAGIC * one HR record per employee: the version current at **quarter end** (was `2024-03-31`), used for
# MAGIC   every month of the quarter, including the dept assignment
# MAGIC * "active" = people-analytics definition `term_date >= day` (termed ON the day still counts),
# MAGIC   unlike `emp_metrics_daily` / `CohortTagger` (`term_date > day`) -- do not "fix" without sign-off
# MAGIC * inner join to `departments`: unknown departments (`D999`) are dropped; `is_active` is ignored
# MAGIC * `turnover_rate_pct = ROUND(terminations * 100 / ((headcount_start + headcount_end) / 2), 2)`
# MAGIC   HALF_UP, `0.00` when both headcounts are 0 (so a dept going 1 -> 0 reports `200.00`)
# MAGIC * **changed vs legacy:** legacy `INSERT OVERWRITE` replaced the whole table; the table sink now
# MAGIC   uses `replaceWhere snapshot_month IN (<quarter months>)` so a new quarter never wipes a closed one
# MAGIC * a dept/month row is published only if headcount_start, headcount_end, hires or terminations > 0
# MAGIC
# MAGIC Local run / validation (from `datacloud-migration-demo/`):
# MAGIC ```
# MAGIC python target/notebooks/nb_turnover_snapshot.py --run_date=2024-03-15 --validate
# MAGIC python scripts/validate.py turnover_snapshot
# MAGIC ```

# COMMAND ----------

import functools
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

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from target.lib import dates, hr_transforms as hr, io, params, paths, validation
from target.lib.spark import get_spark

JOB = "turnover_snapshot"

# COMMAND ----------

# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("run_date", "2024-03-15", "Run date (yyyy-MM-dd); snapshot covers its calendar quarter")
dbutils.widgets.text("snapshot_as_of", "", "HR record as-of override (blank = quarter end of run_date)")
dbutils.widgets.text("input_root", "", "Input root (blank = legacy/sample_data)")
dbutils.widgets.text("output_root", "", "CSV output root (blank = target/output)")
dbutils.widgets.dropdown("output_sink", "csv", ["csv", "table"], "Sink: csv (local/validation) | table (UC)")
dbutils.widgets.text("table_prefix", "hr_dev.hr", "catalog.schema for output_sink=table")
dbutils.widgets.dropdown("validate", "false", ["true", "false"], "Diff output vs legacy/expected_outputs")

run_date = params.get_date(dbutils, "run_date")
months = dates.quarter_months(run_date)
snapshot_as_of = params.get_optional_date(dbutils, "snapshot_as_of") or dates.quarter_end(run_date)
input_root = paths.resolve(params.get_str(dbutils, "input_root"), paths.SAMPLE_DATA_DIR)
output_root = paths.resolve(params.get_str(dbutils, "output_root"), paths.LOCAL_OUTPUT_DIR)
output_sink = params.get_str(dbutils, "output_sink")
table_prefix = params.get_str(dbutils, "table_prefix")
validate = params.get_bool(dbutils, "validate")
if validate and output_sink != "csv":
    raise ValueError("--validate requires output_sink=csv")

out_dir = paths.job_output_dir(output_root, JOB)
print("[%s] run_date=%s months=%s as_of=%s input_root=%s sink=%s"
      % (JOB, run_date, ",".join(m[0] for m in months), snapshot_as_of, input_root, output_sink))

# COMMAND ----------

# MAGIC %md ## Extract

# COMMAND ----------

spark = get_spark("hr_daily." + JOB)

employees = io.read_dataset(spark, paths.input_path(input_root, "employees"), "employees")
departments = io.read_dataset(spark, paths.input_path(input_root, "departments"), "departments")

# COMMAND ----------

# MAGIC %md ## Transform

# COMMAND ----------

emp_latest = hr.current_employee_version(employees, snapshot_as_of).select(
    "emp_id", "dept_id", "hire_date", "term_date", "term_reason"
)
dept_dim = departments.select("dept_id", "dept_name", "region")
emp_dept = emp_latest.join(dept_dim, "dept_id", "inner")


def _count(cond):
    return F.sum(F.when(cond, F.lit(1)).otherwise(F.lit(0)))


def month_snapshot(month, start, end):
    termed = hr.dated_between("term_date", start, end)
    return emp_dept.groupBy("dept_id", "dept_name", "region").agg(
        _count(hr.active_on_day(start, term_day_counts=True)).alias("headcount_start"),
        _count(hr.active_on_day(end, term_day_counts=True)).alias("headcount_end"),
        _count(hr.dated_between("hire_date", start, end)).alias("hires"),
        _count(termed).alias("terminations"),
        _count(termed & (F.col("term_reason") == "VOLUNTARY")).alias("voluntary_terminations"),
    ).withColumn("snapshot_month", F.lit(month))


monthly = functools.reduce(DataFrame.unionByName, [month_snapshot(m, s, e) for m, s, e in months])

headcount_sum = F.col("headcount_start") + F.col("headcount_end")
avg_headcount = headcount_sum.cast("decimal(18,0)") / F.lit(2)
turnover = monthly.filter(
    (F.col("headcount_start") > 0) | (F.col("headcount_end") > 0) | (F.col("hires") > 0)
    | (F.col("terminations") > 0)
).withColumn(
    "turnover_rate_pct",
    F.when(
        headcount_sum > 0,
        hr.round_money(F.col("terminations").cast("decimal(18,0)") * F.lit(100) / avg_headcount),
    ).otherwise(F.lit(0).cast(hr.MONEY)),
)

TURNOVER_COLS = [
    "snapshot_month", "dept_id", "dept_name", "region", "headcount_start", "headcount_end", "hires",
    "terminations", "voluntary_terminations", "turnover_rate_pct",
]
turnover_snapshot = turnover.select(*TURNOVER_COLS)

# COMMAND ----------

# MAGIC %md ## Load

# COMMAND ----------

published_months = io.in_predicate("snapshot_month", [m for m, _, _ in months])
written = [
    io.write_output_replace_where(turnover_snapshot, output_sink, out_dir, table_prefix, "turnover_snapshot",
                                  TURNOVER_COLS, published_months),
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
