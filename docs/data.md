# Data Engineering Helpers

`runbook` includes optional core helpers for common data engineering checks. They do not require Airflow or external services.

## Checks

```python
from runbook import (
    check_files_exist,
    check_freshness,
    check_manifest_exists,
    check_not_empty,
    check_row_count,
    check_schema,
    check_watermark,
    compare_row_counts,
)
```

Examples:

```python
step("Check files").require(check_files_exist("files"))
step("Check rows").require(check_row_count("row_count", minimum=1))
step("Check schema").require(check_schema("rows", ["id", "created_at"]))
step("Compare counts").require(compare_row_counts("source_count", "target_count", tolerance=10))
```

## Stage Factories

High-level factories help generate readable stage trees:

```python
from runbook import Runbook, export_stage, post_export_checks, pre_export_checks

runbook = (
    Runbook("Orders export")
    .add(pre_export_checks(files_key="files", schema_key="rows", required_fields=["id"]))
    .add(export_stage())
    .add(post_export_checks(manifest_key="manifest"))
)
```

These factories are intentionally small. They are examples of reusable patterns, not a scheduler.
