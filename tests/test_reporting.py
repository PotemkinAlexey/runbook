import unittest

from runbook import RunbookFailedError, format_failure


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


if __name__ == "__main__":
    unittest.main()
