# datacloud-migration-demo — HR Data Platform: EMR → Databricks Lakehouse

Acme HCM's HR batch platform runs six jobs (Hive, Pig, Oozie, shell, Java) on Amazon EMR. This
folder holds both sides of the re-platforming onto Databricks (PySpark notebooks + Databricks
Workflows), runnable end-to-end on a laptop — no AWS, no Databricks workspace, no credentials.

```
legacy/                     the estate being retired (see legacy/README.md)
  oozie/ hive/ pig/ shell/ java/
  sample_data/              checked-in, deterministic seed extracts (employees, departments, timecards)
  expected_outputs/<job>/   golden CSVs per job = validation source of truth
target/
  MIGRATION_STANDARDS.md    the contract every migration follows
  notebooks/nb_<job>.py     migrated notebooks (Databricks source format, local-PySpark compatible)
  workflows/<job>.json      one Databricks Jobs API 2.1 spec per job
  lib/                      shared business rules + dbutils shim + IO/validation helpers
  tests/                    pytest suite (also runs every migrated job against its goldens)
scripts/validate.py         conformance + golden diff for a job  (VALIDATION.md)
scripts/seed/               regenerate sample_data / expected_outputs (deterministic)
DEMO_RUNBOOK.md             presenter script
PLAYBOOK.md                 Devin Playbook text for the migration procedure (!migrate_job)
PLAYBOOK_FANOUT.md          Devin Playbook that launches the Act 4 wave (!databricks_migration)
```

## Quick start

```bash
cd datacloud-migration-demo
python3 -m pip install -r requirements.txt     # pyspark 3.5.5, pytest 8.3.4 (needs Java 11/17)
python3 scripts/validate.py --list
python3 scripts/validate.py payroll_join       # the migrated exemplar -> PASS
python3 -m pytest -q target/tests
```

Migration status: **`payroll_join` migrated** (exemplar); `emp_metrics_daily`, `turnover_snapshot`,
`cohort_tagger`, `stage_and_publish` and the `hr_daily` Oozie orchestration are still legacy.
