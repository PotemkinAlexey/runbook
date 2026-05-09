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

## Stage

A `Stage` groups steps and nested stages into a readable execution tree.

```python
from runbook import Runbook, stage, step

runbook = (
    Runbook("Orders export")
    .add(
        stage("Pre-checks")
        .add(step("Check files"))
        .add(step("Check schema"))
    )
    .add(step("Run export"))
    .add(
        stage("Post-checks")
        .add(step("Validate manifest"))
    )
)
```

Stages execute children in order and return nested `StageResult` objects.

Stages support the same core controls as steps:

```python
(
    stage("Pre-checks")
    .retry(times=2)
    .timeout(seconds=30)
    .skip_when(...)
    .warn_when(...)
    .fail_when(...)
)
```

Use `continue_on_error()` when all children should run and the stage should report failure at the end:

```python
stage("Validations").continue_on_error()
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

Use `inputs()` and `publish()` when a step has explicit dependencies and outputs:

```python
step("Find files").publish("files", find_files)

(
    step("Build manifest")
    .inputs("files")
    .publish("manifest", build_manifest)
)
```

## Checks

Checks are predicates over the context.

See [Public API](api.md) for the stable import surface.

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

Retry transient failures:

```python
step("Check API").retry(times=3, delay=5).require(...)
```

Limit execution time:

```python
step("Check API").timeout(seconds=30).require(...)
```

## Actions

Actions run after a step passes its checks.

```python
from runbook import log

step("Report").then(log("Done"))
```

Actions receive the context and can perform side effects.

Messages and integration paths use Jinja2 templates. Reused template strings are compiled once and cached by the library.

## Expand

Use `expand()` when the same sub-steps should run for each item in a context list.

```python
runbook = Runbook("items").add(step("Load").set("items", [1, 2, 3]))

with runbook.expand("items") as each:
    each.add(step("Check item").require(gt("item", 0)))
```

The context manager form resets expansion state if an exception happens while defining expanded steps.

Expanded items can run in parallel when each item is independent:

```python
with runbook.expand("items", parallel=True, max_workers=8) as each:
    each.add(step("Check item").require(gt("item", 0)))
```

Parallel expanded steps receive a copy of the parent context plus `item`. Item contexts are not merged back into the parent context.

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

## Parallel Execution

Use `execute_parallel()` for independent top-level steps that mostly perform I/O.

```python
result = runbook.execute_parallel({}, max_workers=4)
```

Parallel execution runs each top-level step with a copy of the initial context, then merges successful step contexts back in step order. Use regular `execute()` when steps depend on data produced by previous steps.
