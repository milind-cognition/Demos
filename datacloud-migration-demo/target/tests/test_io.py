import pytest

from target.lib import io


def test_in_predicate_quotes_values():
    assert io.in_predicate("snapshot_month", ["2024-01", "2024-02"]) == "snapshot_month IN ('2024-01', '2024-02')"
    assert io.in_predicate("k", ["o'brien"]) == "k IN ('o''brien')"
    with pytest.raises(ValueError):
        io.in_predicate("k", [])


def test_write_output_replace_where_csv_writes_full_sorted_file(spark, tmp_path):
    df = spark.createDataFrame([("2024-02", 2), ("2024-01", 1)], "m string, n int")
    path = io.write_output_replace_where(df, "csv", str(tmp_path), "unused", "ds", ["m", "n"],
                                         io.in_predicate("m", ["2024-01"]))
    assert open(path).read().splitlines() == ["m,n", "2024-01,1", "2024-02,2"]
    with pytest.raises(ValueError):
        io.write_output_replace_where(df, "parquet", str(tmp_path), "unused", "ds", ["m", "n"], "m = 'x'")


class _RecordingWriter:
    def __init__(self, calls):
        self.calls = calls

    def mode(self, m):
        self.calls.append(("mode", m))
        return self

    def option(self, k, v):
        self.calls.append(("option", k, v))
        return self

    def saveAsTable(self, name):
        self.calls.append(("saveAsTable", name))


class _RecordingFrame:
    def __init__(self):
        self.calls = []

    def select(self, *cols):
        self.calls.append(("select",) + cols)
        return self

    @property
    def write(self):
        return _RecordingWriter(self.calls)


def test_write_output_replace_where_table_uses_delta_replace_where():
    # Delta is not available on local PySpark, so assert the writer call chain the cluster will run.
    df = _RecordingFrame()
    pred = io.in_predicate("snapshot_month", ["2024-04", "2024-05", "2024-06"])
    fqn = io.write_output_replace_where(df, "table", "unused", "hr_curated", "turnover_snapshot", ["m", "n"], pred)
    assert fqn == "hr_curated.turnover_snapshot"
    assert df.calls == [
        ("select", "m", "n"),
        ("mode", "overwrite"),
        ("option", "replaceWhere", "snapshot_month IN ('2024-04', '2024-05', '2024-06')"),
        ("saveAsTable", "hr_curated.turnover_snapshot"),
    ]
