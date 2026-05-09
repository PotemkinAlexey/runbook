# Troubleshooting And FAQ

This page covers common mistakes and integration questions.

## `Missing required input`

`inputs()` is checked before the step runs its loaders, publishers, lazy values, or actions.

This fails:

```python
step("Find files").inputs("files").publish("files", find_files)
```

The step says it needs `files` before it creates `files`.

Use two steps:

```python
step("Find files").publish("files", find_files)
step("Check files").inputs("files").require(not_empty("files"), "No files found")
```

Or use a single step without `inputs()` when it creates and checks the value itself:

```python
step("Find files").publish("files", find_files).require(not_empty("files"), "No files found")
```

## Decorated Step Cannot Find An Argument

Function arguments on `@step` are inferred inputs:

```python
@step("Read rows", output="rows")
def read_rows(files):
    return warehouse.read(files)
```

This requires `context["files"]` to exist before the step runs.

Fix by adding a producer step first:

```python
@step("Find files", output="files")
def find_files():
    return ["orders.csv"]

runbook = Runbook("Orders").add(find_files).add(read_rows)
```

Use `context` or `ctx` when you need the whole context dictionary:

```python
@step("Read rows", output="rows")
def read_rows(context, files):
    return warehouse.read(files, ds=context["ds"])
```

## `execute()` Or `run()`?

Use `execute()` when embedding:

```python
result = runbook.execute(context)
if result.failed:
    return result.to_dict()
```

Use `run()` when failure should raise:

```python
runbook.run(context)
```

Most services, APIs, and CLIs should use `execute()`. Tests and scheduler tasks often use `run()`.

## Why Did My Context Change?

Context is shared by default:

```python
context = {}
Runbook("x").add(step("Set").set("value", 1)).execute(context)
assert context["value"] == 1
```

Use `stage(...).scoped()` when a reusable stage should not write back to parent context:

```python
stage("Optional checks").scoped().add(step("Set temp").set("temp", 1))
```

## YAML File Does Not Load

JSON support is built in. YAML support requires PyYAML:

```bash
pip install pyyaml
```

Use JSON when you need zero optional dependencies.

## Declarative Runbook Cannot Use My Check

Declarative files can call built-in checks or checks registered in a `Registry`.

```python
registry = Registry()
registry.register_check("positive", positive_check)

runbook = runbook_from_file("checks.json", registry=registry)
```

The config should contain only the registered name:

```json
{"check": "positive", "args": ["row_count"]}
```

Do not put Python import strings or lambdas into JSON/YAML.

## Exporter Did Not Flush Before Process Exit

Synchronous exporters run inline. Async exporters use a background thread.

Use a context manager:

```python
with AsyncResultExporter(JsonlResultExporter("results.jsonl")) as exporter:
    runbook.export_to(exporter)
    runbook.execute(context)
```

Or call `flush()` / `close()` explicitly:

```python
exporter.flush()
exporter.close()
```

## My Stage Should Run All Checks

Stages fail fast by default. Use `continue_on_error()` for validation stages:

```python
stage("Validations").continue_on_error().add(check_a).add(check_b)
```

The stage will still report failure if any child fails.

## Should I Use `load()`, `publish()`, Or `@step`?

Recommended defaults:

- use `publish()` in fluent runbooks
- use `@step(..., output="key")` when ordinary functions are clearer
- use `load()` only for older code or compatibility
- use `lazy()` only for expensive values that might not be read

## Is This Becoming An Orchestrator?

It should not. `runbook` should stay local and embeddable.

If you need scheduling, workers, persistent run history, queues, distributed execution, or retry-after-restart, use an orchestrator and run `runbook` inside it.

Good integration:

```python
def airflow_task(**context):
    runbook.run(context)
```

Bad direction:

```python
runbook.schedule(...).deploy(...)
```

Keep scheduling outside the library.
