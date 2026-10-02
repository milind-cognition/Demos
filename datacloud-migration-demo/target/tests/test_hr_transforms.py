import datetime as dt
from decimal import Decimal

from target.lib import hr_transforms as hr

TC_COLS = ["timecard_id", "emp_id", "work_date", "pay_code", "hours", "approved_flag", "submitted_ts",
           "source_system"]


def test_clean_timecards_dedupes_filters_and_normalises(spark):
    rows = [
        ("T1", "E1", "03/11/2024", "reg", "8", "Y", "2024-03-11 17:00:00", "KRONOS"),
        ("T1", "E1", "03/11/2024", "REG", "7.5", "Y", "2024-03-12 09:00:00", "KRONOS"),  # correction wins
        ("T2", "E1", "03/12/2024", " ot", "2.0", "Y", "2024-03-12 17:00:00", "KRONOS"),
        ("T3", "E1", "03/13/2024", "REG", "8", "N", "2024-03-13 17:00:00", "KRONOS"),  # unapproved
        ("T4", "E1", "03/18/2024", "REG", "8", "Y", "2024-03-18 17:00:00", "KRONOS"),  # outside week
    ]
    out = hr.clean_timecards(spark.createDataFrame(rows, TC_COLS), dt.date(2024, 3, 11), dt.date(2024, 3, 15))
    got = sorted((r.timecard_id, r.pay_code, r.hours) for r in out.collect())
    assert got == [("T1", "REG", Decimal("7.50")), ("T2", "OT", Decimal("2.00"))]


def test_bucket_hours(spark):
    codes = [("REG", "8"), ("OT", "1.5"), ("DT", "1"), ("PTO", "4"), ("HOL", "4"), ("JURY", "2")]
    rows = [("E1", c, Decimal(h)) for c, h in codes]
    df = spark.createDataFrame(rows, "emp_id string, pay_code string, hours decimal(9,2)")
    r = hr.bucket_hours(df, ["emp_id"]).collect()[0]
    assert (r.reg_hours, r.ot_hours, r.pto_hours, r.total_hours) == (
        Decimal("8.00"), Decimal("2.50"), Decimal("8.00"), Decimal("20.50"))


def test_current_employee_version_as_of(spark):
    cols = ["emp_id", "dept_id", "effective_date"]
    rows = [("E1", "D1", "2023-01-01"), ("E1", "D2", "2024-03-01"), ("E1", "D3", "2024-04-01"),
            ("E2", "D1", "2024-02-01"), ("E2", "D1", "2024-02-01")]
    out = hr.current_employee_version(spark.createDataFrame(rows, cols), dt.date(2024, 3, 15))
    assert sorted((r.emp_id, r.dept_id) for r in out.collect()) == [("E1", "D2"), ("E2", "D1")]


def test_round_money_is_half_up(spark):
    df = spark.createDataFrame([(Decimal("1.005"),), (Decimal("2.125"),)], "x decimal(10,3)")
    assert [r.y for r in df.select(hr.round_money(df.x).alias("y")).collect()] == [
        Decimal("1.01"), Decimal("2.13")]


def test_active_on_day_two_legacy_definitions(spark):
    rows = [("E1", "2024-01-01", ""), ("E2", "2024-01-01", "2024-03-15"), ("E3", "2024-01-01", "2024-03-14"),
            ("E4", "2024-03-16", ""), ("E5", "2024-01-01", None)]
    df = spark.createDataFrame(rows, "emp_id string, hire_date string, term_date string")
    day = dt.date(2024, 3, 15)

    def active(term_day_counts):
        return sorted(r.emp_id for r in df.filter(hr.active_on_day(day, term_day_counts)).collect())

    assert active(True) == ["E1", "E2", "E5"]
    assert active(False) == ["E1", "E5"]


def test_dated_between_is_inclusive_and_ignores_blank(spark):
    rows = [("A", "2024-02-01"), ("B", "2024-02-29"), ("C", "2024-03-01"), ("D", ""), ("E", "2024-01-31")]
    df = spark.createDataFrame(rows, "k string, d string")
    out = df.filter(hr.dated_between("d", dt.date(2024, 2, 1), dt.date(2024, 2, 29)))
    assert sorted(r.k for r in out.collect()) == ["A", "B"]
