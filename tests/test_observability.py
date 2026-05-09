import json
import tempfile
import unittest
from pathlib import Path

from runbook import AsyncResultExporter, JsonlResultExporter, Runbook, not_empty, step


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

    def test_async_result_exporter_wraps_jsonl_exporter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir, "results.jsonl")

            with AsyncResultExporter(JsonlResultExporter(str(path))) as exporter:
                result = Runbook("observed").export_to(exporter).add(step("ok")).execute({})

            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["status"], result.status)

    def test_async_result_exporter_flushes_background_results(self):
        exported = []
        exporter = AsyncResultExporter(exported.append)

        result = Runbook("observed").export_to(exporter).add(step("ok")).execute({})
        exporter.flush()
        exporter.close()

        self.assertEqual(exported, [result])

    def test_async_result_exporter_context_manager_closes(self):
        exported = []

        with AsyncResultExporter(exported.append) as exporter:
            result = Runbook("observed").export_to(exporter).add(step("ok")).execute({})

        self.assertEqual(exported, [result])

    def test_async_result_exporter_captures_background_errors(self):
        def broken_exporter(result):
            raise RuntimeError("export failed")

        exporter = AsyncResultExporter(broken_exporter)
        Runbook("observed").export_to(exporter).add(step("ok")).execute({})
        exporter.flush()
        exporter.close()

        self.assertEqual(len(exporter.errors), 1)
        self.assertEqual(str(exporter.errors[0]), "export failed")

    def test_async_result_exporter_close_is_idempotent(self):
        exporter = AsyncResultExporter(lambda result: None)

        exporter.close()
        exporter.close()

    def test_async_result_exporter_rejects_calls_after_close(self):
        exporter = AsyncResultExporter(lambda result: None)
        exporter.close()

        with self.assertRaises(RuntimeError):
            exporter(Runbook("observed").add(step("ok")).execute({}))


if __name__ == "__main__":
    unittest.main()
