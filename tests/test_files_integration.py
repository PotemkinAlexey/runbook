import tempfile
import unittest
from pathlib import Path

from runbook import Runbook, not_empty, step
from runbook.integrations.files import glob_paths, path_exists, read_json, read_text, write_json


class FilesIntegrationTest(unittest.TestCase):
    def test_glob_paths_loader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.csv").write_text("a", encoding="utf-8")
            Path(tmpdir, "b.txt").write_text("b", encoding="utf-8")

            context = {"tmpdir": tmpdir}
            Runbook("files").add(
                step("Find CSV").load("files", glob_paths("{{ tmpdir }}/*.csv")).require(not_empty("files"))
            ).run(context)

            self.assertEqual([Path(path).name for path in context["files"]], ["a.csv"])

    def test_readers_and_writer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir, "data.json")
            text_path = Path(tmpdir, "message.txt")
            output_path = Path(tmpdir, "out.json")
            data_path.write_text('{"items": [1]}', encoding="utf-8")
            text_path.write_text("hello", encoding="utf-8")

            context = {"tmpdir": tmpdir}
            (
                step("Read")
                .load("exists", path_exists("{{ tmpdir }}/data.json"))
                .load("data", read_json("{{ tmpdir }}/data.json"))
                .load("message", read_text("{{ tmpdir }}/message.txt"))
                .then(write_json("{{ tmpdir }}/out.json", "data"))
                .run(context)
            )

            self.assertTrue(context["exists"])
            self.assertEqual(context["data"], {"items": [1]})
            self.assertEqual(context["message"], "hello")
            self.assertEqual(output_path.read_text(encoding="utf-8"), '{\n  "items": [\n    1\n  ]\n}')


if __name__ == "__main__":
    unittest.main()
