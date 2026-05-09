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

    def test_runbook_from_dict_supports_step_controls(self):
        spec = {
            "name": "controls",
            "steps": [
                {
                    "name": "Skip empty",
                    "skip_when": [{"check": "empty", "args": ["items"], "message": "No items"}],
                },
                {
                    "name": "Warn high delay",
                    "warn_when": [{"check": "gt", "args": ["delay", 10], "message": "Late"}],
                },
                {
                    "name": "Fail on errors",
                    "fail_when": [{"check": "gt", "args": ["errors", 0], "message": "Errors found"}],
                },
            ],
        }

        result = runbook_from_dict(spec).execute({"items": [], "delay": 20, "errors": 0})

        self.assertTrue(result.passed)
        self.assertTrue(result.find("Skip empty").skipped)
        self.assertTrue(result.find("Warn high delay").warned)

    def test_runbook_from_dict_supports_retry_and_timeout(self):
        spec = {
            "name": "controls",
            "steps": [
                {
                    "name": "Check items",
                    "retry": {"times": 2, "delay": 0},
                    "timeout": 1,
                    "require": [{"check": "not_empty", "args": ["items"]}],
                }
            ],
        }

        runbook = runbook_from_dict(spec)

        self.assertEqual(runbook.steps[0].retry_attempts, 2)
        self.assertEqual(runbook.steps[0].timeout_seconds, 1)
        self.assertTrue(runbook.execute({"items": [1]}).passed)

    def test_runbook_from_dict_supports_stage_controls(self):
        spec = {
            "name": "controls",
            "stages": [
                {
                    "name": "Validation",
                    "continue_on_error": True,
                    "retry": 2,
                    "timeout": 1,
                    "warn_when": [{"check": "gt", "args": ["delay", 10], "message": "Late"}],
                    "steps": [
                        {
                            "name": "Bad",
                            "require": [{"check": "not_empty", "args": ["missing"], "message": "Missing"}],
                        },
                        {"name": "After"},
                    ],
                }
            ],
        }

        result = runbook_from_dict(spec).execute({"delay": 20})
        stage_result = result.children[0]

        self.assertTrue(result.failed)
        self.assertEqual([child.name for child in stage_result.children], ["Bad", "After"])
        self.assertTrue(stage_result.warned)

    def test_runbook_from_dict_supports_scoped_stage(self):
        spec = {
            "name": "scope",
            "stages": [
                {
                    "name": "Scoped",
                    "scoped": True,
                    "steps": [{"name": "Set value"}],
                }
            ],
        }

        runbook = runbook_from_dict(spec)

        self.assertTrue(runbook.steps[0].scoped_context_enabled)

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
