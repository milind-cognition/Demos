# HR Data Platform — legacy EMR estate (`hr-jobs`)

> Status: **in maintenance mode.** Scheduled for re-platforming onto the Databricks Lakehouse
> (see `../target/MIGRATION_STANDARDS.md`). No new features here.

This folder is a faithful copy of the `hr-jobs` repo that runs on the `emr-hr-prod` cluster
(EMR 5.36, Hive 2.3 on Tez, Pig 0.17, Oozie 5.2, Java 8). It produces the daily HR / payroll
datasets consumed by Tableau, the GL accrual feed, and the people-analytics retention model.

## Layout

| Path | What it is |
|---|---|
| `oozie/coordinator.xml` | Daily coordinator `hr_daily_coord`; waits for `_SUCCESS` on the three landing datasets |
| `oozie/workflow.xml` | `hr_daily_wf`: **stage (shell) → emp_metrics_daily (hive2) → payroll_join (pig)**, email on failure |
| `oozie/job.properties` | Cluster endpoints, app paths, default `runDate` |
| `shell/run_daily.sh` | Cron entry point. Submits Oozie, polls it, then runs CohortTagger, month-close turnover, publish |
| `shell/stage_and_publish.sh` | `stage`: SFTP drop → HDFS staging + `_stage_audit.csv`; `publish`: HDFS → `legacy/publish/<run_date>/` |
| `hive/emp_metrics_daily.sql` | SCD2 `dim_employee` + daily `fct_emp_metrics_daily` (headcount / hours / OT by dept) |
| `hive/turnover_snapshot.sql` | Monthly turnover by department (Jan–Mar 2024 restatement, UNION ALL of 3 copy-pasted blocks) |
| `pig/payroll_join.pig` | Weekly gross-pay estimate per hourly employee + cost-center GL rollup |
| `java/CohortTagger.java` | Tags active employees with fiscal hire cohort / tenure band / OT segment (CSV in → CSV out) |
| `sample_data/` | Anonymised seed extract: `employees.csv` (HR SCD feed), `departments.csv`, `timecards.csv` (KRONOS / ADP WFN) |
| `expected_outputs/<job>/` | Golden outputs per job — the validation source of truth for the migration |
| `publish/` | Where `stage_and_publish.sh publish` drops files for the downstream SFTP pusher |

## HDFS layout

```
/data/landing/hr/<dataset>/dt=YYYY-MM-DD/<dataset>.csv     raw SFTP drop (+ _SUCCESS)
/data/staging/hr/<dataset>/dt=YYYY-MM-DD/<dataset>.csv     CR-stripped, header-checked copy
/data/staging/hr/_audit/dt=YYYY-MM-DD/_stage_audit.csv     row / dup-key audit
/warehouse/hr.db/<table>/                                  Hive / Pig outputs
/apps/oozie/hr_daily/{workflow.xml,coordinator.xml,scripts/}
```

## How each job is invoked today

| Job | Engine | Trigger | Command (on `emr-hr-prod-master`) | Outputs |
|---|---|---|---|---|
| `stage_and_publish` (stage) | bash | Oozie action `stage` | `stage_and_publish.sh stage ${runDate}` | `_stage_audit.csv`, staged CSVs |
| `emp_metrics_daily` | Hive 2 / Tez | Oozie action `emp_metrics_daily` | `beeline -u $HIVE_JDBC -f emp_metrics_daily.sql --hivevar run_date=…` | `hr.dim_employee`, `hr.fct_emp_metrics_daily` |
| `payroll_join` | Pig 0.17 | Oozie action `payroll_join` | `pig -param RUN_DATE=… -f payroll_join.pig` | `payroll_by_employee`, `payroll_by_cost_center` |
| `cohort_tagger` | Java 8 | `run_daily.sh` step 3 | `java -cp hr-jobs-1.4.2.jar com.acme.hrdata.jobs.CohortTagger emp.csv tc.csv out.csv` | `employee_cohorts` |
| `turnover_snapshot` | Hive 2 / Tez | `run_daily.sh` step 4 (1st of month or `FORCE_TURNOVER=1`) | `hive -f turnover_snapshot.sql` | `hr.turnover_snapshot` |
| `run_daily` | bash + cron | `15 6 * * *` | `run_daily.sh [yyyy-mm-dd]` | `legacy/publish/<run_date>/*.csv` + `_SUCCESS` |

Manual re-run of a single day: `run_daily.sh 2024-03-15`. Re-running only Oozie:
`oozie job -config oozie/job.properties -D runDate=2024-03-15 -run`.

Dev-box smoke test of the stage step (no HDFS needed):

```bash
LOCAL_MODE=1 LOCAL_ROOT=/tmp/hr-local ./shell/stage_and_publish.sh stage 2024-03-15
cat /tmp/hr-local/staging/hr/_audit/dt=2024-03-15/_stage_audit.csv
```

CohortTagger also runs anywhere with a JDK:

```bash
javac -d /tmp/ct java/CohortTagger.java
java -cp /tmp/ct com.acme.hrdata.jobs.CohortTagger sample_data/employees.csv sample_data/timecards.csv /tmp/employee_cohorts.csv
```

## Business rules everyone copy-pastes

The **timecard clean + hours rollup** exists in three places (`hive/emp_metrics_daily.sql`,
`pig/payroll_join.pig`, `java/CohortTagger.java`) and has to be kept in sync by hand:

1. Dedupe resubmitted corrections: keep the row with the latest `submitted_ts` per `timecard_id`.
2. Keep `approved_flag = 'Y'` only.
3. Parse `work_date` (`MM/dd/yyyy`) and keep the pay week `2024-03-11 .. 2024-03-15` (**hard-coded**).
4. Normalise `pay_code` with `UPPER(TRIM(...))` (KRONOS sends `reg`, ` ot`, `Reg ` …).
5. Buckets: `REG` → reg, `OT` + `DT` → ot, `PTO` + `HOL` → pto, everything (incl. `JURY`) → total.

"Current employee version" (latest `effective_date` ≤ as-of date) is likewise re-implemented in
the Hive, Pig and Java jobs.

## Known quirks (intentional — preserved in `expected_outputs/`)

* **Magic dates.** Every job hard-codes the March-2024 close (`2024-03-15`, pay week
  `2024-03-11..15`, quarter end `2024-03-31`, months Jan–Mar) even though Oozie passes `runDate`
  (HRDE-388). Staging table `LOCATION`s are hard-coded to `dt=2024-03-15` too.
* **Two definitions of "active".** `emp_metrics_daily` / `CohortTagger`: `term_date > day`.
  `turnover_snapshot`: `term_date >= day` (people-analytics definition).
* **Rate as-of.** Hive uses the SCD2 version valid on each work day; Pig uses the version current
  at pay-period end.
* **DT paid at 1.5x** in `payroll_join` (PAY-1123). JURY hours are in `total_hours` but unpaid.
* **Orphan department `D999`.** Kept (null dept name) in `fct_emp_metrics_daily` (LEFT JOIN),
  dropped by `payroll_join` and `turnover_snapshot` (inner join).
* **Terminated employees.** Excluded from headcount and cohorts on/after the termination date,
  but still included in `payroll_join` (final check estimate).
* **Rounding.** All published decimals are `HALF_UP` to 2 dp; `payroll_by_cost_center.gross_pay`
  sums the already-rounded employee amounts.
* **Published file contract.** Downstream consumers read header-ed CSV with decimals rendered with
  exactly two decimal places (`8.00`, `0.00`) and empty string for null — `expected_outputs/` is in
  that format.

## Contacts

`hr-data-eng@acme-hcm.com` · PagerDuty service `HR-DATA-BATCH` · Confluence space `HRDE`
