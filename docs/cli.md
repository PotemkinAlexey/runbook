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

Nested stages are printed as a tree:

```text
Orders export
  - Pre-checks/
    - Check files
    - Check schema
  - Run export
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

It also prints a nested result tree:

```text
PASS Orders export
  PASS Pre-checks/
    PASS Check files
    PASS Check schema
  PASS Run export
```

Disable lifecycle logs with:

```bash
runbook run checks.py --quiet --context '{"items": [1, 2, 3]}'
```

## JSON Output

Use JSON output when integrating with CI/CD, cron wrappers, or another program:

```bash
runbook run checks.py --quiet --json --context '{"items": [1, 2, 3]}'
```

Include the final context when needed:

```bash
runbook run checks.py --quiet --json --include-context --context '{"items": [1, 2, 3]}'
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
