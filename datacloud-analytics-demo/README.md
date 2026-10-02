# DataCloud Analytics (demo)

A miniature workforce-analytics product used to demo an agent-native development lifecycle: a Jira-style requirement
goes in, a reviewed PR comes out.

- **Metrics engine** (`metrics/`, Python + pandas) computes monthly headcount, turnover, and overtime rate by
  department from a deterministic seed snapshot in `data/`.
- **Dashboard** (`dashboard/`, Vite + React + TypeScript + Recharts) renders the generated metric JSON as storyboards.
- Fully local — no external APIs, databases, or credentials.

## Quick start

Requires Python ≥ 3.10 and Node ≥ 20.19.

```bash
cd datacloud-analytics-demo
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python scripts/compute_metrics.py

cd dashboard
npm ci
npm test
npm run dev        # → http://localhost:5173
```

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — data model, engine contract, and the add-a-metric flow.
- [MDD-98](https://cog-gtm.atlassian.net/browse/MDD-98) — the demo ticket in Jira (offline copy: [`docs/requirements/INT-1042-overtime-benchmark.md`](docs/requirements/INT-1042-overtime-benchmark.md)).
- [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) — presenter script.
- [`PLAYBOOK.md`](PLAYBOOK.md) — Devin Playbook for adding a metric.
- [`AGENTS.md`](AGENTS.md) — commands and conventions for coding agents.
