import datetime as dt

from target.lib import dates


def test_pay_week_matches_legacy_march_close():
    assert dates.pay_week(dt.date(2024, 3, 15)) == (dt.date(2024, 3, 11), dt.date(2024, 3, 15))
    assert dates.pay_week(dt.date(2024, 3, 11)) == (dt.date(2024, 3, 11), dt.date(2024, 3, 15))


def test_quarter_helpers_cover_legacy_turnover_window():
    assert dates.quarter_end(dt.date(2024, 3, 15)) == dt.date(2024, 3, 31)
    assert dates.quarter_months(dt.date(2024, 3, 15)) == [
        ("2024-01", dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
        ("2024-02", dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
        ("2024-03", dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
    ]
