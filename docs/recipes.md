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
