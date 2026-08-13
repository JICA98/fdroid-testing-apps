import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick_mr import format_row, is_ready, is_tested, summarize

class TestPickMr(unittest.TestCase):
    def test_is_ready_success(self):
        self.assertTrue(is_ready({"head_pipeline": {"status": "success"}}))

    def test_is_ready_failed(self):
        self.assertFalse(is_ready({"head_pipeline": {"status": "failed"}}))

    def test_is_ready_no_pipeline(self):
        self.assertFalse(is_ready({"head_pipeline": None}))
        self.assertFalse(is_ready({}))

    def test_is_tested_finds_marker(self):
        notes = [
            {"body": "some other comment"},
            {"body": "## Tester review: Kinetica (com.kinetica.keyboard)"},
        ]
        self.assertTrue(is_tested(notes))

    def test_is_tested_no_marker(self):
        self.assertFalse(is_tested([{"body": "just a comment"}]))

    def test_format_row(self):
        row = {"iid": 45475, "title": "New app: Kinetica", "pipeline": "success", "tested": False}
        self.assertEqual(
            format_row(row),
            "!45475 New app: Kinetica | pipeline: success | tested: no",
        )

    def test_format_row_unknown(self):
        row = {"iid": 45475, "title": "New app: Kinetica", "pipeline": "success", "tested": None}
        self.assertIn("tested: unknown", format_row(row))

    def test_summarize_candidates(self):
        rows = [
            {"iid": 1, "title": "A", "pipeline": "success", "ready": True, "tested": False},
            {"iid": 2, "title": "B", "pipeline": "failed", "ready": False, "tested": False},
            {"iid": 3, "title": "C", "pipeline": "success", "ready": True, "tested": True},
        ]
        self.assertEqual(summarize(rows), [1])


if __name__ == "__main__":
    unittest.main()
