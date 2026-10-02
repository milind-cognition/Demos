"""Every migrated job must pass scripts/validate.py (conformance + golden diff)."""
import importlib.util
import os

import pytest

from target.lib import paths

_spec = importlib.util.spec_from_file_location("validate", os.path.join(paths.DEMO_ROOT, "scripts", "validate.py"))
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)

MIGRATED = validate.migrated_jobs()


def test_exemplar_is_present():
    assert "payroll_join" in MIGRATED


@pytest.mark.parametrize("job", MIGRATED)
def test_conformance(job):
    assert validate.check_notebook(job) == []
    assert validate.check_workflow(job) == []


@pytest.mark.parametrize("job", MIGRATED)
def test_golden_diff(job):
    assert validate.validate_job(job, validate.GOLDEN_RUN_DATE, keep=False, verbose=False)


def test_conformance_catches_violations(tmp_path, monkeypatch):
    bad = tmp_path / "nb_bad.py"
    bad.write_text("import os\nfrom pyspark.dbutils import DBUtils\n"
                   "df = spark.sql('SELECT * FROM hr.employees')\nx = '2024-03-15'\n")
    monkeypatch.setattr(paths, "NOTEBOOKS_DIR", str(tmp_path))
    errors = "\n".join(validate.check_notebook("bad"))
    for needle in ("Databricks notebook source", "Databricks-runtime-only import", "SELECT *",
                   "hard-coded date", "missing required widget 'run_date'", "dbutils shim"):
        assert needle in errors
