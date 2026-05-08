# Quickstart

This guide shows the smallest useful `runbook` workflow.

## 1. Define a Runbook

```python
from runbook import Runbook, configure_runbook_logging, matches_any, not_empty, step

configure_runbook_logging()

runbook = (
    Runbook("Daily input checks")
    .add(
        step("Check files")
        .set("files", ["daily.csv"])
        .require(not_empty("files"), "No files found")
        .require(matches_any("files", "*.csv"), "CSV file is missing")
    )
)
```

## 2. Execute It

```python
result = runbook.execute({})

if result.passed:
    print("ok")
```

`execute()` returns a structured result. It does not raise when a check fails.

## 3. Fail Fast

Use `run()` when failed checks should raise `RunbookFailedError`.

```python
runbook.run({})
```

## 4. Load Dynamic Data

Use `.load()` to compute context values at execution time.

```python
def load_files(context):
    return ["daily.csv"]

runbook = Runbook("files").add(
    step("Check files")
    .load("files", load_files)
    .require(not_empty("files"), "No files found")
)
```

## 5. Add Actions

Use `.then()` for side effects after the step passes.

```python
from runbook import log

step("Check files").require(not_empty("files")).then(
    log("Found {{ files|length }} files")
)
```
