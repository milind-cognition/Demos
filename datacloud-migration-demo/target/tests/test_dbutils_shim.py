import pytest

from target.lib.dbutils_shim import InputWidgetNotDefined, LocalDBUtils, NotebookExit, parse_cli_args


def test_parse_cli_args_forms():
    assert parse_cli_args(["--run_date=2024-03-15", "--validate", "--input-root", "/x"]) == {
        "run_date": "2024-03-15", "validate": "true", "input_root": "/x"}


def test_precedence_cli_over_env_over_default():
    db = LocalDBUtils(argv=["--run_date=2024-04-01"], environ={"HRDP_RUN_DATE": "2024-05-01"})
    db.widgets.text("run_date", "2024-03-15")
    assert db.widgets.get("run_date") == "2024-04-01"
    db = LocalDBUtils(argv=[], environ={"HRDP_RUN_DATE": "2024-05-01"})
    db.widgets.text("run_date", "2024-03-15")
    assert db.widgets.get("run_date") == "2024-05-01"
    db = LocalDBUtils(argv=[], environ={})
    db.widgets.text("run_date", "2024-03-15")
    assert db.widgets.get("run_date") == "2024-03-15"


def test_undefined_widget_and_dropdown_choices():
    db = LocalDBUtils(argv=["--sink=parquet"], environ={})
    with pytest.raises(InputWidgetNotDefined):
        db.widgets.get("nope")
    db.widgets.dropdown("sink", "csv", ["csv", "table"])
    with pytest.raises(ValueError):
        db.widgets.get("sink")


def test_notebook_exit_is_clean_exit():
    with pytest.raises(NotebookExit) as exc:
        LocalDBUtils(argv=[], environ={}).notebook.exit('{"ok": true}')
    assert exc.value.code == 0 and exc.value.value == '{"ok": true}'
