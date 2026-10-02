"""DAG-structure checks for the hr_daily orchestration (MIGRATION_STANDARDS.md section 8)."""
import json
import os
import re
import xml.etree.ElementTree as ET

import pytest

from target.lib import paths

SPEC = json.load(open(paths.workflow_path("hr_daily")))
TASKS = {t["task_key"]: t for t in SPEC["tasks"]}
NOTEBOOK_TASKS = {k: t for k, t in TASKS.items() if "notebook_task" in t}
CONDITION_TASKS = {k: t for k, t in TASKS.items() if "condition_task" in t}
NOTEBOOK_PREFIX = "datacloud-migration-demo/target/notebooks/nb_"
LEGACY_JOBS = sorted(d for d in os.listdir(paths.EXPECTED_OUTPUTS_DIR)
                     if os.path.isdir(os.path.join(paths.EXPECTED_OUTPUTS_DIR, d)))
OOZIE_ACTION_TO_JOB = {"stage": "stage_and_publish"}
JOB_PARAM_REF = re.compile(r"\{\{\s*job\.parameters\.(\w+)\s*\}\}")


def _deps(task):
    return [d["task_key"] for d in task.get("depends_on", [])]


def _oozie_ok_chain():
    ns = {"wf": "uri:oozie:workflow:0.5"}
    root = ET.parse(os.path.join(paths.DEMO_ROOT, "legacy", "oozie", "workflow.xml")).getroot()
    actions = {a.get("name"): a for a in root.findall("wf:action", ns)}
    chain, node = [], root.find("wf:start", ns).get("to")
    while node in actions:
        chain.append(OOZIE_ACTION_TO_JOB.get(node, node))
        node = actions[node].find("wf:ok", ns).get("to")
    assert node == "end"
    return chain


def test_top_level_shape():
    assert SPEC["name"] == "hr_daily.hr_daily"
    assert SPEC["format"] == "MULTI_TASK"
    assert SPEC["max_concurrent_runs"] == 1
    assert SPEC["timeout_seconds"] <= 7200, "run_daily.sh failed the batch after a 2h Oozie poll"
    assert SPEC["queue"]["enabled"] is True
    assert SPEC["schedule"]["pause_status"] == "PAUSED"
    assert SPEC["email_notifications"]["on_failure"]
    for tag in ("domain", "team", "legacy_artifact", "migration_wave", "cost_center"):
        assert tag in SPEC["tags"]
    assert len(TASKS) == len(SPEC["tasks"]), "duplicate task_key"


def test_every_depends_on_resolves():
    for key, task in TASKS.items():
        for dep in _deps(task):
            assert dep in TASKS, "%s depends on unknown task %s" % (key, dep)
            assert dep != key


def test_no_cycles():
    indegree = {k: len(_deps(t)) for k, t in TASKS.items()}
    ready = [k for k, n in indegree.items() if n == 0]
    seen = []
    while ready:
        key = ready.pop()
        seen.append(key)
        for other, task in TASKS.items():
            if key in _deps(task):
                indegree[other] -= 1
                if indegree[other] == 0:
                    ready.append(other)
    assert sorted(seen) == sorted(TASKS), "cycle among %s" % sorted(set(TASKS) - set(seen))


def test_one_notebook_task_per_legacy_job():
    assert sorted(NOTEBOOK_TASKS) == LEGACY_JOBS


@pytest.mark.parametrize("key", sorted(NOTEBOOK_TASKS))
def test_notebook_task_follows_conventions(key):
    task = NOTEBOOK_TASKS[key]
    nt = task["notebook_task"]
    assert nt["notebook_path"] == NOTEBOOK_PREFIX + key
    assert not nt["notebook_path"].endswith(".py")
    assert nt["source"] == "GIT"
    params = nt["base_parameters"]
    assert params["run_date"] == "{{job.parameters.run_date}}"
    assert params["output_sink"] == "table"
    assert params["validate"] == "false"
    assert task["job_cluster_key"] in {c["job_cluster_key"] for c in SPEC["job_clusters"]}
    for field in ("timeout_seconds", "max_retries", "min_retry_interval_millis"):
        assert field in task
    assert task["email_notifications"]["on_failure"]


@pytest.mark.parametrize("key", sorted(NOTEBOOK_TASKS))
def test_matches_per_job_workflow(key):
    per_job = paths.workflow_path(key)
    if not os.path.exists(per_job):
        pytest.skip("target/workflows/%s.json not migrated yet" % key)
    spec = json.load(open(per_job))
    per_job_nt = [t["notebook_task"] for t in spec["tasks"]
                  if t.get("notebook_task", {}).get("notebook_path") == NOTEBOOK_PREFIX + key]
    assert per_job_nt, "%s has no notebook_task for nb_%s" % (per_job, key)
    assert NOTEBOOK_TASKS[key]["notebook_task"] == per_job_nt[0]


def test_every_job_parameter_reference_is_declared():
    declared = {p["name"] for p in SPEC["parameters"]}
    used = set(JOB_PARAM_REF.findall(json.dumps(SPEC["tasks"])))
    assert "run_date" in declared
    assert used <= declared, "undeclared job parameters: %s" % sorted(used - declared)


def test_oozie_ok_to_chain_is_mirrored():
    chain = _oozie_ok_chain()
    assert chain == ["stage_and_publish", "emp_metrics_daily", "payroll_join"]
    assert _deps(TASKS[chain[0]]) == []
    for upstream, downstream in zip(chain, chain[1:]):
        assert _deps(TASKS[downstream]) == [upstream]


def test_run_daily_tail_runs_after_oozie():
    assert _deps(TASKS["cohort_tagger"]) == ["payroll_join"]
    assert list(CONDITION_TASKS) == ["is_month_close"]
    gate = CONDITION_TASKS["is_month_close"]
    assert _deps(gate) == ["cohort_tagger"]
    assert "{{job.parameters." in gate["condition_task"]["left"]
    assert TASKS["turnover_snapshot"]["depends_on"] == [{"task_key": "is_month_close", "outcome": "true"}]
