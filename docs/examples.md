# Examples Cookbook

This page collects practical examples for common integration styles. Use it as a copy-and-adapt reference.

## 1. Smallest Useful Check

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("Input checks").add(
    step("Check files").require(not_empty("files"), "No files found")
)

result = runbook.execute({"files": ["orders.csv"]})
```

## 2. Function Decorator Style

Use this style when your checks naturally start as Python functions.

```python
from runbook import Runbook, not_empty, stage, step

@step("Find files", output="files")
def find_files():
    return ["orders.csv"]

@step("Read rows", output="rows")
def read_rows(files):
    return [{"file": files[0], "id": 1}]

find_files.require(not_empty("files"), "No files found")

@stage("Pre-checks")
def pre_checks():
    return [find_files, read_rows]

runbook = Runbook("Orders export").add(pre_checks)
```

Function arguments are read from context. In the example above, `files` is equivalent to `inputs("files")`.

## 3. Fluent Pipeline Style

Use this style when you want every step contract visible in one chain.

```python
from runbook import Runbook, check_row_count, check_schema, not_empty, stage, step

runbook = (
    Runbook("Orders export")
    .add(
        stage("Pre-checks")
        .add(step("Find files").publish("files", find_files))
        .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
        .add(step("Read rows").inputs("files").publish("rows", read_rows))
        .add(step("Count rows").inputs("rows").publish("row_count", lambda ctx: len(ctx["rows"])))
        .add(step("Check schema").inputs("rows").require(check_schema("rows", ["id", "created_at"])))
        .add(step("Check rows").inputs("row_count").require(check_row_count("row_count", minimum=1)))
    )
    .add(step("Export").inputs("rows").then(export_rows))
)
```

## 4. Declarative JSON For Non-Python Users

`checks.json`:

```json
{
  "name": "Orders checks",
  "steps": [
    {
      "name": "Check files",
      "inputs": ["files"],
      "require": [
        {
          "check": "not_empty",
          "args": ["files"],
          "message": "No files found"
        }
      ]
    }
  ]
}
```

Run it:

```bash
runbook run checks.json --context '{"files": ["orders.csv"]}'
```

Or from Python:

```python
from runbook import runbook_from_file

runbook = runbook_from_file("checks.json")
result = runbook.execute({"files": ["orders.csv"]})
```

## 5. YAML Checks

```yaml
name: Orders checks
stages:
  - name: Pre-checks
    steps:
      - name: Check files
        inputs: [files]
        require:
          - check: not_empty
            args: [files]
            message: No files found
```

YAML support requires PyYAML. JSON support has no optional dependency.

## 6. CLI Script

`checks.py`:

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("Local checks").add(
    step("Check items").require(not_empty("items"), "items are required")
)
```

Commands:

```bash
runbook validate checks.py
runbook list checks.py
runbook run checks.py --context '{"items": [1, 2, 3]}'
runbook run checks.py --quiet --json --context '{"items": [1, 2, 3]}'
```

## 7. API Endpoint

Use `execute()` so the application can decide how to respond.

```python
def validate_request(payload):
    result = runbook.execute({"files": payload.get("files", [])})

    if result.failed:
        return {
            "ok": False,
            "error": result.error.message,
            "result": result.to_dict(),
        }

    return {"ok": True, "result": result.to_dict()}
```

## 8. Test Suite

```python
def test_orders_checks_pass():
    result = runbook.execute({"files": ["orders.csv"], "row_count": 10})

    assert result.passed
    assert result.find("Check files").passed
```

## 9. Airflow Task

Keep the runbook portable. Let Airflow only provide context and scheduling.

```python
def airflow_callable(**airflow_context):
    context = {
        "ds": airflow_context["ds"],
        "files": find_files_for_ds(airflow_context["ds"]),
    }

    runbook.run(context)
```

Use the Airflow adapter only when you want Airflow-specific exception handling.

## 10. Local File Checks

```python
from runbook import Runbook, matches_any, not_empty, step
from runbook.integrations.files import glob_paths

runbook = Runbook("File checks").add(
    step("Find CSV files")
    .publish("files", glob_paths("/data/*.csv"))
    .require(not_empty("files"), "No files found")
    .require(matches_any("files", "*.csv"), "CSV file is missing")
)
```

## 11. HTTP Health Check

```python
from runbook import Runbook, equals, step
from runbook.integrations.http import get_json

runbook = Runbook("API checks").add(
    step("Health")
    .publish("response", get_json("https://example.com/health"))
    .require(equals("response.status", "ok"), "Service is unhealthy")
)
```

## 12. Pydantic Validation

```python
from pydantic import BaseModel
from runbook import Runbook, step

class Row(BaseModel):
    id: int
    created_at: str

runbook = Runbook("Schema checks").add(
    step("Validate row").validate_schema("row", Row)
)

result = runbook.execute({"row": {"id": 1, "created_at": "2026-05-09T00:00:00Z"}})
```

Pydantic is optional. `runbook` calls `model_validate` or `parse_obj` when the model provides it.

## 13. JSON-Schema-Like Validation

```python
step("Validate row").validate_schema(
    "row",
    {
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "integer"}},
    },
)
```

## 14. Warnings And Skips

```python
from runbook import empty, gt, step

step("Export").skip_when(empty("rows"), "Nothing to export")
step("Freshness").warn_when(gt("delay_minutes", 30), "Input is late")
```

## 15. Continue After Validation Failures

Use this when a validation stage should collect all failures.

```python
validations = (
    stage("Validations")
    .continue_on_error()
    .add(step("Check files").require(not_empty("files"), "No files"))
    .add(step("Check rows").require(gt("row_count", 0), "No rows"))
)
```

## 16. Scoped Reusable Stage

Use `scoped()` when a reusable stage should not leak temporary context values.

```python
optional_validation = (
    stage("Optional validation")
    .scoped()
    .add(step("Load temp rows").publish("temp_rows", load_temp_rows))
    .add(step("Check temp rows").require(not_empty("temp_rows"), "No temp rows"))
)
```

## 17. Lazy Expensive Values

Use `lazy()` when loading a value is expensive and might not be needed.

```python
runbook = (
    Runbook("Lazy checks")
    .add(step("Prepare").lazy("files", find_files))
    .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
)
```

## 18. Expanded Item Checks

```python
runbook = Runbook("Items").add(step("Load").set("items", [{"id": 1}, {"id": 2}]))

with runbook.expand("items") as each:
    each.add(step("Check item").require(exists("item.id"), "Item id is missing"))
```

Use `parallel=True` only when each item is independent:

```python
with runbook.expand("items", parallel=True, max_workers=8) as each:
    each.add(step("Check item").require(exists("item.id"), "Item id is missing"))
```

## 19. Result Export

```python
from runbook import JsonlResultExporter

runbook.export_to(JsonlResultExporter("runbook-results.jsonl"))
result = runbook.execute(context)
```

## 20. Async Result Export

```python
from runbook import AsyncResultExporter, JsonlResultExporter

with AsyncResultExporter(JsonlResultExporter("runbook-results.jsonl")) as exporter:
    runbook.export_to(exporter)
    result = runbook.execute(context)
```

Call `flush()` or `close()` before shutdown when not using a context manager.

## 21. Registry Check

```python
from runbook import Registry, custom, runbook_from_file

registry = Registry()
registry.register_check(
    "positive",
    lambda key: custom(f"positive({key})", lambda ctx: ctx[key] > 0),
)

runbook = runbook_from_file("checks.json", registry=registry)
```

`checks.json`:

```json
{
  "name": "Registered checks",
  "steps": [
    {
      "name": "Check count",
      "require": [{"check": "positive", "args": ["count"]}]
    }
  ]
}
```

## 22. Plugin Entry Points

`pyproject.toml`:

```toml
[project.entry-points."runbook.plugins"]
company_checks = "company_checks.runbook_plugin:register"
```

Plugin module:

```python
def register(registry):
    registry.register_check("positive", positive_check)
```

Application startup:

```python
from runbook import load_registry_entry_points

load_registry_entry_points()
```

## 23. Failure Formatting

```python
from runbook import format_failure

result = runbook.execute(context)

if result.failed:
    print(format_failure(result.error, result.context, result.name))
```

## 24. Choosing A Style

Use fluent style when the runbook itself should show every contract:

```python
step("Read rows").inputs("files").publish("rows", read_rows)
```

Use decorator style when normal Python functions are the source of truth:

```python
@step("Read rows", output="rows")
def read_rows(files):
    return warehouse.read(files)
```

Use declarative JSON/YAML when non-Python users should author checks:

```json
{"name": "Checks", "steps": [{"name": "Check files", "require": [{"check": "not_empty", "args": ["files"]}]}]}
```
