# Quickstart

This page shows the shortest path from zero to a useful embedded runbook.

## Install

For local development from this repository:

```bash
pip install -e '.[dev]'
```

In an application, install the package the same way you install any Python dependency.

## 1. Create One Check

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("Daily input checks").add(
    step("Check files").require(not_empty("files"), "No files found")
)
```

A `Runbook` contains executable nodes. A `Step` is the smallest node. `require()` attaches a check that must pass.

## 2. Run It With Context

```python
context = {"files": ["daily.csv"]}
result = runbook.execute(context)

print(result.status)
```

`context` is a normal dictionary. Checks read from it, and steps can write to it.

`execute()` returns a structured result and does not raise for normal check failures. That makes it the best default for embedding.

## 3. Handle Failure

```python
result = runbook.execute({"files": []})

if result.failed:
    print(result.error.message)
```

Use `run()` when a failed runbook should raise:

```python
runbook.run({"files": []})
```

Use `execute()` in services, APIs, CLIs, and schedulers that want to inspect a result. Use `run()` in scripts or tests where an exception is the desired behavior.

## 4. Compute Values

Use `publish()` for explicit step outputs:

```python
def find_files(context):
    return ["daily.csv"]

runbook = (
    Runbook("Daily input checks")
    .add(step("Find files").publish("files", find_files))
    .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
)
```

`inputs("files")` documents and validates that the step needs `context["files"]`.

## 5. Group Steps

Use `stage()` when the runbook grows beyond a few steps:

```python
from runbook import Runbook, not_empty, stage, step

runbook = (
    Runbook("Orders export")
    .add(
        stage("Pre-checks")
        .add(step("Find files").publish("files", find_files))
        .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
    )
    .add(step("Export").inputs("files").then(export_files))
)
```

The result preserves this tree, so logs, CLI output, JSON, and failure messages stay readable.

## 6. Print Useful Logs

```python
from runbook import configure_runbook_logging

configure_runbook_logging()
runbook.run({"files": ["daily.csv"]})
```

Example output:

```text
runbook | start: Daily input checks (1 steps)
runbook | step 1/1 start: Check files
runbook | check require: not_empty(files)
runbook | step pass: Check files
runbook | pass: Daily input checks (1 steps)
```

## Recommended Default

For most production integrations, start with this subset:

- `Runbook`
- `stage`
- `step`
- `inputs`
- `publish`
- `require`
- `execute`

Keep `lazy`, `scoped`, registry plugins, and parallel execution for cases where the basic shape is not enough.
