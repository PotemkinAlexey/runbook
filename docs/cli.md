# CLI

The CLI lets you run runbooks from a terminal or from automation systems that only need a process exit code.

## File Format

A runbook file must expose one of:

- `runbook`
- `checks`
- `build_runbook()`

Example:

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("local").add(
    step("Check input").require(not_empty("items"), "items are required")
)
```

## Validate

```bash
runbook validate checks.py
```

This loads the file and verifies that it exposes a `Runbook`.

## List Steps

```bash
runbook list checks.py
```

## Run

```bash
runbook run checks.py --context '{"items": [1, 2, 3]}'
```

`runbook run` prints step lifecycle logs by default:

```text
runbook | start: local (1 steps)
runbook | step 1/1 start: Check input
runbook | check require: not_empty(items)
runbook | step pass: Check input
runbook | pass: local (1 steps)
```

Disable lifecycle logs with:

```bash
runbook run checks.py --quiet --context '{"items": [1, 2, 3]}'
```

Exit codes:

- `0`: passed
- `1`: runbook failed
- `2`: command-line usage error

## Context

Context is passed as a JSON object.

```bash
runbook run checks.py --context '{"ds": "2026-05-09", "items": [1]}'
```
