# Demo Runbook — "Jira ticket in, reviewed PR out"

**Audience:** engineering leaders / platform teams. **Length:** 20–30 min (Acts 1–4), +5 min for Act 5.
**Story:** a real-looking product (metrics engine + dashboard), a real-looking ticket with real-looking gaps, and Devin
taking it from requirement to a reviewed, green PR while the presenter only plays product owner and reviewer.

## Before you go on stage (T–15 min)

```bash
git clone https://github.com/milind-cognition/Demos.git && cd Demos/datacloud-analytics-demo
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest                    # expect: all passed
cd dashboard && npm ci && npm run dev         # leave running → http://localhost:5173
```

- Browser tabs: (1) http://localhost:5173/#/storyboards/workforce-overview, (2) the repo on GitHub,
  (3) `docs/requirements/INT-1042-overtime-benchmark.md` on GitHub, (4) a fresh Devin session with the
  **DataCloud Analytics — Add a Metric** playbook attached (see `PLAYBOOK.md`).
- Make sure `main` has no open INT-1042 PR or branch left over from a rehearsal (close/delete it).
- Optional safety net: have a pre-recorded run of Acts 2–4 ready in case the network or venue misbehaves.

---

## Act 1 — Tour (3–4 min)

**Show**
1. Dashboard tab → **Workforce Overview**: three cards (Headcount 250, Turnover 1.6%, Overtime 3.8%), headline
   number + month-over-month delta + sparkline. Click **Overtime Rate** in the sidebar → department table: Warehouse and
   Fleet run 8–10%, engineering ~0.3%.
2. Repo → `metrics/registry.py` (three `MetricDefinition`s), `metrics/overtime.py` (a ~40-line pandas function), and
   `docs/ARCHITECTURE.md` → scroll to **"Adding a metric"**: engine function → registry → compute script → JSON →
   card + storyboard.
3. Ticket tab → **INT-1042**: read the Summary and Acceptance Criteria aloud. Don't point out the gaps.

**Talking points**
- "This is the shape of most analytics teams' work: a metrics engine, a dashboard, and a backlog of tickets that are
  *mostly* clear."
- "The architecture doc is the team's tribal knowledge written down — that's exactly what Devin will follow."

---

## Act 2 — Kickoff (1 min)

Paste this into the Devin session (playbook attached), exactly:

```text
Implement docs/requirements/INT-1042-overtime-benchmark.md end to end per docs/ARCHITECTURE.md — engine function, registry entry, tests, regenerated metric JSON, dashboard card + storyboard page — and open a PR.
```

> All paths are relative to `datacloud-analytics-demo/` in the `Demos` repo. If Devin asks where to work, answer:
> `Work in the datacloud-analytics-demo/ folder of the Demos repo, branch off main.`

**Talking points**
- "One sentence. No hand-holding — the ticket and the repo's own docs are the spec."
- "The playbook encodes how *this team* adds a metric, so every engineer — human or Devin — does it the same way."

---

## Act 3 — Plan and checkpoints (8–12 min, mostly while Devin works)

**Show**, as they appear in the session:
1. **Ticket review** — Devin's list of ambiguities with stated assumptions (expect: "high overtime" threshold, the
   zero-employee Field Operations cohort, the metric key). Pause here; this is the money moment.
2. **Plan** — acceptance criteria mapped to files (`metrics/<name>.py`, tests, `registry.py`, JSON,
   `metricCards.ts`, `storyboards.ts`).
3. **Checkpoints** — `pytest` going green, `compute_metrics.py` writing the new JSON, `npm test` / `npm run build`
   passing, then Devin opening the dashboard in its own browser to check the new storyboard.
4. **The PR** — description with Summary, Verification (screenshots), and **Open questions & assumptions**.

While waiting, you can open Devin's shell/IDE view to show the diff taking shape.

**Talking points**
- "Notice it read the ticket like a senior engineer would — it found the gaps *before* writing code, and said what it
  would assume."
- "It isn't done when the code compiles: it ran the same tests, build, and browser check your engineers would."

---

## Act 4 — Review loop (5–7 min)

Open the PR. Post these as review comments (inline on the relevant file where possible, otherwise as PR comments).
Post all three, then submit the review.

**Comment 1** — on `metrics/registry.py` (the new `MetricDefinition`):
```text
Please rename the metric key to ot_cost_benchmark — that matches how finance refers to it and keeps the "ot_" prefix we use in the warehouse. Rename everywhere (registry, JSON filename, card config, storyboard, tests).
```

**Comment 2** — on the new engine module (`metrics/<name>.py`):
```text
Handle the zero-employee cohort case explicitly: Field Operations currently has no active employees. It must still appear in the output (AC 4) with a value of 0 rather than NaN/inf or being dropped, and the docstring should say so. Please add a test for it.
```

**Comment 3** — on the new test file:
```text
Add a test for the threshold boundary: a cohort exactly at the "high overtime" threshold, one just below, and one just above, so we lock in whether the comparison is > or >=. Make the threshold a named constant.
```

Then tell Devin in the session (or let it pick the review up from GitHub):
```text
I've left review comments on the PR — please address them and push.
```

**Show** Devin replying on each thread, pushing new commits, CI/tests green again, and the renamed metric at
`http://localhost:5173/#/metrics/ot_cost_benchmark` after you pull the branch (or in Devin's screenshots).

**Talking points**
- "Review is a conversation, not a re-do — Devin treats comments like a teammate would: acknowledge, fix, re-verify,
  reply."
- "A rename touching six files is exactly the kind of change people get wrong by hand; here it's consistent and tested."

---

## Act 5 (stretch) — The underspecified criterion (3–5 min)

If Devin already flagged the gaps in Act 3, scroll back to that message and call it out. Otherwise, prompt it:

```text
Before we merge: acceptance criterion 5 says cohorts with "high overtime" should be flagged. What threshold did you use, and what would you need from product to make it final?
```

Optional follow-up to show it acting on the answer:
```text
Product confirmed: a cohort is "high overtime" when its overtime cost per employee is at least 25% above the company-wide value for the same month. Update the implementation, tests, and PR description accordingly.
```

**Talking points**
- "The dangerous failure mode for AI coding isn't bad syntax — it's confidently guessing at a requirement. Devin
  surfaces the guess and asks."
- "That's what makes it safe to put in your real backlog: ambiguity becomes a question in the PR, not a bug in prod."

---

## Reset after the demo

Close the PR and delete its branch (`devin/int-1042-*`). `main` is untouched, so the next demo starts clean.

## Known ambiguities in INT-1042 (presenter cheat sheet — don't show)

| # | Where | Gap |
| --- | --- | --- |
| 1 | AC 5 / Description | "High overtime" has no threshold, comparison operator, or baseline. |
| 2 | AC 4 + seed data | Field Operations cohort has zero employees → cost ÷ 0 employees is undefined. |
| 3 | Description | Key is "something like `overtime_benchmark` (or whatever fits)" — reviewer asks for `ot_cost_benchmark`. |
| bonus | AC 1 vs engine contract | Metric is by cohort, but the engine contract is by department (documented convention: cohort label goes in `department`). |
