# runbook

Embeddable Python toolkit for describing operational checks, data loading, and failure handling without hand-written control flow.

`runbook` is not a scheduler and not an Airflow replacement. It is a small execution layer that can run inside a CLI command, API endpoint, cron job, Airflow task, test suite, or any other Python process.

## Example

```python
from runbook import Runbook, configure_runbook_logging, matches_any, not_empty, step

configure_runbook_logging()

checks = (
    Runbook("Daily input checks")
    .add(
        step("Check files")
        .set("files", ["daily.csv"])
        .require(not_empty("files"), "No files found")
        .require(matches_any("files", "*.csv"), "CSV file is missing")
    )
)

checks.run({})
```

## Start Here

- [Quickstart](quickstart.md)
- [Core Concepts](concepts.md)
- [Recipes](recipes.md)
