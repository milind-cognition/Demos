import datetime as dt

from pyspark.sql import functions as F

from target.lib import scd

EMP_COLS = ["emp_id", "dept_id", "hire_date", "term_date", "effective_date"]


def test_scd2_versions_dedupes_windows_and_keys(spark):
    rows = [
        ("E2", "D1", "2023-05-01", "", "2023-05-01"),
        ("E1", "D1", "2020-01-01", "", "2020-01-01"),
        ("E1", "D2", "2020-01-01", "", "2024-03-01"),
        ("E1", "D3", "2020-01-01", "", "2024-04-01"),  # future-dated: excluded
        ("E2", "D1", "2023-05-01", "", "2023-05-01"),  # exact duplicate: collapsed
    ]
    out = scd.scd2_versions(spark.createDataFrame(rows, EMP_COLS), dt.date(2024, 3, 15))
    got = sorted((r.employee_sk, r.emp_id, r.dept_id, r.eff_start_date, r.eff_end_date, r.is_current)
                 for r in out.collect())
    assert got == [
        (1, "E1", "D1", dt.date(2020, 1, 1), dt.date(2024, 2, 29), "N"),
        (2, "E1", "D2", dt.date(2024, 3, 1), scd.OPEN_END_DATE, "Y"),
        (3, "E2", "D1", dt.date(2023, 5, 1), scd.OPEN_END_DATE, "Y"),
    ]


def test_valid_on(spark):
    df = spark.createDataFrame([(dt.date(2024, 3, 1), dt.date(2024, 3, 10))], "eff_start_date date, eff_end_date date")
    days = [dt.date(2024, 2, 29), dt.date(2024, 3, 1), dt.date(2024, 3, 10), dt.date(2024, 3, 11)]
    got = [df.filter(scd.valid_on(F.lit(d))).count() for d in days]
    assert got == [0, 1, 1, 0]


def test_employed_on_both_active_definitions(spark):
    rows = [("A", "2024-01-01", ""), ("B", "2024-01-01", "2024-03-12"), ("C", "2024-03-13", ""),
            ("D", "2024-01-01", "2024-03-11")]
    df = spark.createDataFrame(rows, "emp_id string, hire_date string, term_date string")
    day = F.lit(dt.date(2024, 3, 12))
    strict = sorted(r.emp_id for r in df.filter(scd.employed_on(day)).collect())
    inclusive = sorted(r.emp_id for r in df.filter(scd.employed_on(day, terminated_on_day_is_active=True)).collect())
    assert strict == ["A"]
    assert inclusive == ["A", "B"]
