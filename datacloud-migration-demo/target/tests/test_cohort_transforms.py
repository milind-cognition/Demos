import datetime as dt
from decimal import Decimal

from pyspark.sql import functions as F

from target.lib import cohort_transforms as cohort


def test_active_on_day_excludes_termination_day_without_filtering_hire_date(spark):
    rows = [
        ("blank", "", "2024-04-01"),
        ("null", None, "2020-01-01"),
        ("before", "2024-03-14", "2020-01-01"),
        ("on", "2024-03-15", "2020-01-01"),
        ("after", "2024-03-16", "2020-01-01"),
    ]
    df = spark.createDataFrame(rows, "emp_id string, term_date string, hire_date string")
    active = df.filter(cohort.active_on_day(dt.date(2024, 3, 15)))
    assert sorted(r.emp_id for r in active.collect()) == ["after", "blank", "null"]


def test_completed_anniversaries_and_tenure_band_boundaries(spark):
    rows = [
        ("2024-03-16", -1, "LT1Y"),
        ("2023-03-16", 0, "LT1Y"),
        ("2023-03-15", 1, "1TO3Y"),
        ("2021-03-16", 2, "1TO3Y"),
        ("2021-03-15", 3, "3TO5Y"),
        ("2019-03-16", 4, "3TO5Y"),
        ("2019-03-15", 5, "5YPLUS"),
        ("2010-03-14", 14, "5YPLUS"),
    ]
    df = spark.createDataFrame(rows, "hire_date string, expected_years int, expected_band string")
    actual = df.withColumn("years", cohort.full_years_between(F.to_date("hire_date"), dt.date(2024, 3, 15)))
    actual = actual.withColumn("band", cohort.tenure_band(F.col("years")))
    assert all((r.years, r.band) == (r.expected_years, r.expected_band) for r in actual.collect())


def test_leap_day_anniversary_matches_java_month_day_comparison(spark):
    df = spark.createDataFrame([("2020-02-29",)], ["hire_date"])
    hire = F.to_date("hire_date")
    years = df.select(
        cohort.full_years_between(hire, dt.date(2023, 2, 28)).alias("before"),
        cohort.full_years_between(hire, dt.date(2023, 3, 1)).alias("after"),
        cohort.full_years_between(hire, dt.date(2024, 2, 29)).alias("on"),
    ).first()
    assert (years.before, years.after, years.on) == (2, 3, 4)


def test_fiscal_cohort_quarter_boundaries_and_two_digit_year(spark):
    rows = [
        ("2023-06-30", "FY23-Q4"),
        ("2023-07-01", "FY24-Q1"),
        ("2023-09-30", "FY24-Q1"),
        ("2023-10-01", "FY24-Q2"),
        ("2023-12-31", "FY24-Q2"),
        ("2024-01-01", "FY24-Q3"),
        ("2024-03-31", "FY24-Q3"),
        ("2024-04-01", "FY24-Q4"),
        ("1999-07-01", "FY00-Q1"),
        ("2000-07-01", "FY01-Q1"),
    ]
    df = spark.createDataFrame(rows, ["hire_date", "expected"])
    actual = df.withColumn("cohort", cohort.fiscal_cohort(F.to_date("hire_date")))
    assert all(r.cohort == r.expected for r in actual.collect())


def test_ot_segment_inclusive_threshold_and_salary_precedence(spark):
    rows = [
        ("HOURLY", Decimal("-1.00"), "NO_OT"),
        ("HOURLY", Decimal("0.00"), "NO_OT"),
        ("HOURLY", Decimal("0.01"), "SOME_OT"),
        ("HOURLY", Decimal("7.99"), "SOME_OT"),
        ("HOURLY", Decimal("8.00"), "HIGH_OT"),
        ("HOURLY", Decimal("8.01"), "HIGH_OT"),
        ("SALARY", Decimal("0.00"), "EXEMPT"),
        ("SALARY", Decimal("8.00"), "EXEMPT"),
        ("OTHER", Decimal("8.00"), "HIGH_OT"),
    ]
    df = spark.createDataFrame(rows, "pay_type string, ot_hours decimal(9,2), expected string")
    actual = df.withColumn("segment", cohort.ot_segment(F.col("pay_type"), F.col("ot_hours")))
    assert all(r.segment == r.expected for r in actual.collect())
