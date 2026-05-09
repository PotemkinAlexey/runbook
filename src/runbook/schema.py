"""Schema validation helpers."""

from __future__ import annotations

from typing import Any, Callable


def validate_value(value: Any, schema: Any) -> None:
    """Validate a value using a callable, Pydantic model, or small JSON-schema subset."""
    if callable(schema) and not _looks_like_pydantic_model(schema):
        result = schema(value)
        if result is False:
            raise ValueError("schema callable returned False")
        return

    if hasattr(schema, "model_validate"):
        schema.model_validate(value)
        return

    if hasattr(schema, "parse_obj"):
        schema.parse_obj(value)
        return

    if isinstance(schema, dict):
        _validate_json_schema_subset(value, schema)
        return

    raise TypeError("schema must be a callable, Pydantic model, or schema dict")


def _looks_like_pydantic_model(value: Any) -> bool:
    return hasattr(value, "model_validate") or hasattr(value, "parse_obj")


def _validate_json_schema_subset(value: Any, schema: dict[str, Any]) -> None:
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        raise ValueError(f"expected type {expected_type}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"missing required field: {key}")

        properties = schema.get("properties", {})
        for key, property_schema in properties.items():
            if key in value:
                _validate_json_schema_subset(value[key], property_schema)
        return

    if isinstance(value, list) and "items" in schema:
        for item in value:
            _validate_json_schema_subset(item, schema["items"])


def _matches_type(value: Any, expected_type: str) -> bool:
    type_map: dict[str, Callable[[Any], bool]] = {
        "array": lambda item: isinstance(item, list),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "string": lambda item: isinstance(item, str),
    }
    validator = type_map.get(expected_type)
    if validator is None:
        raise ValueError(f"unsupported schema type: {expected_type}")
    return validator(value)
