import unittest

from runbook import RunbookFailedError, step
from runbook.schema import validate_value


class SchemaValidationTest(unittest.TestCase):
    def test_validate_schema_accepts_json_schema_subset(self):
        context = {"row": {"id": 1, "name": "orders"}}

        result = (
            step("schema")
            .validate_schema(
                "row",
                {
                    "type": "object",
                    "required": ["id", "name"],
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                },
            )
            .run(context)
        )

        self.assertTrue(result.passed)

    def test_validate_schema_fails_missing_field(self):
        with self.assertRaises(RunbookFailedError) as raised:
            step("schema").validate_schema("row", {"type": "object", "required": ["id"]}).run({"row": {}})

        self.assertEqual(raised.exception.condition, "schema(row)")
        self.assertIn("missing required field: id", raised.exception.message)

    def test_validate_value_accepts_callable(self):
        validate_value({"id": 1}, lambda value: value["id"] == 1)

    def test_validate_value_rejects_false_callable(self):
        with self.assertRaises(ValueError):
            validate_value({"id": 1}, lambda value: False)

    def test_validate_value_accepts_pydantic_v2_style_model(self):
        class RowModel:
            value = None

            @classmethod
            def model_validate(cls, value):
                cls.value = value

        validate_value({"id": 1}, RowModel)

        self.assertEqual(RowModel.value, {"id": 1})

    def test_validate_value_accepts_pydantic_v1_style_model(self):
        class RowModel:
            value = None

            @classmethod
            def parse_obj(cls, value):
                cls.value = value

        validate_value({"id": 1}, RowModel)

        self.assertEqual(RowModel.value, {"id": 1})


if __name__ == "__main__":
    unittest.main()
