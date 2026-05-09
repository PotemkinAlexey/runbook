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

Requirement fields:

- `check`: check name
- `args`: positional arguments
- any other field becomes a keyword argument
- `message`: failure message

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
