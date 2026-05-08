import contextlib
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

from runbook.cli import load_runbook_from_file, main


class RunbookCliTest(unittest.TestCase):
    def test_load_runbook_from_file(self):
        path = self._write_runbook(
            """
            from runbook import Runbook, step

            runbook = Runbook("cli").add(step("one"))
            """
        )

        runbook = load_runbook_from_file(str(path))

        self.assertEqual(runbook.name, "cli")
        self.assertEqual([step.name for step in runbook.steps], ["one"])

    def test_main_run_returns_success_exit_code(self):
        path = self._write_runbook(
            """
            from runbook import Runbook, not_empty, step

            runbook = Runbook("cli").add(step("one").require(not_empty("items")))
            """
        )

        exit_code = self._run_cli(["run", str(path), "--quiet", "--context", '{"items": [1]}'])

        self.assertEqual(exit_code, 0)

    def test_main_run_returns_failure_exit_code(self):
        path = self._write_runbook(
            """
            from runbook import Runbook, not_empty, step

            runbook = Runbook("cli").add(step("one").require(not_empty("items")))
            """
        )

        exit_code = self._run_cli(["run", str(path), "--quiet", "--context", "{}"])

        self.assertEqual(exit_code, 1)

    def _write_runbook(self, source):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / "checks.py"
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return path

    def _run_cli(self, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args)


if __name__ == "__main__":
    unittest.main()
