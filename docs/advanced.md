# Advanced Usage

Most runbooks do not need this page. Start with [Quickstart](quickstart.md) and [Pipeline Guide](pipelines.md), then come here when a concrete problem appears.

## Lazy Values

Use `lazy()` when loading a value is expensive and the value might not be needed.

```python
step("Prepare").lazy("files", find_files)
step("Check files").require(not_empty("files"), "No files found")
```

The loader runs the first time a check or step reads `files`.

Do not use `inputs("files")` on the same step that creates `files`; inputs are validated before step modifiers run. Put `inputs()` on the next step.

## Scoped Stages

By default, context mutations are shared. Use `scoped()` when a reusable stage should read parent context but keep its own mutations local:

```python
stage("Try optional validation").scoped().add(
    step("Load temporary data").publish("temp_rows", load_temp_rows)
)
```

Use this for reusable blocks that should not leak temporary values into the parent context.

## Continue On Error

Use `continue_on_error()` when all children should run even if one fails:

```python
stage("Validations").continue_on_error().add(step("Check A")).add(step("Check B"))
```

The stage reports failure at the end if any child failed.

## Parallel Execution

Use top-level `execute_parallel()` only for independent top-level nodes:

```python
result = runbook.execute_parallel(context, max_workers=4)
```

Each node receives a copy of the initial context. Successful contexts are merged back in original order.

Use parallel `expand()` for independent item checks:

```python
with runbook.expand("items", parallel=True, max_workers=8) as each:
    each.add(step("Check item").require(gt("item.size", 0)))
```

Parallel expanded item contexts are not merged back into the parent context.

## Schema Validation

Use `validate_schema()` for structured values:

```python
step("Validate row").validate_schema(
    "row",
    {
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "integer"}},
    },
)
```

The schema can be:

- a callable
- a Pydantic v2 model with `model_validate`
- a Pydantic v1 model with `parse_obj`
- a small JSON-schema-like dictionary

Pydantic stays optional. `runbook` calls the model method when the model object provides it, but does not require Pydantic as a core dependency.

## Registry And Plugins

Use the registry when teams share reusable checks or actions by name:

```python
from runbook import get_registered_check, register_check

@register_check("between")
def between(key, low, high):
    return custom(f"between({key}, {low}, {high})", lambda ctx: low <= ctx[key] <= high)

step("Validate").require(get_registered_check("between", "count", 1, 10))
```

External packages can expose registry plugins:

```toml
[project.entry-points."runbook.plugins"]
company_checks = "company_checks.runbook_plugin:register"
```

Load them explicitly:

```python
from runbook import load_registry_entry_points

load_registry_entry_points()
```

Plugins are not loaded automatically on import.

## Legacy Expression Checks

`expect()` remains available:

```python
step("Rows").expect("row_count > 0", "No rows")
```

Prefer `require()` with checks for new code. Checks are easier to test, compose, document, and register.
