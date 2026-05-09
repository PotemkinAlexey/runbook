import json
import tempfile
import unittest
from pathlib import Path

from runbook import Registry, custom, runbook_from_dict, runbook_from_file


class DeclarativeRunbookTest(unittest.TestCase):
    def test_runbook_from_dict_builds_nested_runbook(self):
        spec = {
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
                                    "message": "No files found",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        result = runbook_from_dict(spec).execute({"files": ["orders.csv"]})

        self.assertTrue(result.passed)
        self.assertEqual(result.children[0].name, "Pre-checks")
        self.assertEqual(result.find("Check files").name, "Check files")

    def test_runbook_from_dict_returns_clear_failure(self):
        spec = {
            "name": "Orders export",
            "steps": [
                {
                    "name": "Check rows",
                    "require": [
                        {
                            "check": "check_row_count",
                            "key": "row_count",
                            "minimum": 1,
                            "message": "No rows found",
                        }
                    ],
                }
            ],
        }

        result = runbook_from_dict(spec).execute({"row_count": 0})

        self.assertTrue(result.failed)
        self.assertEqual(result.error.message, "No rows found")

    def test_runbook_from_dict_uses_registry_checks(self):
        registry = Registry()
        registry.register_check("positive", lambda key: custom(f"positive({key})", lambda ctx: ctx[key] > 0))
        spec = {
            "name": "registered",
            "steps": [
                {
                    "name": "Check count",
                    "require": [{"check": "positive", "args": ["count"]}],
                }
            ],
        }

        result = runbook_from_dict(spec, registry=registry).execute({"count": 1})

        self.assertTrue(result.passed)

    def test_runbook_from_dict_uses_registry_check_kwargs(self):
        registry = Registry()
        registry.register_check(
            "minimum",
            lambda key, value: custom(f"minimum({key}, {value})", lambda ctx: ctx[key] >= value),
        )
        spec = {
            "name": "registered",
            "steps": [
                {
                    "name": "Check count",
                    "require": [{"check": "minimum", "key": "count", "value": 2}],
                }
            ],
        }

        result = runbook_from_dict(spec, registry=registry).execute({"count": 2})

        self.assertTrue(result.passed)

    def test_runbook_from_dict_supports_mixed_children(self):
        spec = {
            "name": "tree",
            "children": [
                {
                    "type": "stage",
                    "name": "group",
                    "children": [
                        {
                            "name": "leaf",
                            "require": [{"check": "not_empty", "args": ["items"]}],
                        }
                    ],
                }
            ],
        }

        result = runbook_from_dict(spec).execute({"items": [1]})

        self.assertTrue(result.passed)
        self.assertEqual(result.children[0].children[0].name, "leaf")

    def test_runbook_from_dict_rejects_unknown_check(self):
        spec = {
            "name": "bad",
            "steps": [{"name": "Check", "require": [{"check": "does_not_exist"}]}],
        }

        with self.assertRaises(KeyError):
            runbook_from_dict(spec)

    def test_runbook_from_dict_rejects_invalid_top_level_shape(self):
        with self.assertRaises(TypeError):
            runbook_from_dict([])

    def test_runbook_from_dict_rejects_missing_step_name(self):
        with self.assertRaises(ValueError):
            runbook_from_dict({"name": "bad", "steps": [{"require": [{"check": "not_empty", "args": ["items"]}]}]})

    def test_runbook_from_dict_rejects_non_list_inputs(self):
        spec = {"name": "bad", "steps": [{"name": "Check", "inputs": "items"}]}

        with self.assertRaises(TypeError):
            runbook_from_dict(spec)

    def test_runbook_from_file_loads_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir, "checks.json")
            path.write_text(
                json.dumps(
                    {
                        "name": "json",
                        "steps": [
                            {
                                "name": "Check items",
                                "require": [{"check": "not_empty", "args": ["items"]}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = runbook_from_file(str(path)).execute({"items": [1]})

        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
