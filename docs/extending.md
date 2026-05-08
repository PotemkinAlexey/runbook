# Extending runbook

`runbook` is designed to grow through small functions.

## Loader

A loader receives context and returns a value.

```python
def load_value(context):
    return 42

step("Load").load("answer", load_value)
```

Factory style is usually better for integrations:

```python
def read_json(path):
    def loader(context):
        ...
    return loader
```

## Action

An action receives context and performs a side effect.

```python
def print_context(context):
    print(context)

step("Report").then(print_context)
```

Factory style:

```python
def send_message(channel, message):
    def action(context):
        ...
    return action
```

## Check

Use `custom()` for one-off checks.

```python
from runbook import custom

positive_balance = custom("positive_balance(balance)", lambda context: context["balance"] > 0)
```

For reusable checks, return a `Check`.

```python
from runbook import Check

def between(key, low, high):
    return Check(
        f"between({key}, {low}, {high})",
        lambda context: low <= context[key] <= high,
    )
```

## Integration Module Shape

A typical integration module should expose:

- loaders for reading external state
- actions for side effects
- optional adapter runners for framework-specific exception handling

Keep framework-specific behavior out of the core package.
