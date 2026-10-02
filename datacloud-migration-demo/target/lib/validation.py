"""Golden-file comparison used by ``--validate`` mode and scripts/validate.py.

Rule (VALIDATION.md): header must match exactly (names and order); data rows are compared as
multisets of exact strings after sorting -- no tolerance, no trimming, no type coercion.
"""
import csv
import glob
import os
from collections import Counter

MAX_SAMPLE = 10


def read_csv_rows(path):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise ValueError("%s is empty (no header)" % path)
    return rows[0], [tuple(r) for r in rows[1:]]


def compare_csv(actual_path, expected_path):
    """Return a dict describing the diff; ``result["match"]`` is True iff identical."""
    res = {"dataset": os.path.basename(expected_path), "actual": actual_path, "expected": expected_path}
    if not os.path.exists(actual_path):
        res.update(match=False, reason="missing actual output")
        return res
    a_hdr, a_rows = read_csv_rows(actual_path)
    e_hdr, e_rows = read_csv_rows(expected_path)
    res.update(actual_rows=len(a_rows), expected_rows=len(e_rows))
    if a_hdr != e_hdr:
        res.update(match=False, reason="header mismatch", actual_header=a_hdr, expected_header=e_hdr)
        return res
    a_cnt, e_cnt = Counter(a_rows), Counter(e_rows)
    missing = sorted((e_cnt - a_cnt).elements())
    unexpected = sorted((a_cnt - e_cnt).elements())
    res.update(
        match=not missing and not unexpected,
        reason="" if not missing and not unexpected else "row mismatch",
        header=e_hdr,
        missing_count=len(missing),
        unexpected_count=len(unexpected),
        missing_sample=missing[:MAX_SAMPLE],
        unexpected_sample=unexpected[:MAX_SAMPLE],
    )
    return res


def compare_job(actual_dir, expected_dir):
    """Compare every golden CSV for a job; extra actual CSVs are reported as failures too."""
    expected = sorted(glob.glob(os.path.join(expected_dir, "*.csv")))
    if not expected:
        raise FileNotFoundError("no golden CSVs under %s" % expected_dir)
    results = [compare_csv(os.path.join(actual_dir, os.path.basename(p)), p) for p in expected]
    names = {os.path.basename(p) for p in expected}
    for extra in sorted(glob.glob(os.path.join(actual_dir, "*.csv"))):
        if os.path.basename(extra) not in names:
            results.append({"dataset": os.path.basename(extra), "actual": extra, "expected": None,
                            "match": False, "reason": "unexpected output dataset (no golden file)"})
    return results


def format_report(job, results):
    lines = []
    for r in results:
        status = "PASS" if r["match"] else "FAIL"
        counts = ""
        if "actual_rows" in r:
            counts = " rows actual=%d expected=%d" % (r["actual_rows"], r["expected_rows"])
        detail = "" if r["match"] else " -- " + r["reason"]
        lines.append("[%s] %s/%s%s%s" % (status, job, r["dataset"], counts, detail))
        if r.get("reason") == "header mismatch":
            lines.append("    expected header: %s" % ",".join(r["expected_header"]))
            lines.append("    actual header:   %s" % ",".join(r["actual_header"]))
        for label, key in (("missing (in golden, not produced)", "missing_sample"),
                           ("unexpected (produced, not in golden)", "unexpected_sample")):
            if r.get(key):
                lines.append("    %s: %d" % (label, r[key.replace("_sample", "_count")]))
                for row in r[key]:
                    lines.append("      " + ",".join(row))
    return "\n".join(lines)


def all_match(results):
    return all(r["match"] for r in results)
