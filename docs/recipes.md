# Recipes

## Check That Input Exists

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("input").add(
    step("Check input").require(not_empty("items"), "items are required")
)
```

## Skip When There Is Nothing to Process

```python
from runbook import Runbook, empty, step

runbook = Runbook("process").add(
    step("Process files")
    .load("files", lambda context: [])
    .skip_when(empty("files"), "No files to process")
    .then(lambda context: context.update({"processed": True}))
)
```

## Warn But Continue

```python
from runbook import Runbook, gt, step

runbook = Runbook("latency").add(
    step("Check latency")
    .set("delay_minutes", 45)
    .warn_when(gt("delay_minutes", 30), "Input is late")
)
```

## Fail on a Bad State

```python
from runbook import Runbook, gt, step

runbook = Runbook("errors").add(
    step("Check errors")
    .set("error_count", 2)
    .fail_when(gt("error_count", 0), "Errors found")
)
```

## Use a Custom Loader

```python
from runbook import Runbook, not_empty, step

def load_users(context):
    return [{"id": 1}, {"id": 2}]

runbook = Runbook("users").add(
    step("Load users")
    .load("users", load_users)
    .require(not_empty("users"), "No users found")
)
```

## Check Local Files

```python
from runbook import Runbook, matches_any, not_empty, step
from runbook.integrations.files import glob_paths

runbook = Runbook("local files").add(
    step("Find CSV files")
    .load("files", glob_paths("/data/*.csv"))
    .require(not_empty("files"), "No files found")
    .require(matches_any("files", "*.csv"), "CSV file is missing")
)
```

## Check an HTTP API

```python
from runbook import Runbook, equals, step
from runbook.integrations.http import get_json

runbook = Runbook("api").add(
    step("Health")
    .load("response", get_json("https://example.com/health"))
    .require(equals("response.status", "ok"), "Service is unhealthy")
)
```

## Retry a Transient Check

```python
from runbook import Runbook, equals, step
from runbook.integrations.http import get_json

runbook = Runbook("api").add(
    step("Health")
    .retry(times=3, delay=5)
    .load("response", get_json("https://example.com/health"))
    .require(equals("response.status", "ok"), "Service is unhealthy")
)
```

## Timeout a Slow Step

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("timeout").add(
    step("Slow loader")
    .timeout(seconds=30)
    .load("items", lambda context: [])
    .require(not_empty("items"), "No items")
)
```

## Use a Custom Check

```python
from runbook import Runbook, custom, step

has_admin = custom(
    "has_admin(users)",
    lambda context: any(user["role"] == "admin" for user in context["users"]),
)

runbook = Runbook("users").add(
    step("Check admin")
    .set("users", [{"role": "admin"}])
    .require(has_admin, "No admin user")
)
```

## Build an Embeddable Export Runbook

```python
from runbook import JsonlResultExporter, Runbook, check_row_count, check_schema, not_empty, post_export_checks, stage, step

runbook = (
    Runbook("Orders export")
    .export_to(JsonlResultExporter("runbook-results.jsonl"))
    .add(
        stage("Pre-checks")
        .add(step("Find files").lazy("files", find_files).require(not_empty("files"), "No input files found"))
        .add(
            step("Read rows")
            .inputs("files")
            .publish("rows", read_rows)
            .publish("row_count", lambda context: len(context["rows"]))
        )
        .add(step("Check schema").require(check_schema("rows", ["id", "created_at"])))
        .add(step("Check row count").require(check_row_count("row_count", minimum=1)))
    )
    .add(stage("Export").add(step("Build manifest").publish("manifest", build_manifest)))
    .add(post_export_checks())
)
```

See `examples/orders_export.py` for a complete local version.
