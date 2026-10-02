"""Inbound-feed staging checks (legacy ``shell/stage_and_publish.sh stage``).

The feed contract lives here once: the expected header of every landing CSV (derived from
``io.INPUT_COLUMNS``, which the readers use too) and each dataset's business key. The audit
reproduces the shell pipeline line-for-line:

* ``tr -d '\\r'``                         -> every CR removed from every line
* ``head -1`` vs ``EXPECTED_<ds>``        -> exact string compare, no trimming
* ``tail -n +2 | grep -v '^[[:space:]]*$' | wc -l``           -> ``row_count``
* ``... | cut -d, -f<keycols> | sort -u | wc -l``            -> ``distinct_key_count``
  (raw comma split like ``cut``: no CSV quote handling, no trimming)
"""
from pyspark.errors import AnalysisException
from pyspark.sql import functions as F

from target.lib import io

FEED_DATASETS = ("departments", "employees", "timecards")

BUSINESS_KEYS = {
    "departments": ("dept_id",),
    "employees": ("emp_id", "effective_date"),
    "timecards": ("timecard_id",),
}

AUDIT_COLUMNS = ["load_date", "dataset", "row_count", "distinct_key_count", "duplicate_key_count", "status"]

STATUS_OK = "OK"
STATUS_WARN_DUP_KEYS = "WARN_DUP_KEYS"
STATUS_FAILED_HEADER = "FAILED_HEADER"

_BLANK_LINE = r"^\s*$"


class HeaderMismatchError(ValueError):
    """Inbound file header differs from the feed contract (legacy ``FAILED_HEADER``, exit 1)."""

    def __init__(self, dataset, got, expected):
        self.dataset, self.got, self.expected = dataset, got, expected
        super().__init__("%s: header mismatch for %s\n  got:      %s\n  expected: %s"
                         % (STATUS_FAILED_HEADER, dataset, got, expected))


def expected_header(dataset):
    return ",".join(io.INPUT_COLUMNS[dataset])


def key_positions(dataset):
    """1-based column positions of the business key (the shell's ``KEYCOLS_<ds>``)."""
    cols = io.INPUT_COLUMNS[dataset]
    return [cols.index(c) + 1 for c in BUSINESS_KEYS[dataset]]


def read_feed_lines(spark, path):
    """Raw lines of one inbound file (single ``value`` column), CRs stripped."""
    try:
        raw = spark.read.option("lineSep", "\n").text(path)
    except AnalysisException as exc:
        raise FileNotFoundError("missing inbound file %s" % path) from exc
    return raw.select(F.regexp_replace("value", "\r", "").alias("value"))


def header_line(lines):
    """First line of the file (``head -1``); empty string for an empty file."""
    first = lines.first()
    return "" if first is None else first["value"]


def check_header(dataset, header):
    expected = expected_header(dataset)
    if header != expected:
        raise HeaderMismatchError(dataset, header, expected)


def cut_fields(line_col, positions):
    """``cut -d, -f<positions>`` on a string column: missing fields are skipped, joined by ``,``."""
    parts = F.split(line_col, ",", -1)
    picked = [F.when(F.size(parts) >= p, F.element_at(parts, p)) for p in positions]
    return F.concat_ws(",", *picked)


def audit_feed(lines, dataset, load_date):
    """One-row ``AUDIT_COLUMNS`` frame for a header-checked feed (``lines`` includes the header).

    The header is line 1, so it is removed from the counts arithmetically: one non-blank line,
    and its key from the distinct set unless a data line carries the same key.
    """
    header_key = ",".join(BUSINESS_KEYS[dataset])
    keyed = (
        lines.filter(~F.col("value").rlike(_BLANK_LINE))
        .select(cut_fields(F.col("value"), key_positions(dataset)).alias("key"))
    )
    counts = keyed.agg(
        F.count(F.lit(1)).alias("_lines"),
        F.countDistinct("key").alias("_distinct"),
        F.sum(F.when(F.col("key") == header_key, 1).otherwise(0)).alias("_header_key_lines"),
    )
    return (
        counts.withColumn("row_count", F.col("_lines") - 1)
        .withColumn("distinct_key_count",
                    F.col("_distinct") - F.when(F.col("_header_key_lines") == 1, 1).otherwise(0))
        .withColumn("duplicate_key_count", F.col("row_count") - F.col("distinct_key_count"))
        .withColumn("status", F.when(F.col("duplicate_key_count") > 0, F.lit(STATUS_WARN_DUP_KEYS))
                    .otherwise(F.lit(STATUS_OK)))
        .withColumn("load_date", F.lit(load_date))
        .withColumn("dataset", F.lit(dataset))
        .select(*AUDIT_COLUMNS)
    )
