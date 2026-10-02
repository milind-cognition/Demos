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
