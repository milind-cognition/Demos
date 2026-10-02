# Demo Runbook — "Retire the EMR HR batch onto Databricks, live"

**Audience:** data-platform leaders + engineers who own a Hadoop/EMR estate.
**Length:** ~35 min (Act 1: 7 · Act 2: 5 · Act 3: 13 · Act 4: 10).
**Repo:** `https://github.com/milind-cognition/Demos` → folder `datacloud-migration-demo/` (every
path below is relative to it).

## Quick version — one prompt, ~15 min

Use this when you want the whole story driven by a single prompt. The full four-act script below
is the long version.

| Step | Show | Say |
|---|---|---|
| 1. Pain (2 min) | `legacy/`: duplicated timecard logic in `hive/emp_metrics_daily.sql`, `pig/payroll_join.pig`, `java/CohortTagger.java`; hard-coded `2024-03-15`; `shell/run_daily.sh` sleep/poll/email loop | "Every enterprise has this, and nobody touches it because nobody can prove a rewrite is correct." |
| 2. Guardrails (2 min) | `target/MIGRATION_STANDARDS.md`, `nb_payroll_join.py`, then `python3 scripts/validate.py payroll_join` → PASS | "Devin gets the rules and the worked example a senior engineer would get, plus an objective definition of done." |
| 3. One prompt (1 min to launch) | Paste the prompt below into one new Devin session | "One request, five engineers working in parallel, one shared playbook." |
| 4. Watch (5 min) | The coordinator's session list; click into one child to see its plan and the validator running | "Each session reads the legacy job, reuses the shared library, and proves itself against the golden data." |
| 5. Review (5 min) | One PR side by side with the legacy SQL; the validator output in the PR; the coordinator's summary table of all PRs | "You review evidence (an exact data match), not vibes." |

```
!databricks_migration Launch the datacloud-migration-demo migration wave for milind-cognition/Demos.
```

The wave launches five sessions (emp_metrics_daily, turnover_snapshot, cohort_tagger,
stage_and_publish, Oozie → `hr_daily.json`). It skips any job that already has a notebook on `main`.

---

## Pre-flight (T-30 min)

1. `main` contains only the `payroll_join` exemplar migration:
   `python3 scripts/validate.py --list` → only `payroll_join` shows `notebook workflow`.
   If a previous rehearsal merged `emp_metrics_daily`, revert that merge (or close the PR unmerged)
   before the demo.
2. On the presenter laptop: `python3 scripts/validate.py payroll_join` → `SUMMARY payroll_join PASS`.
3. Devin: Playbook **"EMR → Databricks job migration"** saved from `PLAYBOOK.md` (macro
   `!migrate_job`), Knowledge notes from the setup checklist added, repo `milind-cognition/Demos`
   connected.
4. Tabs open: GitHub repo at `datacloud-migration-demo/`, the Devin web app, a terminal in
   `datacloud-migration-demo/`.

---

## Act 1 — Pain tour (≈7 min)

**Talking points**
* "This is what fifteen years of Hadoop looks like: six jobs, four languages, one set of business
  rules copy-pasted into three of them — and the March close date hard-coded everywhere."
* "Nobody wants to touch this because nobody can prove a rewrite produces the same numbers. That's
  the problem we're actually solving today."

**Presenter walk (show the files yourself):**
1. `legacy/oozie/workflow.xml` → `stage` (shell) → `emp_metrics_daily` (hive2) → `payroll_join`
   (pig), email on failure. Then `legacy/shell/run_daily.sh`: CohortTagger and turnover are bolted on
   *outside* Oozie, with `sleep 60` polling and `mail` alerts.
2. Duplication: search `keep in sync` / `copy of the hive/pig` → the timecard-clean + OT rollup in
   `hive/emp_metrics_daily.sql`, `pig/payroll_join.pig`, `java/CohortTagger.java`.
3. Magic dates: `2024-03-15`, `2024-03-11`, `HRDE-388` in all of them; the three copy-pasted month
   blocks in `hive/turnover_snapshot.sql` ("copy the block for April").
4. `SELECT *` / `SELECT DISTINCT *` in both Hive scripts; two different definitions of "active".

**Optional Devin prompt (Ask/Search):**

```
Give me a pain tour of datacloud-migration-demo/legacy/. For each of the 6 jobs: what it does, how it is triggered (Oozie vs run_daily.sh), its inputs/outputs, and its hard-coded dates. Then list every business rule that is duplicated across the Hive, Pig and Java jobs with file:line references, and every place SELECT * is used. Finish with the top 5 migration risks, citing legacy/README.md "Known quirks".
```

---

## Act 2 — Live migration (≈5 min to launch)

**Talking points**
* "One sentence of intent. The standards doc and the exemplar do the rest — this is how you scale a
  migration factory without scaling the team."
* "Notice the prompt says *passing validation*: done means byte-for-byte equal to what legacy
  produces, not 'looks right'."

Show `target/MIGRATION_STANDARDS.md` (§4 shim, §5 shared lib, §7 validate) and
`target/notebooks/nb_payroll_join.py` for 60 seconds, then start a new Devin session on the repo
with **exactly**:

```
Migrate hive/emp_metrics_daily.sql to the target platform per target/MIGRATION_STANDARDS.md — notebook, workflow.json, passing validation — and open a PR.
```

(If the audience asks "where is that file?": all paths are inside `datacloud-migration-demo/`;
Devin finds it. To be explicit, prefix the prompt with `In datacloud-migration-demo/, `.)

---

## Act 3 — Review the plan, watch, validate, review the PR (≈13 min)

**Talking points**
* "Devin read the legacy SQL, the standards, and the exemplar before writing a line — the plan
  already calls out the SCD2 surrogate keys and the D999 left join that would trip up a human."
* "Validation is the reviewer's best friend: the PR proves equivalence, so the review is about
  design, not arithmetic."

1. **Plan review** — when Devin posts its plan, check it names: `nb_emp_metrics_daily.py`,
   `target/workflows/emp_metrics_daily.json`, reuse of `clean_timecards` / `bucket_hours`, a new
   shared SCD2 helper in `target/lib/`, both outputs (`dim_employee`, `fct_emp_metrics_daily`),
   and preserved quirks (per-day rate, `term_date > day`, LEFT JOIN keeps `D999`). If a point is
   missing, reply in the session:

   ```
   Before implementing: reuse target/lib/hr_transforms.clean_timecards and bucket_hours, put the SCD2 versioning in target/lib with a unit test, preserve every quirk in legacy/README.md "Known quirks" that applies to emp_metrics_daily, and derive all dates from run_date via target/lib/dates.py.
   ```

2. **Watch** — show the shell/editor: notebook cells mirroring the Hive steps, `validate.py`
   iterations converging (first run often shows a rounding or join-type diff — narrate how the
   report pinpoints it).
3. **Validate yourself** in the terminal once the branch is pushed:

   ```bash
   git fetch origin && git checkout <devin-branch>
   python3 scripts/validate.py emp_metrics_daily
   python3 scripts/validate.py --all          # exemplar still green
   python3 -m pytest -q target/tests
   ```

   Or ask Devin in the session:

   ```
   Run python3 scripts/validate.py emp_metrics_daily and python3 scripts/validate.py --all from datacloud-migration-demo/ and paste the full output into the PR description.
   ```

4. **PR review** — walk the diff: notebook header lists preserved quirks; no `SELECT *`; no date
   literals; workflow JSON mirrors `payroll_join.json`; CI (`datacloud-migration-demo` check) green.
   Optional: ask Devin Review / leave a comment and let Devin address it.

---

## Act 4 — Fan-out (≈10 min)

**Talking points**
* "The first migration taught the system the pattern; now it's parallel. Four sessions, one
  playbook, one validator — a wave, not a backlog."
* "Each PR is independently provable, so you can review and merge them in any order."

**One-prompt option (recommended on stage):** paste this into a single new session and it launches
the four sessions below for you, then reports a PR/validation table:
```
!databricks_migration Launch the datacloud-migration-demo migration wave for milind-cognition/Demos. Skip emp_metrics_daily; it is already in flight from Act 2.
```

**Manual option:** launch **4 parallel Devin sessions** (one per job). Use the Playbook macro so every session gets the
same procedure. Paste each prompt into its own new session:

**Session A — turnover_snapshot**
```
!migrate_job Migrate hive/turnover_snapshot.sql to the target platform per target/MIGRATION_STANDARDS.md — notebook target/notebooks/nb_turnover_snapshot.py, target/workflows/turnover_snapshot.json, passing `python3 scripts/validate.py turnover_snapshot` — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar (nb_payroll_join.py, payroll_join.json, target/lib) as the pattern. Replace the three copy-pasted month blocks with a loop over target/lib/dates.quarter_months(run_date). Keep the turnover "active" definition (term_date >= day) and the inner join to departments.
```

**Session B — cohort_tagger**
```
!migrate_job Migrate java/CohortTagger.java to the target platform per target/MIGRATION_STANDARDS.md — notebook target/notebooks/nb_cohort_tagger.py, target/workflows/cohort_tagger.json, passing `python3 scripts/validate.py cohort_tagger` — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar as the pattern and reuse target/lib/hr_transforms (clean_timecards, bucket_hours, current_employee_version) instead of re-implementing the Java copies. Use native DataFrame functions for tenure band / fiscal cohort — no Python UDFs.
```

**Session C — stage_and_publish**
```
!migrate_job Migrate the `stage` step of shell/stage_and_publish.sh to the target platform per target/MIGRATION_STANDARDS.md — notebook target/notebooks/nb_stage_and_publish.py producing stage_audit, target/workflows/stage_and_publish.json, passing `python3 scripts/validate.py stage_and_publish` — and open a PR. MIGRATION_STANDARDS.md is the shared playbook; follow the payroll_join exemplar as the pattern. Header validation failures must fail the task; duplicate keys produce WARN_DUP_KEYS exactly as the shell script does.
```

**Session D — Oozie orchestration → hr_daily workflow**
```
!migrate_job Convert the legacy orchestration (oozie/workflow.xml, oozie/coordinator.xml, oozie/job.properties and the tail of shell/run_daily.sh) into a single Databricks multi-task job target/workflows/hr_daily.json per target/MIGRATION_STANDARDS.md §8, and open a PR. MIGRATION_STANDARDS.md is the shared playbook; reuse the job_clusters / notebook_task / notification structure of the payroll_join exemplar (target/workflows/payroll_join.json). Tasks: stage_and_publish -> emp_metrics_daily -> payroll_join (mirroring Oozie ok-to transitions), then cohort_tagger, and turnover_snapshot gated by a condition_task for month-close. Reference notebooks by the standard nb_<job> paths even if their migration PRs are still open. Add a pytest under target/tests that checks the DAG (every depends_on resolves, no cycles, every notebook_path follows the nb_<job> convention, run_date is passed to every task) and make sure `python3 -m pytest -q target/tests` and `python3 scripts/validate.py --all` pass.
```

Close by showing the four PRs side by side and `python3 scripts/validate.py --list` on a branch
that merges them.

---

## Reset after the demo

Close (don't merge) the demo PRs, or revert their merges on `main`, so the next run starts from the
exemplar-only state. Delete demo branches: `git push origin --delete <branch>`.
