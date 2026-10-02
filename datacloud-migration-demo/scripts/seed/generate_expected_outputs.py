#!/usr/bin/env python3
"""Reference (oracle) implementation of the legacy job semantics -> legacy/expected_outputs/.

The golden CSVs under legacy/expected_outputs/ are committed and are the validation source of
truth for every migration. This script exists only so they are reproducible and auditable; it is
a plain-stdlib, Decimal-based re-statement of what the Hive / Pig / Java / shell jobs do on the
March-2024 close (run_date 2024-03-15), including their documented quirks (legacy/README.md).

Migrated notebooks must NOT import or copy this file -- they implement the logic in PySpark using
target/lib/. Re-running it must produce no git diff:

    python scripts/seed/generate_expected_outputs.py
"""
import csv
import datetime as dt
import os
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SD = os.path.join(ROOT, "legacy", "sample_data")
EO = os.path.join(ROOT, "legacy", "expected_outputs")
D0 = Decimal("0")
OT_CODES = ("OT", "DT")
PTO_CODES = ("PTO", "HOL")


def q2(x):
    return str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def load(name):
    with open(os.path.join(SD, name), newline="") as fh:
        return list(csv.DictReader(fh))


def write(job, dataset, cols, rows):
    os.makedirs(os.path.join(EO, job), exist_ok=True)
    rows = sorted(rows, key=lambda r: [str(r[c]) for c in cols])
    with open(os.path.join(EO, job, dataset + ".csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    print(job, dataset, len(rows))


def mdy(s):
    m, d, y = s.split("/")
    return "%s-%s-%s" % (y, m.zfill(2), d.zfill(2))


def clean_timecards(tcs, start, end):
    latest = {}
    for r in tcs:
        k = r["timecard_id"]
        if k not in latest or r["submitted_ts"] > latest[k]["submitted_ts"]:
            latest[k] = r
    out = []
    for r in latest.values():
        if r["approved_flag"] != "Y":
            continue
        wd = mdy(r["work_date"])
        if not (start <= wd <= end):
            continue
        out.append({"timecard_id": r["timecard_id"], "emp_id": r["emp_id"], "work_date": wd,
                    "pay_code": r["pay_code"].strip().upper(), "hours": Decimal(r["hours"])})
    return out


def rollup(tcs, keyf):
    agg = defaultdict(lambda: {"reg": D0, "ot": D0, "pto": D0, "total": D0})
    for r in tcs:
        a = agg[keyf(r)]
        c, h = r["pay_code"], r["hours"]
        if c == "REG":
            a["reg"] += h
        if c in OT_CODES:
            a["ot"] += h
        if c in PTO_CODES:
            a["pto"] += h
        a["total"] += h
    return agg


def latest_version(emps, as_of):
    best = {}
    for r in emps:
        if r["effective_date"] <= as_of:
            if r["emp_id"] not in best or r["effective_date"] > best[r["emp_id"]]["effective_date"]:
                best[r["emp_id"]] = r
    return best


emps = load("employees.csv")
depts = {r["dept_id"]: r for r in load("departments.csv")}
tcs_raw = load("timecards.csv")

# ---------------- stage_and_publish ----------------
RUN_DATE = "2024-03-15"
audit = []
for ds, keyf in [("departments", lambda r: r["dept_id"]),
                 ("employees", lambda r: r["emp_id"] + "|" + r["effective_date"]),
                 ("timecards", lambda r: r["timecard_id"])]:
    rows = load(ds + ".csv")
    keys = set(keyf(r) for r in rows)
    dup = len(rows) - len(keys)
    audit.append({"load_date": RUN_DATE, "dataset": ds, "row_count": len(rows),
                  "distinct_key_count": len(keys), "duplicate_key_count": dup,
                  "status": "WARN_DUP_KEYS" if dup else "OK"})
write("stage_and_publish", "stage_audit",
      ["load_date", "dataset", "row_count", "distinct_key_count", "duplicate_key_count", "status"], audit)

# ---------------- emp_metrics_daily ----------------
END = "2024-03-15"
START = "2024-03-11"
uniq = {tuple(sorted(r.items())): r for r in emps}.values()
versions = sorted([r for r in uniq if r["effective_date"] <= END], key=lambda r: (r["emp_id"], r["effective_date"]))
dim = []
for i, r in enumerate(versions):
    nxt = versions[i + 1] if i + 1 < len(versions) and versions[i + 1]["emp_id"] == r["emp_id"] else None
    dim.append({
        "employee_sk": i + 1, "emp_id": r["emp_id"],
        "full_name": r["first_name"].strip() + " " + r["last_name"].strip(),
        "dept_id": r["dept_id"], "job_title": r["job_title"], "employment_type": r["employment_type"],
        "pay_type": r["pay_type"], "hourly_rate": q2(r["hourly_rate"]), "hire_date": r["hire_date"],
        "term_date": r["term_date"],
        "eff_start_date": r["effective_date"],
        "eff_end_date": (dt.date.fromisoformat(nxt["effective_date"]) - dt.timedelta(days=1)).isoformat() if nxt else "9999-12-31",
        "is_current": "N" if nxt else "Y",
    })
write("emp_metrics_daily", "dim_employee",
      ["employee_sk", "emp_id", "full_name", "dept_id", "job_title", "employment_type", "pay_type",
       "hourly_rate", "hire_date", "term_date", "eff_start_date", "eff_end_date", "is_current"], dim)

tc = clean_timecards(tcs_raw, START, END)
hrs = rollup(tc, lambda r: (r["emp_id"], r["work_date"]))
spine = sorted(set(r["work_date"] for r in tc))
fact = defaultdict(lambda: {"hc": set(), "reg": D0, "ot": D0, "pto": D0, "total": D0, "otemps": set()})
for day in spine:
    for v in dim:
        if v["eff_start_date"] <= day <= v["eff_end_date"] and v["hire_date"] <= day and (v["term_date"] == "" or v["term_date"] > day):
            f = fact[(day, v["dept_id"])]
            f["hc"].add(v["emp_id"])
            h = hrs.get((v["emp_id"], day))
            if h:
                for k in ("reg", "ot", "pto", "total"):
                    f[k] += h[k]
                if h["ot"] > 0:
                    f["otemps"].add(v["emp_id"])
rows = []
for (day, dept), f in fact.items():
    dp = depts.get(dept)
    rows.append({"work_date": day, "dept_id": dept, "dept_name": dp["dept_name"] if dp else "",
                 "cost_center": dp["cost_center"] if dp else "", "headcount": len(f["hc"]),
                 "reg_hours": q2(f["reg"]), "ot_hours": q2(f["ot"]), "pto_hours": q2(f["pto"]),
                 "total_hours": q2(f["total"]),
                 "ot_pct": q2(f["ot"] * 100 / f["total"]) if f["total"] > 0 else "0.00",
                 "employees_with_ot": len(f["otemps"])})
write("emp_metrics_daily", "fct_emp_metrics_daily",
      ["work_date", "dept_id", "dept_name", "cost_center", "headcount", "reg_hours", "ot_hours",
       "pto_hours", "total_hours", "ot_pct", "employees_with_ot"], rows)

# ---------------- payroll_join ----------------
P_START, P_END = "2024-03-11", "2024-03-15"
tc = clean_timecards(tcs_raw, P_START, P_END)
cur = latest_version(emps, P_END)
by_emp = rollup(tc, lambda r: r["emp_id"])
emp_rows = []
for emp_id, h in by_emp.items():
    v = cur.get(emp_id)
    if not v or v["pay_type"] != "HOURLY" or v["dept_id"] not in depts:
        continue
    dp = depts[v["dept_id"]]
    rate = Decimal(v["hourly_rate"])
    gross = (h["reg"] + h["pto"]) * rate + h["ot"] * rate * Decimal("1.5")
    emp_rows.append({"pay_period_start": P_START, "pay_period_end": P_END, "emp_id": emp_id,
                     "full_name": v["first_name"].strip() + " " + v["last_name"].strip(),
                     "dept_id": v["dept_id"], "dept_name": dp["dept_name"], "cost_center": dp["cost_center"],
                     "region": dp["region"], "hourly_rate": q2(rate), "reg_hours": q2(h["reg"]),
                     "ot_hours": q2(h["ot"]), "pto_hours": q2(h["pto"]), "total_hours": q2(h["total"]),
                     "gross_pay": q2(gross), "ot_flag": "Y" if h["ot"] > 0 else "N"})
write("payroll_join", "payroll_by_employee",
      ["pay_period_start", "pay_period_end", "emp_id", "full_name", "dept_id", "dept_name", "cost_center",
       "hourly_rate", "reg_hours", "ot_hours", "pto_hours", "total_hours", "gross_pay", "ot_flag"], emp_rows)
cc = defaultdict(lambda: {"n": 0, "total": D0, "ot": D0, "gross": D0})
for r in emp_rows:
    a = cc[(r["cost_center"], r["region"])]
    a["n"] += 1
    a["total"] += Decimal(r["total_hours"])
    a["ot"] += Decimal(r["ot_hours"])
    a["gross"] += Decimal(r["gross_pay"])
write("payroll_join", "payroll_by_cost_center",
      ["pay_period_start", "pay_period_end", "cost_center", "region", "employee_count", "total_hours", "ot_hours", "gross_pay"],
      [{"pay_period_start": P_START, "pay_period_end": P_END, "cost_center": k[0], "region": k[1],
        "employee_count": a["n"], "total_hours": q2(a["total"]), "ot_hours": q2(a["ot"]), "gross_pay": q2(a["gross"])}
       for k, a in cc.items()])

# ---------------- turnover_snapshot ----------------
cur = latest_version(emps, "2024-03-31")
rows = []
for month, s, e in [("2024-01", "2024-01-01", "2024-01-31"), ("2024-02", "2024-02-01", "2024-02-29"),
                    ("2024-03", "2024-03-01", "2024-03-31")]:
    agg = defaultdict(lambda: [0, 0, 0, 0, 0])
    for v in cur.values():
        if v["dept_id"] not in depts:
            continue
        a = agg[v["dept_id"]]
        t = v["term_date"]
        a[0] += 1 if v["hire_date"] <= s and (t == "" or t >= s) else 0
        a[1] += 1 if v["hire_date"] <= e and (t == "" or t >= e) else 0
        a[2] += 1 if s <= v["hire_date"] <= e else 0
        a[3] += 1 if t != "" and s <= t <= e else 0
        a[4] += 1 if t != "" and s <= t <= e and v["term_reason"] == "VOLUNTARY" else 0
    for dept, a in agg.items():
        if sum(a[:4]) == 0:
            continue
        avg = Decimal(a[0] + a[1]) / 2
        dp = depts[dept]
        rows.append({"snapshot_month": month, "dept_id": dept, "dept_name": dp["dept_name"], "region": dp["region"],
                     "headcount_start": a[0], "headcount_end": a[1], "hires": a[2], "terminations": a[3],
                     "voluntary_terminations": a[4],
                     "turnover_rate_pct": q2(Decimal(a[3]) * 100 / avg) if avg > 0 else "0.00"})
write("turnover_snapshot", "turnover_snapshot",
      ["snapshot_month", "dept_id", "dept_name", "region", "headcount_start", "headcount_end", "hires",
       "terminations", "voluntary_terminations", "turnover_rate_pct"], rows)

# ---------------- cohort_tagger ----------------
AS_OF = "2024-03-15"
tc = clean_timecards(tcs_raw, "2024-03-11", "2024-03-15")
ot_by_emp = rollup(tc, lambda r: r["emp_id"])
cur = latest_version(emps, AS_OF)
rows = []
a = dt.date.fromisoformat(AS_OF)
for emp_id, v in cur.items():
    if v["term_date"] != "" and v["term_date"] <= AS_OF:
        continue
    h = dt.date.fromisoformat(v["hire_date"])
    years = a.year - h.year - (1 if (a.month, a.day) < (h.month, h.day) else 0)
    band = "LT1Y" if years < 1 else "1TO3Y" if years < 3 else "3TO5Y" if years < 5 else "5YPLUS"
    fy = h.year + 1 if h.month >= 7 else h.year
    fq = {7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 12: 2, 1: 3, 2: 3, 3: 3, 4: 4, 5: 4, 6: 4}[h.month]
    cohort = "FY%02d-Q%d" % (fy % 100, fq)
    ot = ot_by_emp[emp_id]["ot"] if emp_id in ot_by_emp else D0
    seg = "EXEMPT" if v["pay_type"] == "SALARY" else "HIGH_OT" if ot >= 8 else "SOME_OT" if ot > 0 else "NO_OT"
    rows.append({"emp_id": emp_id, "dept_id": v["dept_id"], "pay_type": v["pay_type"], "hire_date": v["hire_date"],
                 "tenure_years": years, "tenure_band": band, "hire_cohort": cohort, "ot_hours": q2(ot),
                 "ot_segment": seg, "cohort_tag": "%s_%s_%s" % (cohort, band, seg)})
write("cohort_tagger", "employee_cohorts",
      ["emp_id", "dept_id", "pay_type", "hire_date", "tenure_years", "tenure_band", "hire_cohort", "ot_hours",
       "ot_segment", "cohort_tag"], rows)
