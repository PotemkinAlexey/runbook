# runbook

Embeddable Python toolkit for describing operational checks, data loading, and failure handling without hand-written control flow.

`runbook` is not a scheduler and not an Airflow replacement. It is a small execution layer that you can embed into a CLI command, API endpoint, cron job, Airflow task, test suite, or any other Python process.

## Install

```bash
pip install -e .
```

## Quick Example

```python
from runbook import Runbook, configure_runbook_logging, format_failure, log, matches_any, not_empty, step

configure_runbook_logging()

checks = (
    Runbook("Daily input checks")
    .add(
        step("Check files")
        .set("files", ["daily.csv"])
        .require(not_empty("files"), "No files found")
        .require(matches_any("files", "*.csv"), "CSV file is missing")
        .then(log("Found {{ files|length }} files"))
    )
)

result = checks.execute({})

if result.failed:
    print(format_failure(result.error, result.context, result.name))
```

Use `run()` when failures should raise immediately:

```python
checks.run({})
```

Use `execute()` when embedding into another system and you need a structured result:

```python
result = checks.execute({})

if result.failed:
    ...
```

## CLI

Create `checks.py`:

```python
from runbook import Runbook, not_empty, step

runbook = Runbook("local").add(
    step("Check input").require(not_empty("items"), "items are required")
)
```

Run it:

```bash
runbook validate checks.py
runbook list checks.py
runbook run checks.py --context '{"items": [1, 2, 3]}'
```

## Documentation

- [Quickstart](docs/quickstart.md)
- [Core Concepts](docs/concepts.md)
- [Checks](docs/checks.md)
- [Execution Results](docs/results.md)
- [Public API](docs/api.md)
- [CLI](docs/cli.md)
- [Integrations](docs/integrations.md)
- [Recipes](docs/recipes.md)
- [Extending runbook](docs/extending.md)

Build the docs site locally:

```bash
mkdocs serve
```

## Current Status

This is an early library API. The core direction is stable:

- portable core with no Airflow dependency
- declarative checks instead of manual `if/else`
- adapters for external systems
- CLI support
- structured results for embedding

## License

MIT
