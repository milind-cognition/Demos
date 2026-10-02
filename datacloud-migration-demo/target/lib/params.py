"""Typed accessors over widgets so notebooks never hand-parse strings."""
import datetime as dt


def get_str(dbutils, name):
    return dbutils.widgets.get(name).strip()


def get_date(dbutils, name):
    raw = get_str(dbutils, name)
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise ValueError("widget %r must be an ISO date (yyyy-MM-dd), got %r" % (name, raw))


def get_optional_date(dbutils, name):
    raw = get_str(dbutils, name)
    return dt.date.fromisoformat(raw) if raw else None


def get_bool(dbutils, name):
    raw = get_str(dbutils, name).lower()
    if raw in ("true", "1", "y", "yes"):
        return True
    if raw in ("false", "0", "n", "no", ""):
        return False
    raise ValueError("widget %r must be a boolean, got %r" % (name, raw))
