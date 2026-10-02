"""Shared utilities for migrated HR data-platform notebooks (``hrdp`` = HR Data Platform).

Everything here runs on vanilla PySpark 3.5 (local) and on Databricks Runtime 15.4 LTS without
modification. Nothing in this package may import Databricks-runtime-only modules
(``dbutils``, ``pyspark.dbutils``, ``databricks.*``, ``delta``); see MIGRATION_STANDARDS.md §3.
"""

__all__ = ["dates", "dbutils_shim", "hr_transforms", "io", "params", "paths", "spark", "validation"]
