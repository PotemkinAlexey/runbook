# Integrations

The core package is portable. Integrations live outside the core API.

## Files

Local filesystem helpers are available from `runbook.integrations.files`.

```python
from runbook import Runbook, not_empty, step
from runbook.integrations.files import glob_paths, read_json

checks = Runbook("files").add(
    step("Read input")
    .load("files", glob_paths("/data/*.json"))
    .require(not_empty("files"), "No JSON files found")
    .load("config", read_json("config.json"))
)
```

## Airflow

Airflow helpers are available from `runbook.integrations.airflow`.

```python
from runbook import Runbook, not_empty, step
from runbook.integrations.airflow import run_task, s3_keys, slack_notify

checks = (
    Runbook("Daily S3 checks")
    .notify_on_failure(
        slack_notify("slack_default", "#alerts", "Runbook failed", "{{ step_name }} failed")
    )
    .add(
        step("Check input files")
        .load("files", s3_keys("aws_default", "bucket", "daily/{{ ds }}/"))
        .require(not_empty("files"), "No input files found")
    )
)

def airflow_callable(**context):
    run_task(checks, context)
```

`run_task()` converts `RunbookFailedError` into Airflow's `AirflowFailException`.

## HTTP

HTTP helpers are available from `runbook.integrations.http`.

```python
from runbook import Runbook, equals, step
from runbook.integrations.http import get_json, post_json

checks = Runbook("api").add(
    step("Check API")
    .load("response", get_json("https://example.com/status"))
    .require(equals("response.ok", True), "API is not healthy")
    .then(post_json("https://example.com/audit", "response"))
)
```

The HTTP integration uses the Python standard library.

## Writing an Integration

An integration usually exposes loaders and actions.

Loader:

```python
def list_files(path):
    def loader(context):
        return ...
    return loader
```

Action:

```python
def notify(message):
    def action(context):
        ...
    return action
```

Then use them from a step:

```python
step("Check").load("files", list_files("/data")).then(notify("done"))
```
