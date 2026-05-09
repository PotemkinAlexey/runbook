# Cheat Sheet

Use this page when you know what you want to do but not which API to choose.

## Build A Runbook

| Goal | Use |
| --- | --- |
| Create a runbook | `Runbook("Name")` |
| Add one operation | `.add(step("Name"))` |
| Turn a function into a step | `@step("Name", output="key")` |
| Group operations | `.add(stage("Name").add(...))` |
| Turn a function into a stage | `@stage("Name")` returning steps/stages |
| Run and inspect result | `.execute(context)` |
| Run and raise on failure | `.run(context)` |

## Move Data Through Context

| Goal | Use |
| --- | --- |
| Put a constant into context | `step("Load").set("key", value)` |
| Compute a value immediately in the step | `step("Load").publish("key", fn)` |
| Compute a value with old compatibility API | `step("Load").load("key", fn)` |
| Declare required input | `step("Use").inputs("key")` |
| Delay expensive computation until first read | `step("Prepare").lazy("key", fn)` |

Recommended default: use `publish()` for new code and `inputs()` on consuming steps.

```python
step("Find files").publish("files", find_files)
step("Read rows").inputs("files").publish("rows", read_rows)
```

Decorator equivalent:

```python
@step("Find files", output="files")
def find_files(context):
    return ["daily.csv"]
```

Function arguments are read from context and become inferred inputs:

```python
@step("Read rows", output="rows")
def read_rows(files):
    return [{"file": files[0]}]
```

For multiple outputs, return a dict or tuple/list:

```python
@step("Read rows", outputs=["rows", "row_count"])
def read_rows(context):
    rows = [{"id": 1}]
    return rows, len(rows)
```

Group decorated steps with `@stage`:

```python
@stage("Pre-checks")
def pre_checks():
    return [find_files, read_rows]
```

## Validate Data

| Goal | Use |
| --- | --- |
| Required non-empty value | `require(not_empty("key"), "message")` |
| Numeric threshold | `require(gt("row_count", 0), "message")` |
| Exact value | `require(equals("status", "ok"), "message")` |
| File pattern in a list | `require(matches_any("files", "*.csv"), "message")` |
| Custom predicate | `require(custom("name", fn), "message")` |
| Structured object/schema | `validate_schema("key", schema)` |

## Control Behavior

| Goal | Use |
| --- | --- |
| Skip cleanly | `.skip_when(check, "message")` |
| Warn but continue | `.warn_when(check, "message")` |
| Fail when condition matches | `.fail_when(check, "message")` |
| Retry transient failure | `.retry(times=3, delay=5)` |
| Limit runtime | `.timeout(seconds=30)` |
| Run all child validations | `stage("Validations").continue_on_error()` |
| Keep stage writes local | `stage("Try").scoped()` |

## Side Effects

| Goal | Use |
| --- | --- |
| Run side effect after checks pass | `.then(action)` |
| Log a rendered message | `.then(log("Found {{ files|length }} files"))` |
| Notify on runbook failure | `Runbook(...).notify_on_failure(action)` |
| Export final result | `Runbook(...).export_to(exporter)` |

Keep side effects in actions. Keep checks in `require()`, `warn_when()`, and `fail_when()`.

## Choose Execution Mode

Use `execute()` when embedding:

```python
result = runbook.execute(context)
if result.failed:
    return result.to_dict()
```

Use `run()` when failure should raise:

```python
runbook.run(context)
```

Use CLI when another system only needs a process:

```bash
runbook run checks.py --context '{"files": ["daily.csv"]}'
```

## Avoid Common Mistakes

Do not put `inputs("key")` on the same step that creates `key`:

```python
# Avoid
step("Find files").inputs("files").publish("files", find_files)
```

Use this instead:

```python
step("Find files").publish("files", find_files)
step("Check files").inputs("files").require(not_empty("files"))
```

Do not start with plugins or registry for local code. Start with plain Python functions.
