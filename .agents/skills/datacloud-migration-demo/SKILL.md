---
name: datacloud-migration-demo
description: Conventions and commands for migrating legacy EMR jobs (Hive/Pig/Oozie/shell/Java) to PySpark notebooks + Databricks workflow JSON inside datacloud-migration-demo/.
---

# datacloud-migration-demo

Use whenever a task touches `datacloud-migration-demo/` (EMR → Databricks migration demo).

## Setup
```bash
cd datacloud-migration-demo
python3 -m pip install --user -r requirements.txt flake8==7.3.0   # pyspark 3.5.5, pytest 8.3.4; needs Java 11/17
export SPARK_LOCAL_IP=127.0.0.1                                    # if Spark fails to bind
```

## Rules
- `target/MIGRATION_STANDARDS.md` is the contract; `payroll_join` (`target/notebooks/nb_payroll_join.py`, `target/workflows/payroll_join.json`) is the pattern to copy.
- Notebooks: `target/notebooks/nb_<job>.py`, Databricks-source format, vanilla PySpark only (no `pyspark.dbutils`, `databricks.*`, `delta`, `dlt`, `%run`, `%sql`, `display()`), parameters via `target/lib/dbutils_shim.py` widgets, no `SELECT *`, no date literals outside widget defaults, shared logic in `target/lib/`.
- One `target/workflows/<job>.json` per job; Oozie orchestration becomes `target/workflows/hr_daily.json` (standards §8).
- Never edit `legacy/` (including `legacy/expected_outputs/` and `legacy/sample_data/`), and never weaken `scripts/validate.py` or `target/lib/validation.py`.

## Definition of done
```bash
python3 scripts/validate.py <job>      # must print PASS (exact sorted-row match vs goldens)
python3 scripts/validate.py --all
python3 -m pytest -q target/tests
flake8
```
Then open a PR against `main` with the validate output in the description. Playbooks: `!migrate_job` (one job), `!migrate_wave` (parallel wave across all remaining jobs).
