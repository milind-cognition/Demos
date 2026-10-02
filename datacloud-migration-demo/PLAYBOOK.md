<!-- Paste everything below the line into Devin → Settings → Playbooks → New playbook.
     Suggested title: "EMR → Databricks job migration"   Suggested macro: !migrate_job -->

---

# EMR → Databricks job migration

## Overview
Migrate one legacy HR batch job (Hive SQL, Pig, Java, shell, or the Oozie orchestration) from
`datacloud-migration-demo/legacy/` to the Databricks Lakehouse target in
`datacloud-migration-demo/target/`: a Databricks-source PySpark notebook that runs on local vanilla
PySpark, a Databricks Jobs API 2.1 workflow JSON, any shared logic in `target/lib/`, and a PR whose
output is proven identical to the legacy golden files by `scripts/validate.py`.
`target/MIGRATION_STANDARDS.md` is the contract; the `payroll_join` migration is the exemplar.

## What's Needed From User
- The legacy artifact to migrate, e.g. `hive/emp_metrics_daily.sql` (or "the Oozie orchestration").
- Optionally, extra constraints (e.g. "keep the turnover active definition").

## Procedure
1. `cd datacloud-migration-demo`, `python3 -m pip install -r requirements.txt` if PySpark is missing (needs Java 11/17), and confirm the baseline: `python3 scripts/validate.py --all` passes and `python3 scripts/validate.py --list` shows the job is not yet migrated.
2. Read `target/MIGRATION_STANDARDS.md` end to end, then the exemplar: `target/notebooks/nb_payroll_join.py`, `target/workflows/payroll_join.json`, `target/lib/*.py`.
3. Map the legacy job: read the artifact plus `legacy/README.md` ("How each job is invoked", "Business rules", "Known quirks"). Derive the job name from `legacy/expected_outputs/<job>/` and read every golden CSV header there — those names, column orders and formats are the output contract.
4. Post a short plan before coding: legacy step → notebook cell table, which `target/lib/hr_transforms` functions are reused, which new shared helpers are added to `target/lib/` (with tests), which widgets replace which magic dates, and which quirks are preserved.
5. Implement `target/notebooks/nb_<job>.py` by copying the exemplar's cell structure: header markdown (incl. "Migrated from" and preserved quirks), path bootstrap + `dbutils` shim binding, widgets (`run_date`, `input_root`, `output_root`, `output_sink`, `table_prefix`, `validate` + blank-default overrides), Extract via `io.read_dataset`, Transform with DataFrame API and `target/lib`, Load via `io.write_output(..., columns)`, Validate cell via `validation.compare_job`, `dbutils.notebook.exit(json)`.
6. Put any rule another job also needs into `target/lib/` (new function or module) and add a unit test in `target/tests/` using tiny inline DataFrames.
7. Write `target/workflows/<job>.json` modelled on `payroll_join.json` (name `hr_daily.<job>`, tags with `legacy_artifact`, `git_source`, `job_clusters` with DBR 15.4, notebook_task with `"source": "GIT"` and path without `.py`, `base_parameters` passing `{{job.parameters.run_date}}`, retries, timeouts, notifications, paused schedule). For the Oozie orchestration instead build `hr_daily.json` per standards §8 with `depends_on` mirroring the Oozie `ok to=` chain plus the `run_daily.sh` tail, and add a DAG-structure pytest.
8. Iterate `python3 scripts/validate.py <job>` until it prints `SUMMARY <job> PASS`; use the missing/unexpected sample rows in the report to find the drifting rule (rounding, join type, as-of date, active definition, dedupe order) and fix the notebook — never the golden file.
9. Run the full gate: `python3 scripts/validate.py --all`, `python3 -m pytest -q target/tests`, `flake8` (config in `setup.cfg`).
10. Open a PR titled `migrate(<job>): <legacy artifact> -> nb_<job>` whose body contains the legacy→notebook mapping table, the preserved quirks, new lib functions, and the pasted output of `scripts/validate.py <job>` and `--all`; wait for the `datacloud-migration-demo` CI check to go green and fix any failure.

## Specifications
- Files: `target/notebooks/nb_<job>.py`, `target/workflows/<job>.json`, any `target/lib/` + `target/tests/` changes. Nothing under `legacy/` changes.
- Notebook starts with `# Databricks notebook source`, uses `# COMMAND ----------` cells, runs with `python3 target/notebooks/nb_<job>.py` and with `--validate`, and imports only vanilla PySpark + stdlib + `target.lib`.
- No `SELECT *`/`.select("*")`; no date literals outside widget defaults; dates derived from `run_date` via `target/lib/dates.py`; hours/money are DecimalType with HALF_UP rounding.
- Business rules shared with other jobs live once in `target/lib/`.
- Validation: `python3 scripts/validate.py <job>` exits 0 with every dataset `[PASS]` (exact header, exact sorted rows), `python3 scripts/validate.py --all` exits 0, `python3 -m pytest -q target/tests` passes, CI green.

## Advice and Pointers
- Defaults must reproduce the golden run (`run_date=2024-03-15`) with zero arguments; the validator passes only `--run_date`, `--input_root`, `--output_root`, `--output_sink=csv`.
- The goldens encode legacy quirks on purpose (two "active" definitions, DT at 1.5x, rate as-of differences, D999 kept vs dropped, rounding of already-rounded sums). Reproduce them and list them in the notebook header; propose fixes separately.
- Surrogate keys must be deterministic: `row_number()` over a total ordering that matches the golden file.
- Empty string, not null, is the published representation of a missing value; decimals render with exactly 2 dp — cast to `decimal(…,2)` before writing.
- `hr_transforms.current_employee_version` drops exact duplicate rows; SCD2 versioning should do the same (`dropDuplicates()`), mirroring Hive's `SELECT DISTINCT`.
- Spark startup issues locally: `export SPARK_LOCAL_IP=127.0.0.1`.
- If several migrations run in parallel, add new shared helpers as new functions (or new modules) rather than rewriting existing ones, to keep PRs merge-friendly.

## Forbidden Actions
- Do not edit anything in `legacy/expected_outputs/` or `legacy/sample_data/`, and do not weaken `target/lib/validation.py` or `scripts/validate.py` to make a job pass.
- Do not import `pyspark.dbutils`, `databricks.*`, `dbruntime`, `delta`, or `dlt`, or use `%run`, `%sql`, or `display()`.
- Do not connect to AWS, Databricks, or any external service; everything runs locally.
- Do not use Python UDFs, `collect()`/`toPandas()` on business data, or non-deterministic functions (`rand`, `uuid`, `current_date`).
- Do not modify or delete the legacy artifact or the `payroll_join` exemplar as part of a migration PR.
