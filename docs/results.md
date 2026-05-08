# Execution Results

`runbook` has two execution modes.

## Structured Execution

Use `execute()` when embedding into another system.

```python
result = runbook.execute({})
```

`execute()` returns `RunbookResult`.

```python
if result.passed:
    ...

if result.failed:
    print(result.error)
```

Important fields:

- `name`: runbook name
- `status`: `passed` or `failed`
- `context`: final context dictionary
- `steps`: list of executed `StepResult` objects
- `error`: `RunbookFailedError` when failed

## Serialization

Results can be serialized for APIs, CLI output, and automation systems.

```python
data = result.to_dict()
payload = result.to_json()
```

Include the final context explicitly:

```python
payload = result.to_json(include_context=True)
```

## Strict Execution

Use `run()` when failure should raise.

```python
runbook.run({})
```

This is convenient in scripts, tests, schedulers, and systems where an exception should mark the task as failed.

## Step Results

Each step returns a `StepResult`.

Fields:

- `name`
- `status`: `passed`, `failed`, or `skipped`
- `message`: optional skip/failure message
- `warnings`: warnings collected from `warn_when`

## Formatting Failures

```python
from runbook import format_failure

result = runbook.execute(context)

if result.failed:
    print(format_failure(result.error, result.context, result.name))
```

Secrets in common keys like `token`, `password`, `secret`, and `api_key` are redacted.
