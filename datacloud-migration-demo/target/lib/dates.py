"""Business-calendar helpers. Replace every legacy magic date with one of these."""
import calendar
import datetime as dt


def pay_week(run_date):
    """Mon..Fri pay week containing ``run_date`` (legacy HR close: 2024-03-15 -> 03-11..03-15)."""
    start = run_date - dt.timedelta(days=run_date.weekday())
    return start, start + dt.timedelta(days=4)


def month_bounds(year, month):
    return dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])


def quarter_end(run_date):
    q_last_month = ((run_date.month - 1) // 3 + 1) * 3
    return month_bounds(run_date.year, q_last_month)[1]


def quarter_months(run_date):
    """[(yyyy-MM, first_day, last_day)] for each month of ``run_date``'s calendar quarter."""
    first = ((run_date.month - 1) // 3) * 3 + 1
    out = []
    for m in range(first, first + 3):
        s, e = month_bounds(run_date.year, m)
        out.append(("%04d-%02d" % (run_date.year, m), s, e))
    return out


def iso(d):
    return d.isoformat()
