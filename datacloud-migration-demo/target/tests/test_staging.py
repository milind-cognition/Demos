import pytest

from target.lib import staging

SHELL_EXPECTED = {
    "departments": "dept_id,dept_name,cost_center,division,region,is_active",
    "employees": "emp_id,first_name,last_name,dept_id,job_title,employment_type,pay_type,hourly_rate,hire_date,"
                 "term_date,term_reason,location,manager_id,effective_date,record_source",
    "timecards": "timecard_id,emp_id,work_date,pay_code,hours,approved_flag,submitted_ts,source_system",
}


def _lines(spark, values):
    return spark.createDataFrame([(v,) for v in values], "value string")


def _audit(spark, dataset, values):
    r = staging.audit_feed(_lines(spark, values), dataset, "2024-03-15").collect()
    assert len(r) == 1
    return r[0].asDict()


def test_feed_contract_matches_shell_script():
    for ds, hdr in SHELL_EXPECTED.items():
        assert staging.expected_header(ds) == hdr
    assert staging.key_positions("departments") == [1]
    assert staging.key_positions("employees") == [1, 14]
    assert staging.key_positions("timecards") == [1]


def test_check_header_is_exact():
    staging.check_header("departments", SHELL_EXPECTED["departments"])
    for bad in ("", SHELL_EXPECTED["departments"] + " ", "DEPT_ID" + SHELL_EXPECTED["departments"][7:],
                "dept_id,dept_name,cost_center,division,region"):
        with pytest.raises(staging.HeaderMismatchError, match="FAILED_HEADER"):
            staging.check_header("departments", bad)


def test_read_feed_lines_strips_cr_and_keeps_line_order(spark, tmp_path):
    f = tmp_path / "departments.csv"
    f.write_bytes((SHELL_EXPECTED["departments"] + "\r\nD1,a,b,c,d,Y\r\n\r\n").encode())
    lines = staging.read_feed_lines(spark, str(f))
    assert staging.header_line(lines) == SHELL_EXPECTED["departments"]
    assert [r.value for r in lines.collect()] == [SHELL_EXPECTED["departments"], "D1,a,b,c,d,Y", ""]


def test_read_feed_lines_missing_file(spark, tmp_path):
    with pytest.raises(FileNotFoundError, match="missing inbound file"):
        staging.read_feed_lines(spark, str(tmp_path / "nope.csv"))


def test_read_feed_lines_rejects_directory(spark, tmp_path):
    d = tmp_path / "departments.csv"
    d.mkdir()
    (d / "part-0").write_text(SHELL_EXPECTED["departments"] + "\nD1,a,b,c,d,Y\n")
    with pytest.raises(FileNotFoundError, match="not a single regular file"):
        staging.read_feed_lines(spark, str(d))


def test_audit_counts_and_dup_status(spark):
    r = _audit(spark, "departments", [SHELL_EXPECTED["departments"], "D1,a", "D2,b", "D1,c", "   ", ""])
    assert r == {"load_date": "2024-03-15", "dataset": "departments", "row_count": 3, "distinct_key_count": 2,
                 "duplicate_key_count": 1, "status": "WARN_DUP_KEYS"}
    ok = _audit(spark, "departments", [SHELL_EXPECTED["departments"], "D1,a", "D2,b"])
    assert (ok["row_count"], ok["distinct_key_count"], ok["duplicate_key_count"], ok["status"]) == (2, 2, 0, "OK")


def test_audit_composite_key_uses_cut_semantics(spark):
    hdr = SHELL_EXPECTED["employees"]
    row = "E1,f,l,D1,t,FT,HOURLY,1.00,2024-01-01,,,X,M,{eff},WD"
    r = _audit(spark, "employees", [hdr, row.format(eff="2024-01-01"), row.format(eff="2024-02-01"),
                                    row.format(eff="2024-01-01"), "E2,short"])
    assert (r["row_count"], r["distinct_key_count"], r["duplicate_key_count"]) == (4, 3, 1)


def test_audit_header_key_repeated_in_data(spark):
    hdr = SHELL_EXPECTED["timecards"]
    r = _audit(spark, "timecards", [hdr, "timecard_id,x", "T1,y"])
    assert (r["row_count"], r["distinct_key_count"], r["duplicate_key_count"]) == (2, 2, 0)
