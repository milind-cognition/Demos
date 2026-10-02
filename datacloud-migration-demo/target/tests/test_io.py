import csv
import datetime as dt

from target.lib import hr_transforms as hr, io


def test_employee_source_order_survives_shuffle_and_exact_duplicates(spark, tmp_path):
    path = tmp_path / "employees.csv"
    first = dict(emp_id="E1", dept_id="Z99", effective_date="2024-03-01",
                 job_title='VP "HR", Ops', term_date="")
    second = dict(first, dept_id="A01", term_date="2024-03-10")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=io.INPUT_COLUMNS["employees"],
                                doublequote=False, escapechar="\\")
        writer.writeheader()
        writer.writerow(first)
        stream.write("\r\n")
        writer.writerows([second, first, dict(first, effective_date="2024-04-01")])

    employees = io.read_dataset(spark, str(path), "employees")
    assert "_source_order" in employees.columns
    records = employees.orderBy("_source_order").collect()
    assert [r._source_order.row for r in records] == [1, 3, 4, 5]
    assert [r.dept_id for r in records] == ["Z99", "A01", "Z99", "Z99"]
    assert all(r.job_title == first["job_title"] and r.term_reason == "" for r in records)
    selected = hr.current_employee_version(employees.repartition(3), dt.date(2024, 3, 15))
    assert selected.columns == io.INPUT_COLUMNS["employees"]
    result = selected.collect()
    assert len(result) == 1
    assert result[0].dept_id == "Z99" and result[0].term_date == ""
