# HR Data Platform — Migration Standards (EMR → Databricks Lakehouse)

**Status:** v1.2 · **Owner:** hr-data-eng platform team · **Applies to:** every job leaving `legacy/`

This is the contract every migration PR is reviewed against. A migration is **done** only when
`python scripts/validate.py <job>` exits 0 (conformance + golden diff) and the PR follows §10.
The reference implementation of every rule below is the **`payroll_join` exemplar**:

| Exemplar file | Migrated from |
|---|---|
| `target/notebooks/nb_payroll_join.py` | `legacy/pig/payroll_join.pig` |
| `target/workflows/payroll_join.json` | Oozie action `payroll_join` in `legacy/oozie/workflow.xml` |
| `target/lib/*` | logic copy-pasted across Hive / Pig / Java |

When in doubt, copy the exemplar's structure. All paths in this document are relative to
`datacloud-migration-demo/`.

---

## 1. Job inventory and names

The job name is the folder name under `legacy/expected_outputs/` — it is the unit of migration,
validation and scheduling.

| Job | Legacy artifact | Golden outputs (`legacy/expected_outputs/<job>/`) | Status |
|---|---|---|---|
| `payroll_join` | `pig/payroll_join.pig` | `payroll_by_employee.csv`, `payroll_by_cost_center.csv` | **migrated (exemplar)** |
| `emp_metrics_daily` | `hive/emp_metrics_daily.sql` | `dim_employee.csv`, `fct_emp_metrics_daily.csv` | to do |
| `turnover_snapshot` | `hive/turnover_snapshot.sql` | `turnover_snapshot.csv` | to do |
| `cohort_tagger` | `java/CohortTagger.java` | `employee_cohorts.csv` | to do |
| `stage_and_publish` | `shell/stage_and_publish.sh` (`stage`) | `stage_audit.csv` | to do |
| `hr_daily` (orchestration) | `oozie/workflow.xml` + `coordinator.xml` + `shell/run_daily.sh` | — (structure checks only, §8) | to do |

`python scripts/validate.py --list` shows live status.

## 2. File naming and layout

| What | Path | Rule |
|---|---|---|
| Notebook | `target/notebooks/nb_<job>.py` | exactly one per job, Databricks **source** format (§3) |
| Workflow | `target/workflows/<job>.json` | exactly one per job, Jobs API 2.1 JSON (§8) |
| Shared code | `target/lib/<module>.py` | anything used by ≥ 2 jobs, or any business rule (§5) |
| Tests | `target/tests/test_<topic>.py` | pytest; new lib functions need a unit test |
| Local outputs | `target/output/<job>/<dataset>.csv` | git-ignored, never committed |

Output dataset names are **identical** to the golden file names (`payroll_by_employee`, not
`payroll_emp_v2`). Column names and order are identical to the golden header.

## 3. Notebook format and the local-PySpark rule

* First line is `# Databricks notebook source`; cells are separated by `# COMMAND ----------`;
  markdown cells use `# MAGIC %md`. The file must import cleanly in a Databricks Repo **and** run as
  `python target/notebooks/nb_<job>.py` on a laptop.
* First markdown cell: purpose, `Migrated from` legacy path, inputs, outputs, workflow file, and
  the list of legacy quirks deliberately preserved (copy the exemplar's table).
* **Vanilla PySpark 3.5 DataFrame API only.** Forbidden: `dbutils` as a hard dependency,
  `pyspark.dbutils`, `databricks.*`, `dbruntime`, `delta` / `DeltaTable`, `dlt`, `%sql` / `%run`
  magics, `display()`, Photon- or DBR-only functions. (`scripts/validate.py` enforces the imports.)
* Get Spark from `target.lib.spark.get_spark(...)` — never build a `SparkSession` yourself.
* Prefer DataFrame API over `spark.sql` strings. If SQL is clearer, it still obeys §6.
* All hours and money are `DecimalType` (`hr_transforms.HOURS` / `RATE` / `MONEY`); never `double`.
  Rounding is HALF_UP via `hr_transforms.round_money` (Spark `round`, not `bround`).
* No Python UDFs unless a built-in genuinely cannot express the rule (justify in the PR).
* No `collect()`/`toPandas()` on business data; no `.cache()` without a measured reason.

## 4. Parameters, dates and the `dbutils` shim

Legacy jobs hard-code `2024-03-15`, `2024-03-11..15`, `2024-03-31`, `'2024-01'` … Migrated code
contains **no date literals** outside widget defaults. Every date is derived from `run_date` via
`target/lib/dates.py` (`pay_week`, `quarter_end`, `quarter_months`, `month_bounds`), with optional
blank-by-default override widgets for backfills.

Bind `dbutils` exactly like this (real `dbutils` wins on a cluster, the shim locally):

```python
try:
    dbutils  # noqa: F821 -- injected by Databricks
except NameError:
    from target.lib.dbutils_shim import dbutils
```

The shim (`target/lib/dbutils_shim.py`) implements `dbutils.widgets.text / dropdown / get / getAll /
remove / removeAll` and `dbutils.notebook.exit`. Nothing else is supported — do not call other
`dbutils` APIs. Local value resolution, first hit wins:

1. CLI: `--run_date=2024-03-15`, `--run_date 2024-03-15`, bare `--validate` (= `true`)
2. env: `HRDP_<WIDGET_NAME_UPPER>`, e.g. `HRDP_RUN_DATE=2024-03-15`
3. widget default

Read widgets through `target/lib/params.py` (`get_date`, `get_optional_date`, `get_bool`, `get_str`).

**Required widgets in every notebook** (validator-enforced):

| Widget | Default | Meaning |
|---|---|---|
| `run_date` | `2024-03-15` | business date; the only date the scheduler passes |
| `input_root` | `""` → `legacy/sample_data` | folder holding `employees.csv`, `departments.csv`, `timecards.csv` |
| `output_root` | `""` → `target/output` | CSV sink root; job writes to `<output_root>/<job>/` |
| `output_sink` | `csv` (dropdown `csv`/`table`) | `table` writes managed (Delta) tables `<table_prefix>.<dataset>` on a cluster |
| `table_prefix` | `hr_dev.hr` | Unity Catalog `catalog.schema` for `output_sink=table` |
| `validate` | `false` (dropdown) | run §7 diff after writing |

Defaults must reproduce the golden run (`run_date=2024-03-15`) with no arguments.

## 5. Shared utilities (`target/lib/`) — kill the copy-paste

The legacy estate re-implements the same rules in Hive, Pig and Java. In the target they exist
**once**, in `target/lib/hr_transforms.py`, and notebooks call them:

| Rule | Function |
|---|---|
| latest correction per `timecard_id` → `approved_flag='Y'` → `MM/dd/yyyy` parse → window filter → `UPPER(TRIM(pay_code))` | `clean_timecards(df, start, end)` |
| REG / OT+DT / PTO+HOL / total buckets | `bucket_hours(clean_df, group_cols)` |
| employee SCD version current as of a date (exact dupes collapsed) | `current_employee_version(df, as_of)` |
| `TRIM(first) + ' ' + TRIM(last)` | `full_name()` |
| HALF_UP 2 dp money | `round_money(col)` |

Other modules: `io.py` (schema'd CSV reads, single-file sorted CSV writes, table sink),
`paths.py` (repo path conventions), `dates.py`, `params.py`, `spark.py`, `validation.py`.

Rules: if you need a rule that already exists, **call it**; if you need a new rule that a second
job will need (e.g. SCD2 versioning, the active-on-day predicate), add it to `target/lib/` with a
unit test in the same PR. Changing an existing lib function must keep **every** migrated job green
(`python scripts/validate.py --all`).

## 6. SQL / DataFrame hygiene

* **No `SELECT *`** — not in SQL strings, not as `.select("*")`. Project explicit columns at every
  read and before every write (`io.write_output(..., columns)`).
* Join with explicit keys and an explicit `how=`. Document every intentional row-dropping inner
  join (e.g. `D999`) in the notebook header.
* No hard-coded HDFS / S3 / DBFS paths. Inputs come from `input_root`; prod paths live only in the
  workflow JSON (`/Volumes/hr_prod/...`).
* Deterministic: no `rand()`, `uuid()`, `current_date()`/`current_timestamp()` in business logic.
  Surrogate keys must be derived deterministically (e.g. `row_number()` over a total ordering).

## 7. `--validate` mode

Every notebook ends with a validate cell that, when `validate=true`:

1. calls `validation.compare_job(<output_root>/<job>, paths.expected_dir(JOB))`,
2. prints `validation.format_report(...)`,
3. raises (non-zero exit / failed task) on any mismatch.

Comparison rule (owned by `target/lib/validation.py`, documented in `VALIDATION.md`): header exact
(names + order); rows compared as exact-string multisets after sorting; missing, unexpected and
extra datasets all fail. **There are no tolerances.** Match the published file contract: decimals
rendered with exactly 2 dp (`8.00`), integers without decimals, empty string for null, ISO dates.

Legacy quirks (two "active" definitions, 1.5x DT, rate as-of, D999 handling…) are **preserved**,
not fixed — the golden files encode them. Fixing a business rule is a separate, signed-off change
that regenerates the goldens (`scripts/seed/generate_expected_outputs.py`) in its own PR.

## 8. Workflows (`target/workflows/<job>.json`)

One Databricks Jobs API 2.1 job spec per migrated job, modelled on `payroll_join.json`:

* `name`: `hr_daily.<job>`; `description` names the legacy artifact; `tags` include `domain`,
  `team`, `legacy_artifact`, `migration_wave`, `cost_center`.
* `parameters`: `run_date` defaulting to `{{job.start_time.iso_date}}` plus anything prod-specific.
* `git_source` pointing at this repo / `main`; notebook tasks use `"source": "GIT"` and
  `notebook_path` **without** `.py` (`datacloud-migration-demo/target/notebooks/nb_<job>`).
* `job_clusters` with a `job_cluster_key`, `new_cluster.spark_version` (`15.4.x-scala2.12`),
  `node_type_id`, `autoscale` or `num_workers`, `data_security_mode`, `spark_conf`
  (UTC, ANSI on), `aws_attributes`, `custom_tags` (`CostCenter`, `Workload`, `DataClassification`).
  Tasks reference clusters by key — no `existing_cluster_id`, no all-purpose clusters.
* Each task: `task_key`, `job_cluster_key`, `notebook_task.base_parameters` (must pass `run_date`
  as `{{job.parameters.run_date}}`; `output_sink=table`; `validate=false`), `timeout_seconds`,
  `max_retries`, `min_retry_interval_millis`, task-level `email_notifications.on_failure`.
* Job-level `email_notifications`, `max_concurrent_runs: 1`, `queue.enabled`, `run_as`
  service principal, `schedule` with `pause_status: PAUSED` (cut-over flips it).

**Orchestration (`hr_daily.json`).** The Oozie coordinator + workflow + `run_daily.sh` become one
multi-task job `target/workflows/hr_daily.json`: one task per migrated notebook,
`depends_on` mirroring the Oozie `ok to=` chain (`stage_and_publish → emp_metrics_daily →
payroll_join`) plus the `run_daily.sh` tail (`cohort_tagger`, `turnover_snapshot`); the Oozie
`<email>` kill path becomes `email_notifications.on_failure`; the coordinator's daily
06:15 frequency / `timezone` (`job.properties`) becomes `schedule`; the coordinator's `_SUCCESS` dataset dependency becomes a
`file_arrival` trigger on the landing volume **or** is documented as replaced by the upstream
feed's SLA. Month-close-only `turnover_snapshot` uses a `condition_task` on `run_date`. It must
reference the per-job notebooks (same `notebook_path`s and `base_parameters` as the per-job specs).

## 9. Tests

* `python -m pytest -q target/tests` must pass (it runs conformance + golden diff for every
  migrated job automatically via `test_migrations.py`).
* New `target/lib` functions get unit tests with tiny inline DataFrames (see `test_hr_transforms.py`).

## 10. Definition of done / PR checklist

- [ ] `target/notebooks/nb_<job>.py` + `target/workflows/<job>.json` (+ lib changes and tests)
- [ ] `python scripts/validate.py <job>` → `SUMMARY <job> PASS` (paste output in the PR)
- [ ] `python scripts/validate.py --all` and `python -m pytest -q target/tests` green
- [ ] No `SELECT *`, no date literals outside widget defaults, no Databricks-only imports
- [ ] Every legacy quirk preserved and listed in the notebook header; no golden file edited
- [ ] Legacy artifact left untouched (decommission happens after cut-over, not in the migration PR)
- [ ] PR title `migrate(<job>): <legacy artifact> -> nb_<job>`; body maps legacy steps → notebook cells
