import json
import tempfile
import unittest
from pathlib import Path

from runbook import JsonlResultExporter, Runbook, not_empty, step


class ObservabilityTest(unittest.TestCase):
    def test_runbook_exports_success_result(self):
        exported = []

        result = Runbook("observed").export_to(exported.append).add(step("ok")).execute({})

        self.assertTrue(result.passed)
        self.assertEqual(exported, [result])

    def test_runbook_exports_failure_result(self):
        exported = []

        result = (
            Runbook("observed")
            .export_to(exported.append)
            .add(step("bad").require(not_empty("items"), "missing"))
            .execute({})
        )

        self.assertTrue(result.failed)
        self.assertEqual(exported, [result])

    def test_exporter_errors_do_not_fail_runbook(self):
        def broken_exporter(result):
            raise RuntimeError("export failed")

        result = Runbook("observed").export_to(broken_exporter).add(step("ok")).execute({})

        self.assertTrue(result.passed)

    def test_jsonl_result_exporter_appends_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir, "results.jsonl")

            result = Runbook("observed").export_to(JsonlResultExporter(str(path))).add(step("ok")).execute({})

            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["name"], "observed")
        self.assertEqual(payload["status"], result.status)


if __name__ == "__main__":
    unittest.main()
