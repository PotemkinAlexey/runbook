# Pipeline Guide

This guide shows the recommended shape for embeddable data engineering runbooks.

The goal is not to build a scheduler. The goal is to make pipeline logic readable, testable, and easy to embed.

## Recommended Shape

Use stages for the major phases:

```python
from runbook import Runbook, stage, step

runbook = (
    Runbook("Orders export")
    .add(stage("Pre-checks"))
    .add(stage("Export"))
    .add(stage("Post-checks"))
)
```

A stage should describe intent. A step should do one clear thing.

## Parent Context

Every runbook receives a context dictionary:

```python
context = {
    "ds": "2026-05-09",
    "source": "orders",
}

result = runbook.execute(context)
```

By default, the same dictionary is shared across steps. This keeps integration simple and backward compatible.

## Inputs And Outputs

Prefer `publish()` for values produced by a step:

```python
step("Find files").publish("files", find_files)
```

Prefer `inputs()` for values required by a step:

```python
step("Read rows").inputs("files").publish("rows", read_rows)
```

This gives each step an explicit contract:

- what it needs
- what it produces
- where a missing dependency failed

## Checks

Use `require()` for validations that must pass:

```python
from runbook import check_row_count, check_schema, not_empty

(
    stage("Pre-checks")
    .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
    .add(step("Check schema").inputs("rows").require(check_schema("rows", ["id", "created_at"])))
    .add(step("Check rows").inputs("row_count").require(check_row_count("row_count", minimum=1)))
)
```

Use `warn_when()` for signals that should not fail the run:

```python
step("Check freshness").warn_when(is_late("loaded_at"), "Input is late")
```

Use `skip_when()` when a step should be skipped cleanly:

```python
step("Export").skip_when(empty("rows"), "Nothing to export")
```

## Full Example

```python
from runbook import Runbook, check_row_count, check_schema, not_empty, post_export_checks, stage, step

runbook = (
    Runbook("Orders export")
    .add(
        stage("Pre-checks")
        .add(step("Find files").publish("files", find_files))
        .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
        .add(step("Read rows").inputs("files").publish("rows", read_rows))
        .add(step("Count rows").inputs("rows").publish("row_count", lambda ctx: len(ctx["rows"])))
        .add(step("Check schema").inputs("rows").require(check_schema("rows", ["id", "created_at"])))
        .add(step("Check rows").inputs("row_count").require(check_row_count("row_count", minimum=1)))
    )
    .add(
        stage("Export").add(
            step("Build manifest")
            .inputs("files", "row_count")
            .publish("manifest", build_manifest)
            .then(export_manifest)
        )
    )
    .add(post_export_checks())
)
```

See `examples/orders_export.py` for a runnable version.

## Result Tree

The output keeps the same structure:

```text
PASS Orders export
  PASS Pre-checks/
    PASS Find files
    PASS Check files
    PASS Read rows
  PASS Export/
    PASS Build manifest
  PASS Post-checks/
    PASS Validate manifest
```

The JSON result also includes `path` on tree nodes:

```json
{
  "name": "Check files",
  "path": ["Orders export", "Pre-checks", "Check files"],
  "status": "passed"
}
```

## What To Avoid

Avoid hiding important behavior in large custom actions:

```python
step("Do everything").then(run_all_checks_and_export)
```

Prefer visible steps:

```python
stage("Pre-checks").add(step("Check files")).add(step("Check schema"))
```

Avoid using registry plugins, lazy providers, or parallel execution until the normal staged runbook is clear.

## When To Use Advanced Features

Use advanced features only when they solve a concrete problem:

- `lazy()` when a value is expensive and might not be needed.
- `scoped()` when a reusable stage should not mutate parent context.
- `continue_on_error()` when validation should collect all failures before reporting.
- `export_to()` when another system needs result telemetry.
- registry plugins when teams share reusable checks across packages.
