# Embedding Guide

`runbook` is designed to run inside another Python process. This page shows the common embedding patterns.

## Service Or API

Use `execute()` and return or store the structured result:

```python
def validate_export_request(payload):
    context = {
        "files": payload["files"],
        "request_id": payload["request_id"],
    }

    result = runbook.execute(context)

    if result.failed:
        return {
            "ok": False,
            "error": result.error.message,
            "result": result.to_dict(),
        }

    return {"ok": True, "result": result.to_dict()}
```

## Script Or CLI

Use `run()` when failure should become an exception:

```python
from runbook import configure_runbook_logging

configure_runbook_logging()
runbook.run({"files": ["daily.csv"]})
```

Use `execute()` when the CLI should print JSON:

```python
result = runbook.execute(context)
print(result.to_json(indent=2))
raise SystemExit(0 if result.passed else 1)
```

## Tests

Runbooks are plain Python objects, so tests can inspect the context and result:

```python
def test_orders_export_runbook():
    context = {"files": ["orders.csv"]}

    result = runbook.execute(context)

    assert result.passed
    assert result.find("Check files").passed
```

## Airflow Or Another Scheduler

Keep scheduling outside the core runbook:

```python
def task_callable(**airflow_context):
    context = {
        "ds": airflow_context["ds"],
        "files": find_files_for_ds(airflow_context["ds"]),
    }

    runbook.run(context)
```

The Airflow adapter can be used when you want Airflow-specific exception handling, but the runbook itself should stay portable.

## Telemetry

Attach exporters when another system needs every result:

```python
from runbook import JsonlResultExporter

runbook.export_to(JsonlResultExporter("/var/log/runbook/results.jsonl"))
```

Custom exporters are just callables:

```python
def send_to_observability(result):
    client.send(result.to_dict(include_context=False))

runbook.export_to(send_to_observability)
```

Exporter failures are logged and do not change runbook status.

## Failure Formatting

Use `format_failure()` for human-readable errors:

```python
from runbook import format_failure

result = runbook.execute(context)

if result.failed:
    print(format_failure(result.error, result.context, result.name))
```

Common secret keys are redacted in formatted context output.

## Dependency Boundary

Keep integrations thin:

- loaders read external state and return data
- actions perform side effects
- runbooks describe execution order and checks
- schedulers decide when to run

This keeps the same runbook usable from local scripts, tests, services, and orchestrators.
