import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runbook import (
    Runbook,
    check_files_exist,
    check_freshness,
    check_manifest_exists,
    check_row_count,
    check_schema,
    check_watermark,
    compare_row_counts,
    export_stage,
    post_export_checks,
    pre_export_checks,
    validation_stage,
)


class DataChecksTest(unittest.TestCase):
    def test_data_checks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir, "orders.csv")
            file_path.write_text("id\n1\n", encoding="utf-8")
            context = {
                "files": [str(file_path)],
                "rows": [{"id": 1}],
                "row_count": 1,
                "source_count": 10,
                "target_count": 9,
                "watermark": 5,
                "minimum_watermark": 4,
                "manifest": {"ok": True},
                "loaded_at": "2026-05-09T00:00:00+00:00",
                "now": datetime(2026, 5, 9, 0, 0, 30, tzinfo=timezone.utc),
            }

            self.assertTrue(check_files_exist("files")(context))
            self.assertTrue(check_schema("rows", ["id"])(context))
            self.assertTrue(check_row_count("row_count")(context))
            self.assertTrue(compare_row_counts("source_count", "target_count", tolerance=1)(context))
            self.assertTrue(check_watermark("watermark", "minimum_watermark")(context))
            self.assertTrue(check_manifest_exists("manifest")(context))
            self.assertTrue(check_freshness("loaded_at", max_age_seconds=60, now_key="now")(context))

    def test_high_level_stage_factories(self):
        context = {
            "files": ["orders.csv"],
            "rows": [{"id": 1}],
            "manifest": {"ok": True},
        }
        result = (
            Runbook("export")
            .add(pre_export_checks(schema_key="rows", required_fields=["id"]))
            .add(export_stage())
            .add(post_export_checks())
            .add(validation_stage("Counts", compare_row_counts("source", "target", tolerance=1)))
            .execute({**context, "source": 10, "target": 10})
        )

        self.assertTrue(result.passed)
        self.assertEqual([child.name for child in result.children], [
            "Pre-export checks",
            "Export",
            "Post-export checks",
            "Counts",
        ])


if __name__ == "__main__":
    unittest.main()
