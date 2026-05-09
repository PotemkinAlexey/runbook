# runbook

`runbook` is a small embeddable Python framework for describing operational checks and data pipeline guardrails without scattering `if/else` logic through application code.

It is not a scheduler. It does not own workers, queues, DAG parsing, deployments, or calendars. You run it inside the process you already have: a CLI command, API endpoint, cron job, Airflow task, notebook, test suite, or service.

## The Idea

Instead of writing this:

```python
files = find_files()
if not files:
    raise RuntimeError("No files found")

rows = read_rows(files)
if len(rows) == 0:
    raise RuntimeError("No rows found")

export(rows)
```

Describe the workflow:

```python
from runbook import Runbook, check_row_count, not_empty, stage, step

runbook = (
    Runbook("Orders export")
    .add(
        stage("Pre-checks")
        .add(step("Find files").publish("files", find_files))
        .add(step("Check files").inputs("files").require(not_empty("files"), "No files found"))
        .add(step("Read rows").inputs("files").publish("rows", read_rows))
        .add(step("Check rows").publish("row_count", lambda ctx: len(ctx["rows"])).require(check_row_count()))
    )
    .add(step("Export").inputs("rows").then(export_rows))
)
```

The result is a structured execution tree that can be printed, serialized, exported, or inspected by another system.

## Who It Is For

- Data engineers who need repeatable checks before and after pipeline steps.
- Platform engineers who want a tiny embeddable execution layer without a scheduler dependency.
- Application developers who want readable operational guardrails.
- LLM-assisted workflows where generated code should produce predictable stages and checks instead of ad hoc branching.

## How To Learn It

1. Read [Quickstart](quickstart.md) for the smallest useful example.
2. Read [Pipeline Guide](pipelines.md) for the recommended production shape.
3. Use [Recipes](recipes.md) when adding a specific behavior.
4. Keep [Advanced Usage](advanced.md) for later.

Most users only need `Runbook`, `stage`, `step`, `inputs`, `publish`, and `require`.
