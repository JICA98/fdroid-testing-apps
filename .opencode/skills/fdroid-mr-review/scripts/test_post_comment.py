import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_comment import load_token, notes_url


class TestPostComment(unittest.TestCase):
    def test_notes_url(self):
        self.assertEqual(
            notes_url(169887, 45475),
            "https://gitlab.com/api/v4/projects/169887/merge_requests/45475/notes",
        )

    def test_load_token_strips(self):
        path = Path(__file__).parent / "_token_test.txt"
        path.write_text("  glpat-abcdef\n")
        try:
            self.assertEqual(load_token(path), "glpat-abcdef")
        finally:
            path.unlink()

    def test_load_token_empty_raises(self):
        path = Path(__file__).parent / "_token_test.txt"
        path.write_text("  \n")
        try:
            with self.assertRaises(ValueError):
                load_token(path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
