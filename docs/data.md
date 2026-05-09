# Data Engineering Helpers

`runbook` includes optional core helpers for common data engineering checks. They do not require Airflow or external services.

Use these helpers after you understand the basic step shape from [Quickstart](quickstart.md). They are convenience checks, not integrations with external systems.

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

## Recommended Pattern

For real pipelines, keep the external I/O in your own loaders and actions:

```python
def find_files(context):
    return storage.list("orders/")

def read_rows(context):
    return warehouse.query("select * from orders")
```

Then wire them into explicit stages:

```python
(
    Runbook("Orders export")
    .add(
        stage("Pre-checks")
        .add(step("Find files").publish("files", find_files))
        .add(step("Check files").inputs("files").require(check_not_empty("files")))
        .add(step("Read rows").inputs("files").publish("rows", read_rows))
        .add(step("Check schema").inputs("rows").require(check_schema("rows", ["id"])))
    )
)
```

This keeps cloud clients, database drivers, and scheduler-specific code outside the core DSL.
