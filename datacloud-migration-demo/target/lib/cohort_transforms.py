"""Native Spark expressions for employee cohort business rules."""
from pyspark.sql import functions as F


def active_on_day(as_of_date):
    """Cohort/headcount definition: termination on the as-of day is already inactive."""
    term = F.col("term_date")
    return term.isNull() | (term == "") | (F.to_date(term) > F.lit(as_of_date))


def full_years_between(hire_date, as_of_date):
    """Completed anniversaries, comparing month/day even for leap-day hires."""
    as_of = F.lit(as_of_date)
    before_anniversary = F.date_format(as_of, "MMdd") < F.date_format(hire_date, "MMdd")
    return F.year(as_of) - F.year(hire_date) - F.when(before_anniversary, 1).otherwise(0)


def tenure_band(years):
    return (
        F.when(years < 1, "LT1Y")
        .when(years < 3, "1TO3Y")
        .when(years < 5, "3TO5Y")
        .otherwise("5YPLUS")
    )


def fiscal_cohort(hire_date):
    """July-start fiscal year, published as FYyy-Qn."""
    month = F.month(hire_date)
    year = F.year(hire_date) + F.when(month >= 7, 1).otherwise(0)
    quarter = (F.floor(F.pmod(month - 7, F.lit(12)) / 3) + 1).cast("int")
    return F.concat(
        F.lit("FY"), F.lpad(F.pmod(year, F.lit(100)).cast("string"), 2, "0"),
        F.lit("-Q"), quarter.cast("string"),
    )


def ot_segment(pay_type, ot_hours):
    return (
        F.when(pay_type == "SALARY", "EXEMPT")
        .when(ot_hours >= 8, "HIGH_OT")
        .when(ot_hours > 0, "SOME_OT")
        .otherwise("NO_OT")
    )
