# INT-1042 — Add an overtime-cost benchmark metric by industry cohort

> Live in Jira as **[MDD-98](https://cog-gtm.atlassian.net/browse/MDD-98)**. This file is the offline copy of the same ticket.

| Field | Value |
| --- | --- |
| **Type** | Story |
| **Project** | INT — DataCloud Insights |
| **Status** | Ready for Development |
| **Priority** | High |
| **Reporter** | Dana Whitfield (Product Manager, Workforce Insights) |
| **Assignee** | _Unassigned_ |
| **Sprint** | INT Sprint 31 |
| **Story points** | 5 |
| **Labels** | `metrics-engine`, `dashboard`, `benchmarking`, `q4-launch` |
| **Components** | Metrics Engine, Storyboards |
| **Epic** | INT-980 — Benchmarking & Peer Comparison |
| **Linked issues** | relates to INT-1017 (Overtime Rate metric), blocks INT-1051 (CFO labor-cost storyboard) |

## Summary

As a **finance or HR leader**, I want to see **what overtime is costing us per employee in each industry cohort**, so
that I can tell whether a team's overtime spend is normal for the kind of work it does or a signal that it is
understaffed.

## Description

Today the dashboard shows **Overtime Rate** (overtime hours as a share of total hours). Customers keep telling us that
hours alone don't land with finance: 6% overtime in a warehouse and 6% overtime in payroll operations cost very
different amounts, and nobody can say whether either is "good". In the Q3 customer advisory board, three of five
customers asked for overtime **cost** with a **peer benchmark**.

We already map every department to an industry cohort (`data/industry_cohorts.csv` — Technology, Professional
Services, Financial Services, Transportation & Logistics, Field Operations). We want a new metric that rolls overtime
cost up to those cohorts so leaders can compare like with like.

**Proposed calculation**

- Overtime cost for a timecard = `overtime_hours × hourly_rate × 1.5` (standard time-and-a-half premium).
- For each month and each industry cohort:
  `overtime cost per employee = total overtime cost of the cohort's departments ÷ active employees in the cohort`.
- Active employees should be counted the same way the existing Headcount metric does (active on the last day of the
  month).
- The company-wide rollup is the same calculation across all employees.

Please call the metric something like `overtime_benchmark` (or whatever fits our naming). It should follow the
standard add-a-metric flow in `docs/ARCHITECTURE.md` so it shows up in the dashboard like the other metrics.

On the dashboard, finance wants a dedicated page that tells the cost story: the company trend, how each cohort
compares, and where we are running hot. Cohorts with **high overtime** should stand out visually so a CFO can spot
them in a few seconds.

## Acceptance Criteria

1. A new metric is available in the metrics engine that returns overtime cost per employee by **month** and
   **industry cohort**, plus the company-wide rollup, and passes the standard metric schema validation.
2. The metric is registered in the metric registry and is produced by `scripts/compute_metrics.py`; the generated JSON
   is committed under `dashboard/public/metrics/`.
3. Values are shown in US dollars.
4. **Every cohort in `industry_cohorts.csv` appears in the benchmark.**
5. Cohorts with high overtime are flagged so they can be highlighted in the dashboard.
6. The dashboard has a metric card for the new metric (headline number + trend), and a new storyboard page
   ("Overtime Cost Benchmark") featuring it alongside the existing Overtime Rate metric.
7. Unit tests cover the calculation, including the company-wide rollup.
8. Existing metrics, tests, and storyboards are unchanged and still pass.

## Out of Scope

- Pulling real benchmark data from external sources (BLS, industry surveys) — cohorts are benchmarked against each
  other using our own snapshot only.
- Changing the overtime premium per state or union rules; assume 1.5× everywhere.
- Department-level drill-down for this metric (cohort level is enough for v1).
- Currency conversion / non-USD customers.
- Alerting or emailing when a cohort crosses the threshold.
- Changes to the seed data in `data/`.

## Notes / Attachments

- Mock from design review: _"Overtime Cost Benchmark" storyboard — headline card, cohort comparison bars, company
  trend._ (Figma link pending)
- Finance contact for sign-off on the formula: Marcus Lee (FP&A).

## Comments

> **Marcus Lee (FP&A)** — 2 days ago
> Formula looks right to me. Please make sure the cohort numbers reconcile to the company total in some obvious way —
> the CFO will check.

> **Dana Whitfield** — yesterday
> Engineering, we'd like this in the Sprint 31 demo build. Ping me in the PR if anything is unclear.
