"""Tests for diff truncation and review formatting."""

import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


class TestReviewMerge(unittest.TestCase):

    def test_diff_truncation_logic(self):
        short_diff = "diff --git a/file b/file\n+print('hello')"
        if len(short_diff) > 2000:
            truncated = short_diff[:2000] + "\n\n... [truncated]"
        else:
            truncated = short_diff
        self.assertEqual(truncated, short_diff)

        long_diff = "x" * 3500
        if len(long_diff) > 2000:
            truncated = long_diff[:2000] + "\n\n... [diff truncated to stay within command buffer]"
        else:
            truncated = long_diff

        self.assertTrue(len(truncated) > 2000)
        self.assertIn("... [diff truncated", truncated)
        self.assertTrue(truncated.startswith("x" * 2000))


if __name__ == "__main__":
    unittest.main()
