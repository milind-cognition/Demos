# Databricks notebook source
# MAGIC %md
# MAGIC # nb_stage_and_publish
# MAGIC
# MAGIC Header + duplicate-business-key audit of the daily HR inbound feed, run before every downstream
# MAGIC job. **Migrated from** the `stage` mode of `legacy/shell/stage_and_publish.sh`
# MAGIC (Oozie `hr_daily_wf` → action `stage`).
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Inputs | `departments`, `employees`, `timecards` (landing CSV, read as raw lines) |
# MAGIC | Outputs | `stage_audit` (was `/data/staging/hr/_audit/dt=<run_date>/_stage_audit.csv`) |
# MAGIC | Workflow | `target/workflows/stage_and_publish.json` |
# MAGIC | Owner | hr-data-eng |
# MAGIC
# MAGIC **Legacy behaviour preserved on purpose** (see `legacy/README.md` and `target/lib/staging.py`):
# MAGIC * datasets checked in order `departments → employees → timecards`; a missing file or a header
# MAGIC   that is not byte-identical to the contract (after CR stripping, no trimming) **fails the task**
# MAGIC   and no audit is published (shell: `FAILED_HEADER` + `exit 1` before the audit `put`)
# MAGIC * duplicate business keys (`dept_id` / `emp_id,effective_date` / `timecard_id`) are **not** a
# MAGIC   failure: status `WARN_DUP_KEYS`, task succeeds ("downstream jobs dedupe")
# MAGIC * `row_count` = non-blank data lines; keys are taken with raw `cut -d,` semantics (no CSV quote
# MAGIC   parsing, no trimming), so a quoted comma would shift the key exactly as it does in the shell
# MAGIC * `load_date` = `run_date`
# MAGIC
# MAGIC **Not migrated here:** the HDFS landing / staging copies (downstream notebooks read `input_root`
# MAGIC directly) and the `publish` mode (`getmerge` to the SFTP publish dir) — orchestration tail.
# MAGIC
# MAGIC Local run / validation (from `datacloud-migration-demo/`):
# MAGIC ```
# MAGIC python target/notebooks/nb_stage_and_publish.py --run_date=2024-03-15 --validate
# MAGIC python scripts/validate.py stage_and_publish
# MAGIC ```

# COMMAND ----------

import json
import os
import sys
from functools import reduce

_NB_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_DEMO_ROOT = os.path.abspath(os.path.join(_NB_DIR, "..", ".."))
if _DEMO_ROOT not in sys.path:
    sys.path.insert(0, _DEMO_ROOT)

try:
    dbutils  # noqa: F821 -- injected by Databricks
except NameError:
    from target.lib.dbutils_shim import dbutils

from target.lib import dates, io, params, paths, staging, validation
from target.lib.spark import get_spark

JOB = "stage_and_publish"

# COMMAND ----------

# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("run_date", "2024-03-15", "Run date (yyyy-MM-dd) = audit load_date")
dbutils.widgets.text("input_root", "", "Inbound feed root (blank = legacy/sample_data)")
dbutils.widgets.text("output_root", "", "CSV output root (blank = target/output)")
dbutils.widgets.dropdown("output_sink", "csv", ["csv", "table"], "Sink: csv (local/validation) | table (UC)")
dbutils.widgets.text("table_prefix", "hr_dev.hr", "catalog.schema for output_sink=table")
dbutils.widgets.dropdown("validate", "false", ["true", "false"], "Diff output vs legacy/expected_outputs")

run_date = params.get_date(dbutils, "run_date")
input_root = paths.resolve(params.get_str(dbutils, "input_root"), paths.SAMPLE_DATA_DIR)
output_root = paths.resolve(params.get_str(dbutils, "output_root"), paths.LOCAL_OUTPUT_DIR)
output_sink = params.get_str(dbutils, "output_sink")
table_prefix = params.get_str(dbutils, "table_prefix")
validate = params.get_bool(dbutils, "validate")
if validate and output_sink != "csv":
    raise ValueError("--validate requires output_sink=csv")

out_dir = paths.job_output_dir(output_root, JOB)
print("[%s] run_date=%s input_root=%s sink=%s" % (JOB, run_date, input_root, output_sink))

# COMMAND ----------

# MAGIC %md ## Extract + header check (fails the task on mismatch)

# COMMAND ----------

spark = get_spark("hr_daily." + JOB)

feeds = {}
for ds in staging.FEED_DATASETS:
    lines = staging.read_feed_lines(spark, paths.input_path(input_root, ds))
    staging.check_header(ds, staging.header_line(lines))
    feeds[ds] = lines

# COMMAND ----------

# MAGIC %md ## Transform: row / distinct-key / duplicate-key audit

# COMMAND ----------

load_date = dates.iso(run_date)
stage_audit = reduce(
    lambda a, b: a.unionByName(b),
    [staging.audit_feed(feeds[ds], ds, load_date) for ds in staging.FEED_DATASETS],
)

# COMMAND ----------

# MAGIC %md ## Load

# COMMAND ----------

written = [io.write_output(stage_audit, output_sink, out_dir, table_prefix, "stage_audit", staging.AUDIT_COLUMNS)]
for w in written:
    print("[%s] wrote %s" % (JOB, w))

audit_rows = [r.asDict() for r in stage_audit.orderBy("dataset").collect()]
for r in audit_rows:
    if r["status"] == staging.STATUS_WARN_DUP_KEYS:
        print("[%s] WARN %s has %d duplicate business keys (downstream jobs dedupe)"
              % (JOB, r["dataset"], r["duplicate_key_count"]))
    print("[%s] %s rows=%d distinct_keys=%d" % (JOB, r["dataset"], r["row_count"], r["distinct_key_count"]))

# COMMAND ----------

# MAGIC %md ## Validate (`--validate`)

# COMMAND ----------

summary = {"job": JOB, "run_date": load_date, "outputs": written, "validated": validate,
           "status": {r["dataset"]: r["status"] for r in audit_rows}}
if validate:
    results = validation.compare_job(out_dir, paths.expected_dir(JOB))
    print(validation.format_report(JOB, results))
    summary["validation"] = "PASS" if validation.all_match(results) else "FAIL"
    if summary["validation"] != "PASS":
        raise AssertionError("[%s] output does not match legacy/expected_outputs/%s" % (JOB, JOB))

dbutils.notebook.exit(json.dumps(summary))
