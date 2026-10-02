# Playbook: Add a metric to DataCloud Analytics

> Saved in Devin as a playbook (keep in sync when editing). Name:
> **"DataCloud Analytics — Add a Metric"**. Macro: `!add_metric`.

---

## Overview

Implement a new workforce metric in the DataCloud Analytics demo (`datacloud-analytics-demo/` in the `Demos`
repository) end to end — engine function, tests, registry entry, regenerated JSON, dashboard card, and storyboard —
and open a reviewed-quality PR. The input is usually a Jira ticket (e.g. `MDD-98` on cog-gtm.atlassian.net), or a ticket file in `docs/requirements/`.

## What's Needed From User

- The ticket: a Jira key such as `MDD-98` (read it through the Jira integration or Atlassian MCP), a path such as
  `docs/requirements/INT-1042-overtime-benchmark.md`, or pasted text.
- Optional: answers to any open questions you raise (see Procedure step 3). If the user doesn't answer, proceed with
  your stated assumptions.

## Procedure

1. **Read the ticket.** For a Jira key, fetch the issue from cog-gtm.atlassian.net with the Atlassian MCP (`getJiraIssue`), including its description and comments. Move it to **In Progress** if the workflow allows.
2. **Orient.** Work inside `datacloud-analytics-demo/`. Read `AGENTS.md`, `docs/ARCHITECTURE.md` (especially "Engine
   contract" and "Adding a metric"), the ticket, `metrics/registry.py`, one existing metric module (e.g.
   `metrics/overtime.py`) and its test, `dashboard/src/config/metricCards.ts`, and
   `dashboard/src/config/storyboards.ts`. Set up if needed:
   `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` and `(cd dashboard && npm ci)`.
3. **Review the ticket before coding.** List every requirement that is ambiguous or underspecified — e.g. an undefined
   threshold ("high", "significant"), behaviour for empty groups / zero denominators, a vague or non-conventional
   metric key, a grouping dimension that doesn't match the engine contract. Post them to the user as a short numbered
   list, each with the assumption you will make if not told otherwise. Do not block waiting for answers; continue with
   the stated assumptions and carry them into the PR description.
4. **Plan.** Share a short checklist mapping each acceptance criterion to the file(s) you will change.
5. **Branch.** `git checkout -b devin/<ticket-id-lowercase>-<short-slug>` from `main`.
6. **Engine function.** Create `metrics/<name>.py` exposing `compute_<key>(data_dir: str | Path) -> pd.DataFrame`.
   - Load data only through `metrics.snapshot.load_snapshot`; build the result with `metrics.snapshot.finalize` so it has
     exactly `period`, `department`, `value`, one row per period × group, and an `All Departments` rollup computed from
     the underlying records (not an average of groups).
   - For non-department groupings (e.g. industry cohort), put the group label in the `department` column.
   - Guard every division; decide and document behaviour for groups with no employees or no hours.
   - Module docstring states the formula, units, and edge-case behaviour.
7. **Tests.** Add `metrics/tests/test_<name>.py` using the `mini_snapshot` fixture (extend its CSVs and
   `fixtures/README.md` if needed — never edit `data/` for tests). Hand-compute expected values in comments. Cover:
   the rollup, each threshold boundary (value exactly at the threshold, just above, just below), empty / zero-employee
   groups, and determinism. Run `.venv/bin/python -m pytest` until green.
8. **Registry entry.** Append a `MetricDefinition` to `_DEFINITIONS` in `metrics/registry.py` with a snake_case key,
   label, one-sentence description, `unit` (`count | percent | currency | hours | index`), and `higher_is_better`.
   Update `metrics/tests/test_registry.py` if it asserts the set of keys.
9. **Regenerate JSON.** `.venv/bin/python scripts/compute_metrics.py`; confirm `dashboard/public/metrics/<key>.json`
   and `index.json` changed as expected and contain no NaN/null. Commit the generated files.
10. **Dashboard card.** Add the key to `METRIC_CARDS` in `dashboard/src/config/metricCards.ts` (pick an accent from the
   existing neutral palette family; caption ≤ 45 characters).
11. **Storyboard.** Add or update a storyboard in `dashboard/src/config/storyboards.ts` — `headline` cards plus
    `sections` using `trend` / `departments` / `breakdown` charts, each with a one-sentence narrative grounded in the
    actual generated numbers. Only add new React components if the ticket genuinely needs a visual the existing chart
    kinds can't express; keep them small and add a Vitest test.
12. **Verify everything.**
    `.venv/bin/python -m pytest` · `(cd dashboard && npm test)` · `(cd dashboard && npm run build)` — all green, no
    warnings introduced.
13. **Frontend verification (required).** Start the dev server (`cd dashboard && npm run dev`, port 5173), open
    http://localhost:5173 in the browser, and navigate the main pages: every storyboard in the sidebar, the new metric's
    page (`#/metrics/<key>`), and at least one existing metric page. Confirm the new card shows a headline number and
    trend, charts render, there are no console errors, and existing pages are unchanged. Record the browser session
    and capture screenshots of the new storyboard and metric page as proof.
14. **Open the PR** against `main` titled `<TICKET-ID>: <ticket title>`. Description sections: Summary (formula in one
    line), Changes (engine / registry / JSON / dashboard), Verification (commands run + screenshots/recording),
    **Open questions & assumptions** (from step 3), Out of scope. If the ticket is in Jira, comment the PR link and the open questions on it.
15. **Review loop.** For each review comment: reply acknowledging it, make the change in a new commit (never
    force-push or amend), re-run step 12 (and step 13 if UI changed), push, and reply on the thread with what changed.
    If a comment renames the metric key, rename it everywhere: registry, module/function name if keyed, tests, JSON
    filename (re-run the compute script so the stale file is pruned), card config, storyboard, PR text.

## Specifications

- `pytest`, `npm test`, and `npm run build` pass on the PR branch.
- `dashboard/public/metrics/<key>.json` exists, is listed in `index.json`, and was produced by the compute script.
- The metric appears in the sidebar, has a card with a headline number and trend, and is featured on a storyboard.
- Existing metrics' JSON is byte-for-byte unchanged unless the ticket asks otherwise.
- Every assumption about an ambiguous requirement is written down in the PR description.

## Advice and Pointers

- `config.test.ts` will fail if you add JSON without a card config or forget the storyboard — that's intentional.
- The seed snapshot has a department with zero employees (Field Services → Field Operations cohort); any per-employee
  or per-hour metric must handle it explicitly.
- Percent values are 0–100. Currency is USD; the dashboard formats `unit: "currency"` automatically.
- Use `--only <key>` with the compute script for fast iteration, then run it without flags before committing so stale
  files are pruned.
- Keep the diff focused: no refactors of existing metrics, no dependency upgrades, no new external services.

## Forbidden Actions

- Do not modify `data/*.csv` or `scripts/generate_seed_data.py` unless the ticket explicitly requires it.
- Do not hand-edit generated JSON.
- Do not add network calls, external APIs, databases, or credentials.
- Do not push to `main`, force-push, or amend commits; all changes go through the PR.
- Do not delete or weaken existing tests to make the suite pass.
