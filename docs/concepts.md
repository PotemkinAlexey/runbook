# Core Concepts

## Runbook

A `Runbook` is a named sequence of steps.

```python
from runbook import Runbook

runbook = Runbook("Daily checks")
```

Runbooks are portable. The core package does not require Airflow or any other scheduler.

## Step

A `Step` loads data, evaluates checks, and runs actions.

```python
from runbook import not_empty, step

step("Check files").require(not_empty("files"))
```

## Context

The context is a mutable dictionary shared across steps.

```python
context = {"ds": "2026-05-09"}
result = runbook.execute(context)
```

Steps can add context values:

```python
step("Load").set("files", ["daily.csv"])
```

Or compute values:

```python
step("Load").load("files", lambda context: ["daily.csv"])
```

## Checks

Checks are predicates over the context.

```python
from runbook import gt, not_empty

(
    step("Validate")
    .require(not_empty("files"), "No files found")
    .require(gt("row_count", 0), "No rows found")
)
```

## Policies

Policies replace hand-written `if/else`.

```python
from runbook import empty, gt

(
    step("Process")
    .skip_when(empty("files"), "Nothing to process")
    .warn_when(gt("delay_minutes", 30), "Input is late")
    .fail_when(gt("error_count", 0), "Errors found")
)
```

## Actions

Actions run after a step passes its checks.

```python
from runbook import log

step("Report").then(log("Done"))
```

Actions receive the context and can perform side effects.

## Execution Logging

Runbook emits lifecycle logs through the `runbook` logger:

```python
from runbook import configure_runbook_logging

configure_runbook_logging()
runbook.run({})
```

Example output:

```text
runbook | start: Daily checks (1 steps)
runbook | step 1/1 start: Check files
runbook | check require: not_empty(files)
runbook | step pass: Check files
runbook | pass: Daily checks (1 steps)
```
