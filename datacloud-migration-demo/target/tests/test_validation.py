from target.lib import validation


def _write(path, text):
    path.write_text(text)
    return str(path)


def test_exact_match_ignores_row_order(tmp_path):
    e = _write(tmp_path / "e.csv", "a,b\n1,x\n2,y\n")
    a = _write(tmp_path / "a.csv", "a,b\n2,y\n1,x\n")
    assert validation.compare_csv(a, e)["match"]


def test_detects_value_header_and_duplicate_row_diffs(tmp_path):
    e = _write(tmp_path / "e.csv", "a,b\n1,x\n2,y\n")
    assert not validation.compare_csv(_write(tmp_path / "v.csv", "a,b\n1,x\n2,z\n"), e)["match"]
    assert validation.compare_csv(_write(tmp_path / "h.csv", "b,a\nx,1\ny,2\n"), e)["reason"] == "header mismatch"
    dup = validation.compare_csv(_write(tmp_path / "d.csv", "a,b\n1,x\n1,x\n2,y\n"), e)
    assert not dup["match"] and dup["unexpected_count"] == 1


def test_formatting_is_significant(tmp_path):
    e = _write(tmp_path / "e.csv", "h\n8.00\n")
    assert not validation.compare_csv(_write(tmp_path / "a.csv", "h\n8.0\n"), e)["match"]


def test_compare_job_flags_missing_and_extra(tmp_path):
    exp, act = tmp_path / "exp", tmp_path / "act"
    exp.mkdir()
    act.mkdir()
    _write(exp / "one.csv", "a\n1\n")
    _write(act / "two.csv", "a\n1\n")
    res = {r["dataset"]: r for r in validation.compare_job(str(act), str(exp))}
    assert res["one.csv"]["reason"] == "missing actual output"
    assert res["two.csv"]["reason"].startswith("unexpected output dataset")
