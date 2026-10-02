"""Local stand-in for the subset of Databricks ``dbutils`` that migrated notebooks may use.

Only ``dbutils.widgets`` and ``dbutils.notebook.exit`` are supported -- that is the whole
contract (MIGRATION_STANDARDS.md §4). Notebooks bind it like this, so the real ``dbutils`` wins
on a cluster and the shim is used everywhere else:

    try:
        dbutils  # noqa: F821  (injected by Databricks)
    except NameError:
        from target.lib.dbutils_shim import dbutils

Widget value resolution order (first hit wins):

1. command-line ``--<name>=<value>`` or ``--<name> <value>`` (``--validate`` alone means ``true``)
2. environment variable ``HRDP_<NAME>`` (upper-cased), e.g. ``HRDP_RUN_DATE=2024-03-15``
3. the default declared by ``dbutils.widgets.text(...)`` / ``dropdown(...)``
"""
import json
import os
import sys

ENV_PREFIX = "HRDP_"


class InputWidgetNotDefined(Exception):
    """Mirrors com.databricks.dbutils_v1.InputWidgetNotDefined."""


class NotebookExit(SystemExit):
    """Raised by ``dbutils.notebook.exit`` so local runs stop like a cluster run would."""

    def __init__(self, value):
        super().__init__(0)
        self.value = value


def parse_cli_args(argv):
    """Parse ``--key=value`` / ``--key value`` / bare ``--flag`` into a dict of strings."""
    out = {}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--"):
            key = tok[2:]
            if "=" in key:
                key, val = key.split("=", 1)
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                val = argv[i + 1]
                i += 1
            else:
                val = "true"
            out[key.replace("-", "_")] = val
        i += 1
    return out


class _Widgets:
    def __init__(self, argv=None, environ=None):
        self._argv = sys.argv[1:] if argv is None else argv
        self._environ = os.environ if environ is None else environ
        self._defaults = {}
        self._choices = {}

    def text(self, name, defaultValue, label=None):
        self._defaults[name] = defaultValue

    def dropdown(self, name, defaultValue, choices, label=None):
        if defaultValue not in choices:
            raise ValueError("default %r not in choices %r for widget %r" % (defaultValue, choices, name))
        self._defaults[name] = defaultValue
        self._choices[name] = list(choices)

    def get(self, name):
        cli = parse_cli_args(self._argv)
        if name in cli:
            val = cli[name]
        elif ENV_PREFIX + name.upper() in self._environ:
            val = self._environ[ENV_PREFIX + name.upper()]
        elif name in self._defaults:
            val = self._defaults[name]
        else:
            raise InputWidgetNotDefined("No input widget named %s is defined" % name)
        if name in self._choices and val not in self._choices[name]:
            raise ValueError("widget %r value %r not in %r" % (name, val, self._choices[name]))
        return val

    def getAll(self):
        return {k: self.get(k) for k in self._defaults}

    def remove(self, name):
        self._defaults.pop(name, None)
        self._choices.pop(name, None)

    def removeAll(self):
        self._defaults.clear()
        self._choices.clear()


class _Notebook:
    def exit(self, value):
        print("NOTEBOOK_EXIT " + (value if isinstance(value, str) else json.dumps(value)))
        raise NotebookExit(value)


class LocalDBUtils:
    def __init__(self, argv=None, environ=None):
        self.widgets = _Widgets(argv, environ)
        self.notebook = _Notebook()


dbutils = LocalDBUtils()
