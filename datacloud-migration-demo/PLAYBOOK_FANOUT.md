<!-- Saved in Devin as playbook "EMR → Databricks migration wave (fan-out)", macro !migrate_wave.
     Paste everything below the line if you need to recreate it. -->

---

# EMR → Databricks migration wave (fan-out)

## Overview
Launch the full migration wave for `milind-cognition/Demos` / `datacloud-migration-demo/`: five parallel child Devin sessions, each running the `!migrate_job` playbook on one legacy job (or the Oozie orchestration), then report back one table of PRs and validation results. The coordinating session does NOT migrate anything itself.

## What's Needed From User
- Nothing beyond the trigger prompt. Optional: a subset of sessions (A–E) to launch, or an instruction to skip a job that has already been migrated.

## Procedure
1. Clone/refresh `milind-cognition/Demos` and `cd datacloud-migration-demo`. Run `python3 scripts/validate.py --list` and note which jobs already have `nb_<job>.py` on `main`; drop those sessions from the wave (unless the user said otherwise).
2. Create the child sessions in ONE `devin_session_create` call: `repos=["milind-cognition/Demos"]`, `tags=["datacloud-migration-wave"]`, `notify_on_response=true` on every spec, and the session titles and prompts exactly as listed under Specifications. Do not edit the prompts.
3. Immediately tell the user the session links (one line each), non-blocking.
4. Wait for notifications. When a child blocks on a question it can answer from `target/MIGRATION_STANDARDS.md` or the `payroll_join` exemplar, answer it via `devin_session_interact`; escalate anything else to the user.
5. When all children have settled, collect from each: PR URL, `python3 scripts/validate.py <job>` result (PASS/FAIL with row counts), and any open caveat.
6. Report one markdown table (Session | Job | PR | Validation | Caveats) to the user. If any child failed validation, say so first.

## Specifications
- Exactly one child per remaining job; children work on separate branches and open separate PRs against `main`. Never merge PRs.
- The five sessions and their prompts:

### Session A — emp_metrics_daily
```
!migrate_job Migrate hive/emp_metrics_daily.sql to the target platform per target/MIGRATION_STANDARDS.md — notebook, workflow.json, passing validation — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar (nb_payroll_join.py, payroll_join.json, target/lib) as the pattern. Outputs are dim_employee (SCD2) and fct_emp_metrics_daily; keep the daily "active" definition (term_date > day) and the LEFT join that keeps D999 employees.
```

### Session B — turnover_snapshot
```
!migrate_job Migrate hive/turnover_snapshot.sql to the target platform per target/MIGRATION_STANDARDS.md — notebook target/notebooks/nb_turnover_snapshot.py, target/workflows/turnover_snapshot.json, passing `python3 scripts/validate.py turnover_snapshot` — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar (nb_payroll_join.py, payroll_join.json, target/lib) as the pattern. Replace the three copy-pasted month blocks with a loop over target/lib/dates.quarter_months(run_date). Keep the turnover "active" definition (term_date >= day) and the inner join to departments.
```

### Session C — cohort_tagger
```
!migrate_job Migrate java/CohortTagger.java to the target platform per target/MIGRATION_STANDARDS.md — notebook target/notebooks/nb_cohort_tagger.py, target/workflows/cohort_tagger.json, passing `python3 scripts/validate.py cohort_tagger` — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar as the pattern and reuse target/lib/hr_transforms (clean_timecards, bucket_hours, current_employee_version) instead of re-implementing the Java copies. Use native DataFrame functions for tenure band / fiscal cohort — no Python UDFs.
```

### Session D — stage_and_publish
```
!migrate_job Migrate the `stage` step of shell/stage_and_publish.sh to the target platform per target/MIGRATION_STANDARDS.md — notebook target/notebooks/nb_stage_and_publish.py producing stage_audit, target/workflows/stage_and_publish.json, passing `python3 scripts/validate.py stage_and_publish` — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar as the pattern. Header validation failures must fail the task; duplicate keys produce WARN_DUP_KEYS exactly as the shell script does.
```

### Session E — Oozie orchestration → hr_daily workflow
```
!migrate_job Convert the legacy orchestration (oozie/workflow.xml, oozie/coordinator.xml, oozie/job.properties and the tail of shell/run_daily.sh) into a single Databricks multi-task job target/workflows/hr_daily.json per target/MIGRATION_STANDARDS.md §8, and open a PR. MIGRATION_STANDARDS.md is the shared playbook; reuse the job_clusters / notebook_task / notification structure of the payroll_join exemplar (target/workflows/payroll_join.json). Tasks: stage_and_publish -> emp_metrics_daily -> payroll_join (mirroring Oozie ok-to transitions), then cohort_tagger, and turnover_snapshot gated by a condition_task for month-close. Reference notebooks by the standard nb_<job> paths even if their migration PRs are still open. Add a pytest under target/tests that checks the DAG (every depends_on resolves, no cycles, every notebook_path follows the nb_<job> convention, run_date is passed to every task) and make sure `python3 -m pytest -q target/tests` and `python3 scripts/validate.py --all` pass.
```

## Advice and Pointers
- `MIGRATION_STANDARDS.md` is the shared contract and `payroll_join` is the reference pattern; point children back to them rather than inventing rules.
- Session E's `hr_daily.json` references notebooks from the other PRs by path; that is expected and fine.
- `scripts/validate.py --all` on a branch that merges all PRs is the closing proof for the demo.

## Forbidden Actions
- Do not implement migrations in the coordinating session.
- Do not merge, force-push, or push to `main`.
- Do not modify `legacy/expected_outputs/` or `legacy/sample_data/`, and do not tell children to.
