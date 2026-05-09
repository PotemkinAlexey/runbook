# Declarative Runbooks

Declarative runbooks let you describe checks in JSON or YAML while still executing through the same `Runbook`, `Stage`, and `Step` core.

Use this when users should write checks without Python code. Keep Python for custom loaders, actions, and complex integration logic.

## JSON Example

```json
{
  "name": "Orders export",
  "stages": [
    {
      "name": "Pre-checks",
      "steps": [
        {
          "name": "Check files",
          "inputs": ["files"],
          "require": [
            {
              "check": "not_empty",
              "args": ["files"],
              "message": "No files found"
            }
          ]
        },
        {
          "name": "Check rows",
          "inputs": ["row_count"],
          "require": [
            {
              "check": "check_row_count",
              "key": "row_count",
              "minimum": 1,
              "message": "No rows found"
            }
          ]
        }
      ]
    }
  ]
}
```

Run it from Python:

```python
from runbook import runbook_from_file

runbook = runbook_from_file("orders.json")
result = runbook.execute({"files": ["orders.csv"], "row_count": 10})
```

Run it from CLI:

```bash
runbook run orders.json --context '{"files": ["orders.csv"], "row_count": 10}'
```

## YAML

YAML files use the same structure:

```yaml
name: Orders export
stages:
  - name: Pre-checks
    steps:
      - name: Check files
        inputs: [files]
        require:
          - check: not_empty
            args: [files]
            message: No files found
```

YAML support uses PyYAML when it is installed. JSON support has no optional dependency.

Install the optional YAML extra when you want YAML files:

```bash
pip install "runbook[yaml]"
```

## Supported Shape

Top-level fields:

- `name`: runbook name
- `steps`: list of step specs
- `stages`: list of stage specs
- `children`: mixed list of stages and steps

Stage fields:

- `name`
- `steps`
- `stages`
- `children`

Step fields:

- `name`
- `inputs`
- `require`
- `skip_when`
- `warn_when`
- `fail_when`
- `validate_schema`
- `retry`
- `timeout`

Stage fields:

- `name`
- `steps`
- `stages`
- `children`
- `skip_when`
- `warn_when`
- `fail_when`
- `retry`
- `timeout`
- `continue_on_error`
- `fail_fast`
- `scoped`

Requirement fields:

- `check`: check name
- `args`: positional arguments
- any other field becomes a keyword argument
- `message`: failure message

## Controls

Step and stage policies use the same check shape as `require`.

```yaml
name: Orders export
stages:
  - name: Validations
    continue_on_error: true
    warn_when:
      - check: gt
        args: [delay_minutes, 30]
        message: Input is late
    steps:
      - name: Check files
        inputs: [files]
        retry:
          times: 2
          delay: 1
        timeout: 30
        skip_when:
          - check: empty
            args: [files]
            message: No files to process
        require:
          - check: not_empty
            args: [files]
            message: No files found
```

`retry` can also be a number:

```yaml
retry: 3
```

## Schema Validation

Declarative steps can validate structured values with the built-in JSON-schema-like subset:

```yaml
name: Schema checks
steps:
  - name: Validate row
    validate_schema:
      - key: row
        schema:
          type: object
          required: [id]
          properties:
            id:
              type: integer
```

For Pydantic models, use the Python DSL. Declarative files should stay portable and avoid Python import strings.

## Checks

Declarative runbooks can call built-in checks:

```yaml
require:
  - check: not_empty
    args: [files]
```

They can also call Registry checks:

```python
from runbook import Registry, custom, runbook_from_file

registry = Registry()
registry.register_check("positive", lambda key: custom(f"positive({key})", lambda ctx: ctx[key] > 0))

runbook = runbook_from_file("checks.json", registry=registry)
```

## Design Boundary

Declarative files describe wiring and checks. They should not contain arbitrary Python imports, lambdas, scheduler behavior, or complex control flow.

Use the Python DSL when behavior needs real code.
