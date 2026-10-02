"""Path conventions shared by notebooks, the validator and the tests."""
import os

DEMO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAMPLE_DATA_DIR = os.path.join(DEMO_ROOT, "legacy", "sample_data")
EXPECTED_OUTPUTS_DIR = os.path.join(DEMO_ROOT, "legacy", "expected_outputs")
LOCAL_OUTPUT_DIR = os.path.join(DEMO_ROOT, "target", "output")
NOTEBOOKS_DIR = os.path.join(DEMO_ROOT, "target", "notebooks")
WORKFLOWS_DIR = os.path.join(DEMO_ROOT, "target", "workflows")


def resolve(root_or_blank, default):
    """Blank widget -> repo default; relative paths are resolved against the demo root."""
    if not root_or_blank:
        return default
    return root_or_blank if os.path.isabs(root_or_blank) else os.path.join(DEMO_ROOT, root_or_blank)


def input_path(input_root, dataset):
    return os.path.join(input_root, dataset + ".csv")


def job_output_dir(output_root, job):
    return os.path.join(output_root, job)


def expected_dir(job):
    return os.path.join(EXPECTED_OUTPUTS_DIR, job)


def notebook_path(job):
    return os.path.join(NOTEBOOKS_DIR, "nb_%s.py" % job)


def workflow_path(job):
    return os.path.join(WORKFLOWS_DIR, "%s.json" % job)
