import csv
import os
import subprocess
import sys

import pytest

from target.lib import io, paths


@pytest.mark.parametrize("active_first", [True, False])
def test_same_date_employee_revisions_match_java(tmp_path, active_first):
    active = dict(emp_id="E1", dept_id="Z99", pay_type="SALARY", hire_date="2019-07-01",
                  effective_date="2024-03-01", term_date="")
    terminated = dict(emp_id="E1", dept_id="A01", pay_type="HOURLY", hire_date="2023-01-01",
                      effective_date="2024-03-01", term_date="2024-03-10")
    first, second = (active, terminated) if active_first else (terminated, active)
    rows = [
        dict(active, effective_date="2023-01-01"),
        first,
        second,
        dict(first),
        dict(second, effective_date="2024-04-01"),
        dict(active, emp_id="E2", effective_date="2023-01-01", dept_id="OLD"),
        dict(active, emp_id="E2", dept_id="CURRENT"),
    ]
    employees = tmp_path / "employees.csv"
    timecards = tmp_path / "timecards.csv"
    for file, dataset, records in [(employees, "employees", rows), (timecards, "timecards", [])]:
        with file.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=io.INPUT_COLUMNS[dataset])
            writer.writeheader()
            writer.writerows(records)

    expected = tmp_path / "java.csv"
    subprocess.run(
        ["java", os.path.join(paths.DEMO_ROOT, "legacy", "java", "CohortTagger.java"),
         str(employees), str(timecards), str(expected)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    subprocess.run(
        [sys.executable, paths.notebook_path("cohort_tagger"), "--run_date", "2024-03-15",
         "--input_root", str(tmp_path), "--output_root", str(tmp_path / "output"), "--output_sink", "csv"],
        check=True, capture_output=True, text=True, timeout=120,
    )
    actual = tmp_path / "output" / "cohort_tagger" / "employee_cohorts.csv"
    with expected.open(newline="") as stream:
        expected_rows = list(csv.reader(stream))
    with actual.open(newline="") as stream:
        actual_rows = list(csv.reader(stream))
    assert actual_rows[0] == expected_rows[0]
    assert sorted(actual_rows[1:]) == sorted(expected_rows[1:])
    assert [row[0] for row in actual_rows[1:]] == (["E1", "E2"] if active_first else ["E2"])
