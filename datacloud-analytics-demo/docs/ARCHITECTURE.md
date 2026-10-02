# DataCloud Analytics — Architecture

DataCloud Analytics is a miniature workforce-analytics product: a Python **metrics engine** turns an HR/payroll
snapshot into monthly metric values, and a React **dashboard** renders those values as storyboards. Everything runs
locally — no external APIs, databases, or credentials.

```
data/*.csv ──► metrics/<metric>.py ──► metrics/registry.py ──► scripts/compute_metrics.py
 (snapshot)     compute_<key>(data_dir)   MetricDefinition         │ validate + serialize
                -> DataFrame                                       ▼
                                              dashboard/public/metrics/<key>.json + index.json
                                                                   │ fetch at runtime
                                                                   ▼
                                  dashboard/src/config/{metricCards,storyboards}.ts ──► MetricCard / TrendChart / StoryboardPage
```

## Layout

| Path | Purpose |
| --- | --- |
| `data/` | Checked-in, deterministic seed snapshot (see [Data](#data-snapshot)). |
| `metrics/` | Python package: snapshot loader, one module per metric, registry, schema check, JSON export. |
| `metrics/tests/` | pytest suite. `fixtures/mini_snapshot/` is a hand-sized snapshot with hand-computed expectations. |
| `scripts/compute_metrics.py` | Runs every registered metric over `data/` and writes `dashboard/public/metrics/`. |
| `scripts/generate_seed_data.py` | Regenerates `data/` from a fixed seed (only needed if the snapshot shape changes). |
| `dashboard/` | Vite + React + TypeScript app (Recharts for charts, Vitest for tests). |
| `docs/requirements/` | Jira-style tickets for upcoming work. |

## Why pandas (not PySpark)

Production DataCloud pipelines run on Spark, but this demo snapshot is ~13k timecard rows. pandas keeps the engine
dependency-light (`pip install -r requirements.txt`, no JVM), starts instantly, and makes the tests fast enough to run
on every change. Metric functions only use DataFrame operations that have direct PySpark equivalents
(`groupby`/`merge`/filters), so porting a metric is mechanical.

## Data snapshot

| File | Grain | Key columns |
| --- | --- | --- |
| `departments.csv` | department | `department_id`, `department_name`, `cost_center` |
| `employees.csv` | employee | `employee_id`, `department_id`, `job_title`, `flsa_status` (`exempt`/`non_exempt`), `employment_type`, `hourly_rate`, `hire_date` |
| `terminations.csv` | termination | `employee_id`, `termination_date`, `termination_type`, `reason` |
| `timecards.csv` | employee × week | `employee_id`, `week_start` (Monday), `regular_hours`, `overtime_hours` |
| `industry_cohorts.csv` | department | `department_id`, `cohort_id`, `cohort_name`, `naics_sector` |

The window is **Oct 2025 – Sep 2026** (12 monthly periods). Notable properties of the seed data:

- `hourly_rate` is populated for every employee (exempt salaries are expressed as an hourly equivalent).
- Exempt employees never record overtime hours.
- **Field Services** (`D09`, cohort **Field Operations**) is a newly created department with **zero employees** —
  it exists in `departments.csv` and `industry_cohorts.csv` but has no roster, timecards, or terminations.
  Existing metrics omit departments with no employees; any new metric must decide explicitly how to treat them.

## Engine contract

Every metric is a plain function:

```python
def compute_<key>(data_dir: str | Path) -> pd.DataFrame: ...
```

The returned frame must satisfy `metrics/schema.py::validate_metric_frame` (the export step enforces it):

- Columns are exactly `period`, `department`, `value` (`metrics.snapshot.METRIC_COLUMNS`).
- `period` is a `YYYY-MM` string; one row per period in the snapshot window.
- `department` is the grouping label. Metrics grouped by another dimension (e.g. industry cohort) put that label in
  this column — the column name is part of the JSON contract and stays `department`.
- Every period has an `All Departments` rollup row (`metrics.snapshot.ALL_DEPARTMENTS`) computed from the underlying
  records — **not** an average of the group rows.
- `value` is numeric and never null; no duplicate `(period, department)` pairs.
- Build the frame with `metrics.snapshot.finalize(rows, groups)` so ordering is canonical (period, groups A–Z,
  rollup last).

Conventions:

- Load data only via `metrics.snapshot.load_snapshot(data_dir)`; never read CSVs directly.
- A metric is a pure function of the snapshot: deterministic, no I/O besides loading, no wall-clock dates.
- Guard every division. Existing metrics report `0.0` when the denominator is zero; document the choice in the
  module docstring.
- Percent metrics return 0–100 (not 0–1). Currency is USD. Counts are rounded to integers on export.

## Registry — the single extension point

`metrics/registry.py` holds one `MetricDefinition` per metric:

```python
MetricDefinition(
    key="overtime",                 # snake_case, unique; becomes the JSON filename and the dashboard route
    label="Overtime Rate",          # display name
    description="...",              # one sentence, shown under the page title
    unit="percent",                 # count | percent | currency | hours | index  (drives formatting)
    higher_is_better=False,         # drives green/red delta colouring
    compute=compute_overtime,
)
```

Nothing else enumerates metrics: the compute script, the JSON index, and the dashboard navigation are all derived
from the registry. Keys are validated against `^[a-z][a-z0-9_]*$` and must be unique.

## Compute script → JSON

```bash
python scripts/compute_metrics.py                 # all metrics (also prunes stale <key>.json files)
python scripts/compute_metrics.py --only overtime # one metric
```

For each registered key it validates the frame and writes `dashboard/public/metrics/<key>.json`:

```json
{
  "schema_version": 1,
  "key": "overtime",
  "label": "Overtime Rate",
  "description": "...",
  "unit": "percent",
  "higher_is_better": false,
  "periods": ["2025-10", "...", "2026-09"],
  "total": [{ "period": "2025-10", "value": 4.21 }],
  "by_department": [{ "department": "Finance", "series": [{ "period": "2025-10", "value": 1.9 }] }]
}
```

plus `index.json` listing every metric. Generated JSON **is checked in** so the dashboard runs straight from a fresh
clone; always regenerate and commit it alongside engine changes.

## Dashboard

- `src/lib/data.ts` fetches `metrics/index.json` and every `<key>.json` on load (`MetricsProvider`).
- `src/config/metricCards.ts` — presentation per metric key: accent colour + one-line caption.
- `src/config/storyboards.ts` — storyboards: `headline` metric keys (rendered as `MetricCard`s) and `sections`, each a
  `TrendChart` of kind `trend` (company total), `departments` (one line per group), or `breakdown` (latest period,
  one bar per group) with a title and a one-sentence narrative.
- Routes (hash-based): `#/storyboards/<id>` and `#/metrics/<key>`. The sidebar lists storyboards and every metric in
  `index.json` automatically.
- `src/config/config.test.ts` fails if a computed metric has no card config, if a storyboard references a metric that
  is not in `public/metrics/`, or if a metric is not featured on any storyboard.

## Adding a metric (the documented flow)

1. **Engine function** — `metrics/<name>.py` with `compute_<key>(data_dir) -> DataFrame` following the contract
   above; docstring states the formula and zero-denominator behaviour.
2. **Tests** — `metrics/tests/test_<name>.py` against `fixtures/mini_snapshot/` with hand-computed expected values,
   covering the rollup, boundaries (thresholds, month-end), and empty groups. Extend the fixture CSVs if needed and
   update `fixtures/README.md`.
3. **Registry entry** — append a `MetricDefinition` to `_DEFINITIONS` in `metrics/registry.py`.
4. **Compute script** — `python scripts/compute_metrics.py`; commit the new `<key>.json` and updated `index.json`.
5. **Dashboard card** — add the key to `METRIC_CARDS` in `dashboard/src/config/metricCards.ts`.
6. **Storyboard entry** — feature the metric on an existing storyboard or add a new one in
   `dashboard/src/config/storyboards.ts`.
7. **Verify** — `pytest`, `npm test`, `npm run build`, then `npm run dev` and check the new card, metric page, and
   storyboard in the browser.

The metric page (`#/metrics/<key>`) and sidebar entry appear automatically once the JSON exists.
