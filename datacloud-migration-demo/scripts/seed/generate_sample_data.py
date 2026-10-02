#!/usr/bin/env python3
"""Regenerate the checked-in HR seed extracts under legacy/sample_data/.

The CSVs are committed and are the source of truth; this script only exists so
the extracts are reproducible. Output is byte-for-byte deterministic (fixed seed,
stdlib only). Re-running it must produce no git diff.

    python scripts/seed/generate_sample_data.py
"""
import csv
import datetime as dt
import os
import random

SEED = 20240315
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(ROOT, "legacy", "sample_data")

DEPT_NAMES = [
    "Payroll Operations", "Tax Filing Services", "Benefits Administration", "Client Onboarding",
    "Implementation East", "Implementation West", "Customer Care Tier 1", "Customer Care Tier 2",
    "Workforce Analytics", "Time and Attendance", "HR Business Partners", "Talent Acquisition",
    "Learning and Development", "Compensation", "Retirement Services", "Garnishment Processing",
    "Money Movement", "Treasury Operations", "General Ledger", "Accounts Payable",
    "Accounts Receivable", "Financial Planning", "Internal Audit", "Compliance Office",
    "Data Privacy", "Security Operations", "Platform Engineering", "Data Engineering",
    "Mobile Engineering", "QA Automation", "Release Management", "Site Reliability",
    "Product Management Core", "Product Management SMB", "UX Research", "Technical Writing",
    "Sales Ops NA", "Sales Ops EMEA", "Partner Channel", "Marketing Ops",
    "Field Services North", "Field Services South", "Print and Mail", "Document Imaging",
    "Facilities", "Procurement", "Legal Operations", "Executive Office",
    "Legacy Mainframe Support", "PEO Integration",
]
REGIONS = ["NA-EAST", "NA-WEST", "NA-CENTRAL", "EMEA", "APAC"]
DIVISIONS = ["OPERATIONS", "FINANCE", "TECHNOLOGY", "GO-TO-MARKET", "CORPORATE"]
FIRST = [
    "James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Jennifer", "William",
    "Elizabeth", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Carlos", "Karen",
    "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Priya", "Mark", "Aisha", "Steven", "Emily",
    "Andrew", "Mei", "Kevin", "Olga", "Brian", "Fatima", "George", "Sofia", "Edward", "Hannah",
    "Ravi", "Grace", "Luis", "Chloe", "Omar", "Ingrid", "Kenji", "Amara", "Diego", "Leah",
]
LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
    "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor",
    "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez",
    "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
    "Scott", "Torres", "Nguyen", "Hill", "Flores", "Patel", "Kowalski", "O'Brien", "Tanaka",
    "Okafor", "Schmidt", "Rossi", "Haddad",
]
HOURLY_TITLES = [
    "Payroll Specialist", "Customer Service Associate", "Implementation Analyst",
    "Data Entry Clerk", "Benefits Coordinator", "Field Technician", "Mailroom Associate",
]
SALARY_TITLES = ["Software Engineer", "HR Business Partner", "Finance Manager", "Product Manager"]
LOCATIONS = ["ROSELAND-NJ", "ALPHARETTA-GA", "PASADENA-CA", "EL-PASO-TX", "PARIS-FR", "HYDERABAD-IN"]

EMP_COLS = [
    "emp_id", "first_name", "last_name", "dept_id", "job_title", "employment_type", "pay_type",
    "hourly_rate", "hire_date", "term_date", "term_reason", "location", "manager_id",
    "effective_date", "record_source",
]
TC_COLS = [
    "timecard_id", "emp_id", "work_date", "pay_code", "hours", "approved_flag", "submitted_ts",
    "source_system",
]
DEPT_COLS = ["dept_id", "dept_name", "cost_center", "division", "region", "is_active"]


def d(s):
    return dt.date.fromisoformat(s)


def rand_date(rng, start, end):
    span = (d(end) - d(start)).days
    return (d(start) + dt.timedelta(days=rng.randint(0, span))).isoformat()


def build_departments(rng):
    rows = []
    for i, name in enumerate(DEPT_NAMES):
        dept_id = "D%d" % (101 + i)
        rows.append({
            "dept_id": dept_id,
            "dept_name": name,
            "cost_center": "CC-%04d" % (4100 + i * 7),
            "division": DIVISIONS[i % len(DIVISIONS)],
            "region": REGIONS[(i * 3) % len(REGIONS)],
            "is_active": "N" if dept_id in ("D149", "D150") else "Y",
        })
    return rows


def build_employees(rng):
    base = {}
    for i in range(1, 121):
        emp_id = "E%d" % (10000 + i)
        hourly = (i % 10) < 7
        if i >= 113:
            hire = [
                "2024-01-08", "2024-01-22", "2024-02-05", "2024-02-19",
                "2024-03-01", "2024-03-04", "2024-03-11", "2024-03-18",
            ][i - 113]
        elif i >= 105:
            hire = rand_date(rng, "2023-04-01", "2023-12-31")
        else:
            hire = rand_date(rng, "2012-01-01", "2022-12-31")
        if hourly:
            emp_type = "TEMP" if i % 13 == 0 else ("PT" if i % 7 == 0 else "FT")
            rate = "%.2f" % (rng.randint(64, 168) * 0.25)
            title = HOURLY_TITLES[rng.randrange(len(HOURLY_TITLES))]
        else:
            emp_type = "FT"
            rate = "%.2f" % (rng.randint(152, 340) * 0.25)
            title = SALARY_TITLES[rng.randrange(len(SALARY_TITLES))]
        first = FIRST[rng.randrange(len(FIRST))]
        last = LAST[rng.randrange(len(LAST))]
        if i % 17 == 0:
            first = first + " "
        if i % 23 == 0:
            last = " " + last
        dept = "D%d" % (101 + rng.randrange(50))
        if emp_id == "E10076":
            dept = "D999"
        base[emp_id] = {
            "emp_id": emp_id,
            "first_name": first,
            "last_name": last,
            "dept_id": dept,
            "job_title": title,
            "employment_type": emp_type,
            "pay_type": "HOURLY" if hourly else "SALARY",
            "hourly_rate": rate,
            "hire_date": hire,
            "term_date": "",
            "term_reason": "",
            "location": LOCATIONS[rng.randrange(len(LOCATIONS))],
            "manager_id": "" if i <= 5 else "E%d" % (10000 + rng.randint(1, 5)),
            "effective_date": hire,
            "record_source": "PEOPLESOFT_LEGACY" if hire < "2016-01-01" else "WORKDAY_EXTRACT",
        }

    # (emp_id, effective_date, change)
    events = [
        # department transfers
        ("E10003", "2023-02-01", {"dept_id": "D112"}),
        ("E10014", "2023-05-15", {"dept_id": "D127"}),
        ("E10021", "2023-07-01", {"dept_id": "D104"}),
        ("E10033", "2023-09-18", {"dept_id": "D141"}),
        ("E10046", "2023-11-06", {"dept_id": "D118"}),
        ("E10052", "2023-12-04", {"dept_id": "D133"}),
        ("E10060", "2024-02-15", {"dept_id": "D109"}),
        ("E10002", "2024-03-13", {"dept_id": "D131"}),
        ("E10011", "2024-03-13", {"dept_id": "D101"}),
        ("E10024", "2024-03-13", {"dept_id": "D145"}),
        # rate changes
        ("E10001", "2024-01-01", {"hourly_rate": "+1.25"}),
        ("E10012", "2024-01-01", {"hourly_rate": "+0.75"}),
        ("E10030", "2024-01-01", {"hourly_rate": "+2.00"}),
        ("E10041", "2024-01-01", {"hourly_rate": "+1.50"}),
        ("E10004", "2024-03-11", {"hourly_rate": "+1.00"}),
        ("E10013", "2024-03-11", {"hourly_rate": "+0.50"}),
        ("E10006", "2024-04-01", {"hourly_rate": "+3.00"}),
        ("E10020", "2024-04-01", {"hourly_rate": "+2.25"}),
        # terminations, 2023
        ("E10055", "2023-03-31", {"term_reason": "VOLUNTARY"}),
        ("E10068", "2023-08-11", {"term_reason": "INVOLUNTARY"}),
        ("E10081", "2023-10-27", {"term_reason": "RETIREMENT"}),
        # terminations, Q1 2024
        ("E10015", "2024-01-12", {"term_reason": "VOLUNTARY"}),
        ("E10027", "2024-01-31", {"term_reason": "INVOLUNTARY"}),
        ("E10038", "2024-02-02", {"term_reason": "VOLUNTARY"}),
        ("E10049", "2024-02-16", {"term_reason": "RETIREMENT"}),
        ("E10057", "2024-02-29", {"term_reason": "VOLUNTARY"}),
        ("E10063", "2024-03-01", {"term_reason": "VOLUNTARY"}),
        ("E10071", "2024-03-08", {"term_reason": "INVOLUNTARY"}),
        ("E10005", "2024-03-13", {"term_reason": "VOLUNTARY"}),
        ("E10022", "2024-03-15", {"term_reason": "INVOLUNTARY"}),
        ("E10085", "2024-03-22", {"term_reason": "VOLUNTARY"}),
        ("E10092", "2024-03-29", {"term_reason": "VOLUNTARY"}),
        ("E10114", "2024-03-27", {"term_reason": "VOLUNTARY"}),
        # future-dated termination (after every legacy as-of date)
        ("E10008", "2024-04-05", {"term_reason": "VOLUNTARY"}),
    ]
    events.sort(key=lambda e: (e[0], e[1]))
    rows = []
    current = {k: dict(v) for k, v in base.items()}
    for emp_id in sorted(base):
        rows.append(dict(base[emp_id]))
    for emp_id, eff, change in events:
        row = dict(current[emp_id])
        for k, v in change.items():
            if k == "hourly_rate":
                row[k] = "%.2f" % (float(row[k]) + float(v))
            else:
                row[k] = v
        if "term_reason" in change:
            row["term_date"] = eff
        row["effective_date"] = eff
        row["record_source"] = "WORKDAY_EXTRACT"
        current[emp_id] = row
        rows.append(row)
    # extract glitch: two rows delivered twice
    rows.append(dict(base["E10009"]))
    rows.append(dict(current["E10042"]))
    rng.shuffle(rows)
    return rows


def build_timecards(rng, employees):
    def version_on(emp_id, day):
        vs = [r for r in employees if r["emp_id"] == emp_id and r["effective_date"] <= day]
        return max(vs, key=lambda r: r["effective_date"]) if vs else None

    week = ["2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14", "2024-03-15"]
    special = ["E10002", "E10004", "E10005", "E10011", "E10013", "E10022", "E10024", "E10076"]
    pool = []
    for r in sorted(employees, key=lambda r: r["emp_id"]):
        v = version_on(r["emp_id"], "2024-03-11")
        if (v and v["pay_type"] == "HOURLY" and not v["term_date"]
                and r["emp_id"] not in special and r["emp_id"] not in pool):
            pool.append(r["emp_id"])
    crew = special + pool[: 30 - len(special)]
    crew.append("E10019")  # salaried employee who logs PTO in the time system

    rows = []
    seq = [0]

    def add(emp_id, day, code, hours, approved="Y", ts=None, tc_id=None, source=None):
        if tc_id is None:
            seq[0] += 1
            tc_id = "TC%07d" % (2403000 + seq[0])
        y, m, dd = day.split("-")
        if ts is None:
            ts = "%s 17:%02d:%02d" % (day, rng.randint(0, 59), rng.randint(0, 59))
        rows.append({
            "timecard_id": tc_id,
            "emp_id": emp_id,
            "work_date": "%s/%s/%s" % (m, dd, y),
            "pay_code": code,
            "hours": hours,
            "approved_flag": approved,
            "submitted_ts": ts,
            "source_system": source or ("ADP_WFN" if int(emp_id[1:]) % 4 == 0 else "KRONOS"),
        })
        return rows[-1]

    dt_budget = 3
    for emp_id in crew:
        for day in week:
            v = version_on(emp_id, day)
            if emp_id == "E10019":
                if day == "2024-03-14":
                    add(emp_id, day, "PTO", "8.0")
                continue
            if v["term_date"] and v["term_date"] <= day:
                if emp_id == "E10005" and day == "2024-03-14":
                    add(emp_id, day, "REG", "8.0")  # keyed after termination
                continue
            reg = "4.0" if v["employment_type"] == "PT" else "8.0"
            roll = rng.random()
            if roll < 0.05:
                add(emp_id, day, "PTO", reg)
                continue
            add(emp_id, day, "REG", reg)
            roll = rng.random()
            if roll < 0.12:
                add(emp_id, day, "OT", rng.choice(["1.0", "1.5", "2.0", "2.5", "3.0", "4.0"]))
            elif roll < 0.14 and dt_budget > 0:
                dt_budget -= 1
                add(emp_id, day, "DT", "2.0")

    # jury duty replaces a regular shift
    for r in rows:
        if r["emp_id"] in ("E10031", "E10043") and r["work_date"] == "03/12/2024" and r["pay_code"] == "REG":
            r["pay_code"] = "JURY"
    # guarantee OT for the mid-week transfer so the Type-2 split is visible
    add("E10002", "2024-03-12", "OT", "2.5")
    add("E10002", "2024-03-14", "OT", "3.0")
    add("E10011", "2024-03-15", "DT", "2.0")

    # corrected resubmissions: same timecard_id, later submitted_ts, new hours
    corrections = []
    for r in rows:
        if r["pay_code"] in ("REG", "OT") and len(corrections) < 6 and int(r["timecard_id"][2:]) % 9 == 0:
            corrections.append(r)
    for r in corrections:
        y = r["work_date"][6:]
        m, dd = r["work_date"][:2], r["work_date"][3:5]
        nxt = (d("%s-%s-%s" % (y, m, dd)) + dt.timedelta(days=1)).isoformat()
        new_hours = "7.5" if r["pay_code"] == "REG" else "%.1f" % (float(r["hours"]) + 1.0)
        add(r["emp_id"], "%s-%s-%s" % (y, m, dd), r["pay_code"], new_hours,
            ts="%s 09:%02d:00" % (nxt, rng.randint(0, 59)), tc_id=r["timecard_id"],
            source=r["source_system"])

    # pending approvals
    for emp_id, day in [("E10004", "2024-03-12"), ("E10013", "2024-03-13"), ("E10024", "2024-03-14"),
                        ("E10002", "2024-03-15"), ("E10011", "2024-03-11"), ("E10076", "2024-03-13")]:
        add(emp_id, day, "OT", "2.0", approved="N")
    # outside the pay week
    for emp_id, day in [("E10004", "2024-03-08"), ("E10013", "2024-03-08"), ("E10022", "2024-03-08"),
                        ("E10002", "2024-03-18"), ("E10024", "2024-03-18")]:
        add(emp_id, day, "REG", "8.0")
    # employee id not present in the HR extract
    add("E99999", "2024-03-12", "REG", "8.0")
    add("E99999", "2024-03-13", "OT", "1.5")

    # free-text pay codes / number formatting from the KRONOS export
    messy_codes = {"REG": ["reg", "Reg ", " REG"], "OT": [" ot", "Ot", "ot "]}
    n = 0
    for r in rows:
        if r["pay_code"] in messy_codes and int(r["timecard_id"][2:]) % 11 == 0:
            r["pay_code"] = messy_codes[r["pay_code"]][n % 3]
            n += 1
        if r["hours"] == "8.0" and int(r["timecard_id"][2:]) % 13 == 0:
            r["hours"] = "8"
        if r["hours"] == "4.0" and int(r["timecard_id"][2:]) % 5 == 0:
            r["hours"] = "4.00"
    rng.shuffle(rows)
    return rows


def write(name, cols, rows):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    print("wrote %-40s %4d rows" % (os.path.relpath(path, ROOT), len(rows)))


def main():
    rng = random.Random(SEED)
    os.makedirs(OUT_DIR, exist_ok=True)
    depts = build_departments(rng)
    emps = build_employees(rng)
    tcs = build_timecards(rng, emps)
    write("departments.csv", DEPT_COLS, depts)
    write("employees.csv", EMP_COLS, emps)
    write("timecards.csv", TC_COLS, tcs)


if __name__ == "__main__":
    main()
