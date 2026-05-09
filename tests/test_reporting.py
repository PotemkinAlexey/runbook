import unittest

from runbook import Runbook, RunbookFailedError, format_failure, stage, step
from runbook.reporting import format_result_tree, format_runbook_tree


class ReportingTest(unittest.TestCase):
    def test_format_failure_includes_core_fields_and_context(self):
        error = RunbookFailedError("Load", "not_empty(files)", "No files")

        report = format_failure(error, {"files": [], "token": "abc"}, runbook_name="Daily")

        self.assertIn("Runbook: Daily", report)
        self.assertIn("Step: Load", report)
        self.assertIn("Condition: not_empty(files)", report)
        self.assertIn("Message: No files", report)
        self.assertIn("files: []", report)
        self.assertIn("token: ***", report)
        self.assertNotIn("abc", report)

    def test_format_failure_truncates_long_values(self):
        error = RunbookFailedError("Load", "check", "failed")

        report = format_failure(error, {"payload": "x" * 20}, max_value_length=10)

        self.assertIn("payload: 'xxxxxx...", report)

    def test_format_runbook_tree_shows_nested_stages(self):
        runbook = Runbook("tree").add(stage("group").add(step("leaf"))).add(step("after"))

        report = format_runbook_tree(runbook)

        self.assertIn("tree", report)
        self.assertIn("  - group/", report)
        self.assertIn("    - leaf", report)
        self.assertIn("  - after", report)

    def test_format_result_tree_shows_nested_statuses(self):
        result = Runbook("tree").add(stage("group").add(step("leaf"))).execute({})

        report = format_result_tree(result)

        self.assertIn("PASS tree", report)
        self.assertIn("  PASS group/", report)
        self.assertIn("    PASS leaf", report)

    def test_format_failure_includes_path(self):
        error = RunbookFailedError("Check files", "not_empty(files)", "No files")
        error.path = ["Pre-checks", "Check files"]

        report = format_failure(error, runbook_name="Orders")

        self.assertIn("Path: Orders > Pre-checks > Check files", report)


if __name__ == "__main__":
    unittest.main()
