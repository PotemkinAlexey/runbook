# Public API

This page documents the intended stable surface of `runbook`.

## Core

```python
from runbook import Runbook, Stage, Step, stage, step
```

- `Runbook(name=None)`: sequence of steps
- `stage(name)`: convenience constructor for `Stage`
- `step(name)`: convenience constructor for `Step`
- `Stage(name)`: group of steps and nested stages
- `Step(name)`: step class

Preferred style:

```python
Runbook("checks").add(step("Check").require(...))
```

Decorator style:

```python
@step("Load files", output="files")
def load_files(context):
    return ["daily.csv"]
```

## Checks

```python
from runbook import (
    Check,
    all_of,
    any_of,
    contains,
    custom,
    empty,
    equals,
    exists,
    gt,
    gte,
    lt,
    lte,
    matches_any,
    missing,
    not_,
    not_empty,
)
```

Checks are the preferred validation API.

## Actions and Context Helpers

```python
from runbook import external, if_, if_else, instant_log, lazy, log, raise_
```

`if_` and `if_else` are available for compatibility and advanced cases. Prefer step policies such as `skip_when`, `warn_when`, `fail_when`, and `require` for new code.

## Execution Results

```python
from runbook import RunbookResult, StepResult
```

Use `Runbook.execute()` to receive a `RunbookResult`.

## Declarative Runbooks

```python
from runbook import runbook_from_dict, runbook_from_file
```

Use these helpers to build runbooks from JSON/YAML-style dictionaries and files.

## Errors

```python
from runbook import RunbookFailedError, StepExecutionError
```

## Logging

```python
from runbook import RunbookLogger, configure_runbook_logging, get_runbook_logger
```

## Reporting

```python
from runbook import format_failure
```

## Observability

```python
from runbook import AsyncResultExporter, JsonlResultExporter, ResultExporter
```

Use `Runbook.export_to(...)` to attach result exporters for local files, telemetry bridges, or application-specific sinks.

## Registry

```python
from runbook import (
    Registry,
    get_registered_action,
    get_registered_check,
    list_registered_actions,
    list_registered_checks,
    load_registry_entry_points,
    register_action,
    register_check,
)
```

Use registries to expose reusable checks and actions by stable names without adding scheduler behavior.

## Extension Types

```python
from runbook import Action, Context, ContextModifier, Loader
```

Use these in integrations and custom extensions.

## Integrations

Integrations are imported from their own modules:

```python
from runbook.integrations.airflow import run_task
from runbook.integrations.files import glob_paths
from runbook.integrations.http import get_json
```

Framework-specific helpers should not be imported from the root `runbook` namespace.

## Legacy and Advanced API

```python
from runbook import safe_eval, validate_value
```

`safe_eval` and `Step.expect()` remain available, but new code should prefer declarative checks through `require()`.
