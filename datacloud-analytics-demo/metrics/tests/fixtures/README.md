# `mini_snapshot`

Hand-built snapshot with values small enough to verify by hand. Expected
metric values in the tests are derived from these rows.

| Dept | Employees | Notes |
| --- | --- | --- |
| D10 Assembly | E1, E2, E3 (all non-exempt) | E2 leaves 2026-02-20; E3 hired 2026-02-10 |
| D20 Analytics | E4, E5 (exempt), E6 (non-exempt, part-time) | E5 leaves 2026-03-31 (month-end boundary) |
| D30 Expansion | none | mapped to cohort `NEW`, so that cohort has zero employees |

Periods: 2026-01 .. 2026-03 (one timecard week per month).
