#!/usr/bin/env python3
"""Validate a migrated job against the legacy golden outputs.

    python scripts/validate.py payroll_join            # one job
    python scripts/validate.py --all                   # every job that has a notebook
    python scripts/validate.py --list                  # migration status of every legacy job

For each job this runs two gates (see VALIDATION.md):

1. Conformance -- static checks of target/notebooks/nb_<job>.py and target/workflows/<job>.json
   against target/MIGRATION_STANDARDS.md (format header, no SELECT *, no Databricks-only imports,
   no magic dates, required widgets, workflow structure).
2. Data diff -- executes the notebook on local PySpark against legacy/sample_data/ into a fresh
   scratch directory and compares every CSV with legacy/expected_outputs/<job>/ (header exact,
   rows exact as sorted multisets).

Exit code 0 only if every requested job passes both gates.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

DEMO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, DEMO_ROOT)

from target.lib import paths, validation  # noqa: E402

GOLDEN_RUN_DATE = "2024-03-15"
NOTEBOOK_HEADER = "# Databricks notebook source"
REQUIRED_WIDGETS = ("run_date", "input_root", "output_root", "validate")
FORBIDDEN_IMPORTS = re.compile(
    r"^\s*(from|import)\s+(pyspark\.dbutils|databricks(\.|\s|$)|dbruntime|delta(\.|\s|$)|"
    r"dlt(\s|$)|pyspark\.databricks)",
    re.M,
)
SELECT_STAR = re.compile(r"select\s+(distinct\s+)?(\w+\.)?\*", re.I)
SPARK_SELECT_STAR = re.compile(r"""\.select\(\s*["']\*["']\s*\)""")
ISO_DATE = re.compile(r"""["']\d{4}-\d{2}-\d{2}["']""")
WIDGET_DEFAULT = re.compile(r"dbutils\.widgets\.(text|dropdown)\(")


def legacy_jobs():
    return sorted(d for d in os.listdir(paths.EXPECTED_OUTPUTS_DIR)
                  if os.path.isdir(os.path.join(paths.EXPECTED_OUTPUTS_DIR, d)))


def migrated_jobs():
    return sorted(f[3:-3] for f in os.listdir(paths.NOTEBOOKS_DIR) if re.match(r"nb_\w+\.py$", f))


def check_notebook(job):
    errors = []
    nb = paths.notebook_path(job)
    if not os.path.exists(nb):
        return ["missing notebook %s" % os.path.relpath(nb, DEMO_ROOT)]
    src = open(nb).read()
    lines = src.splitlines()
    if not lines or lines[0].strip() != NOTEBOOK_HEADER:
        errors.append("first line must be '%s'" % NOTEBOOK_HEADER)
    if "# COMMAND ----------" not in src:
        errors.append("no '# COMMAND ----------' cell separators (Databricks source format)")
    for m in FORBIDDEN_IMPORTS.finditer(src):
        errors.append("Databricks-runtime-only import: %s" % m.group(0).strip())
    for i, line in enumerate(lines, 1):
        code = line.split("#", 1)[0] if not line.lstrip().startswith("# MAGIC") else ""
        if SELECT_STAR.search(code) or SPARK_SELECT_STAR.search(code):
            errors.append("line %d: SELECT * is forbidden -- project explicit columns" % i)
        if ISO_DATE.search(code) and not WIDGET_DEFAULT.search(line):
            errors.append("line %d: hard-coded date literal -- derive from a widget via target.lib.dates" % i)
    for w in REQUIRED_WIDGETS:
        if not re.search(r"dbutils\.widgets\.(text|dropdown)\(\s*[\"']%s[\"']" % w, src):
            errors.append("missing required widget '%s'" % w)
    if "from target.lib.dbutils_shim import dbutils" not in src:
        errors.append("must bind the local dbutils shim (MIGRATION_STANDARDS.md section 4)")
    if "validation.compare_job" not in src:
        errors.append("--validate mode must call target.lib.validation.compare_job")
    return errors


def check_workflow(job):
    wf = paths.workflow_path(job)
    if not os.path.exists(wf):
        return ["missing workflow %s" % os.path.relpath(wf, DEMO_ROOT)]
    try:
        spec = json.load(open(wf))
    except ValueError as exc:
        return ["workflow is not valid JSON: %s" % exc]
    errors = []
    for key in ("name", "tags", "job_clusters", "tasks", "email_notifications", "max_concurrent_runs"):
        if key not in spec:
            errors.append("workflow missing top-level '%s'" % key)
    if not spec.get("name", "").startswith("hr_daily."):
        errors.append("workflow name must be 'hr_daily.<job>'")
    clusters = {}
    for c in spec.get("job_clusters", []):
        nc = c.get("new_cluster", {})
        clusters[c.get("job_cluster_key")] = nc
        for key in ("spark_version", "node_type_id", "data_security_mode"):
            if key not in nc:
                errors.append("job_cluster '%s' missing new_cluster.%s" % (c.get("job_cluster_key"), key))
        if "num_workers" not in nc and "autoscale" not in nc:
            errors.append("job_cluster '%s' needs num_workers or autoscale" % c.get("job_cluster_key"))
    nb_suffix = "target/notebooks/nb_%s" % job
    found_nb = False
    for t in spec.get("tasks", []):
        key = t.get("task_key", "?")
        if t.get("job_cluster_key") not in clusters:
            errors.append("task '%s' references undefined job_cluster_key %r" % (key, t.get("job_cluster_key")))
        nt = t.get("notebook_task")
        if nt:
            if nt.get("notebook_path", "").endswith(nb_suffix):
                found_nb = True
            if nt.get("notebook_path", "").endswith(".py"):
                errors.append("task '%s': notebook_path must omit the .py extension" % key)
            if "run_date" not in nt.get("base_parameters", {}):
                errors.append("task '%s': base_parameters must pass run_date" % key)
        for k in ("timeout_seconds", "max_retries"):
            if k not in t:
                errors.append("task '%s' missing %s" % (key, k))
    if not found_nb:
        errors.append("no notebook_task points at .../%s" % nb_suffix)
    return errors


def run_notebook(job, out_root, run_date):
    cmd = [sys.executable, paths.notebook_path(job), "--run_date=%s" % run_date,
           "--input_root=%s" % paths.SAMPLE_DATA_DIR, "--output_root=%s" % out_root,
           "--output_sink=csv", "--validate=false"]
    env = dict(os.environ, SPARK_LOCAL_IP=os.environ.get("SPARK_LOCAL_IP", "127.0.0.1"))
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=DEMO_ROOT, env=env, capture_output=True, text=True)
    return proc, time.time() - t0


def validate_job(job, run_date, keep, verbose):
    print("=== %s" % job)
    ok = True
    if not os.path.isdir(paths.expected_dir(job)):
        print("[FAIL] no golden outputs under legacy/expected_outputs/%s" % job)
        return False
    conf = check_notebook(job) + check_workflow(job)
    for e in conf:
        print("[FAIL] conformance: %s" % e)
    if not conf:
        print("[PASS] conformance: notebook + workflow follow MIGRATION_STANDARDS.md")
    ok = ok and not conf
    if not os.path.exists(paths.notebook_path(job)):
        return False
    out_root = tempfile.mkdtemp(prefix="hrdp_validate_%s_" % job)
    try:
        proc, secs = run_notebook(job, out_root, run_date)
        if verbose or proc.returncode != 0:
            sys.stdout.write(proc.stdout)
            sys.stdout.write(proc.stderr[-4000:])
        if proc.returncode != 0:
            print("[FAIL] notebook exited %d after %.1fs" % (proc.returncode, secs))
            return False
        print("[PASS] notebook ran on local PySpark in %.1fs (run_date=%s)" % (secs, run_date))
        results = validation.compare_job(paths.job_output_dir(out_root, job), paths.expected_dir(job))
        print(validation.format_report(job, results))
        ok = ok and validation.all_match(results)
    finally:
        if keep:
            print("outputs kept in %s" % out_root)
        else:
            shutil.rmtree(out_root, ignore_errors=True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", nargs="?", help="job name, e.g. payroll_join (= legacy/expected_outputs/<job>)")
    ap.add_argument("--all", action="store_true", help="validate every job that has a notebook")
    ap.add_argument("--list", action="store_true", help="show migration status per legacy job")
    ap.add_argument("--run-date", default=GOLDEN_RUN_DATE, help="must match the golden run (default %(default)s)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch output directory")
    ap.add_argument("-v", "--verbose", action="store_true", help="echo notebook stdout/stderr")
    args = ap.parse_args(argv)

    if args.list:
        for job in legacy_jobs():
            nb = "notebook" if os.path.exists(paths.notebook_path(job)) else "-"
            wf = "workflow" if os.path.exists(paths.workflow_path(job)) else "-"
            print("%-20s %-9s %-9s" % (job, nb, wf))
        return 0
    jobs = migrated_jobs() if args.all else [args.job] if args.job else None
    if not jobs:
        ap.error("give a job name, --all or --list")
    results = {job: validate_job(job, args.run_date, args.keep, args.verbose) for job in jobs}
    print("\nSUMMARY")
    for job, ok in results.items():
        print("  %-20s %s" % (job, "PASS" if ok else "FAIL"))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
