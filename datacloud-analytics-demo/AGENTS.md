# AGENTS.md — DataCloud Analytics demo

All paths are relative to this folder (`datacloud-analytics-demo/`).

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Python >= 3.10
(cd dashboard && npm ci)                                               # Node >= 20.19
```

## Commands (all must pass before opening a PR)

```bash
.venv/bin/python -m pytest                       # engine tests
.venv/bin/python scripts/compute_metrics.py      # regenerate dashboard/public/metrics/*.json (commit the output)
(cd dashboard && npm test)                       # vitest
(cd dashboard && npm run build)                  # tsc --noEmit + vite build
(cd dashboard && npm run dev)                    # http://localhost:5173
```

## Conventions

- Adding or changing a metric follows the flow in `docs/ARCHITECTURE.md` ("Adding a metric"). The registry
  (`metrics/registry.py`) is the only place metrics are enumerated.
- Metric functions: `compute_<key>(data_dir) -> DataFrame[period, department, value]`, built with
  `metrics.snapshot.finalize`, loaded via `load_snapshot`, every division guarded, behaviour documented in the module
  docstring.
- Metric keys are `snake_case`; the key is the JSON filename and the dashboard route.
- Generated JSON in `dashboard/public/metrics/` is committed; never hand-edit it.
- Do not modify `data/` (the seed snapshot) unless the ticket says so. Test-only data goes in
  `metrics/tests/fixtures/mini_snapshot/`.
- Everything runs locally: no network calls, external APIs, or credentials.
- When a ticket is ambiguous (thresholds, empty groups, naming), state the assumption you made in the PR description
  under "Open questions", and prefer the most conservative reading.
