# Checks

Checks are small, composable predicates. They are the preferred alternative to expression strings.

## Built-in Checks

```python
from runbook import (
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

## Examples

```python
step("Files").require(not_empty("files"), "No files")
```

```python
step("Rows").require(gt("row_count", 0), "No rows")
```

```python
step("CSV").require(matches_any("files", "*.csv"), "CSV file is missing")
```

```python
step("Status").require(equals("response.status", 200), "API did not return 200")
```

Nested keys use dot notation and work with dictionaries or object attributes.

## Composing Checks

```python
from runbook import all_of, matches_any, not_empty

step("Files").require(
    all_of(not_empty("files"), matches_any("files", "*.csv")),
    "Valid CSV input is missing",
)
```

## Custom Checks

```python
from runbook import custom

has_large_file = custom(
    "has_large_file(files)",
    lambda context: any(file["size"] > 1000 for file in context["files"]),
)

step("Files").require(has_large_file, "No large file found")
```

Use `custom()` when a built-in check is too small or too generic.

## Legacy Expression Checks

`expect()` is still available:

```python
step("Rows").expect("row_count > 0", "No rows")
```

Prefer `require()` with built-in checks for new code. It is easier to test, document, and compose.
