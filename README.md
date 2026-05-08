# runbook

Small Python library for describing Airflow-oriented operational runbooks.

## Install locally

```bash
pip install -e .
```

## Basic usage

```python
from runbook import Runbook, log, matches_any, not_empty, step

runbook = (
    Runbook("Daily checks")
    .add(
        step("Check files")
        .with_data("files", ["daily.csv"])
        .require(not_empty("files"), "No files found")
        .require(matches_any("files", "*.csv"), "CSV file is missing")
        .then(log("Found {{ files|length }} files"))
    )
)

runbook.run({})
```

The core package only depends on Jinja2 and can run in any Python process.
External systems are optional integrations.

## Airflow integration

```python
from runbook import Runbook, not_empty, step
from runbook.integrations.airflow import run_task, s3_keys, slack_notify

checks = (
    Runbook("Daily S3 checks")
    .notify_on_failure(slack_notify("slack_default", "#alerts", "Runbook failed", "{{ step_name }} failed"))
    .add(
        step("Check input files")
        .with_loader(s3_keys("aws_default", "bucket", "daily/{{ ds }}/"), "files")
        .require(not_empty("files"), "No input files found")
    )
)

def airflow_callable(**context):
    run_task(checks, context)
```

## License

MIT
