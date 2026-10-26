"""Tests for worktree context injection and line endings."""

import sys
import tempfile
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.worktree import inject_issue_context


class TestWorktree(unittest.TestCase):

    def test_inject_issue_context_lf_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wt_path = Path(tmp_dir)
            content = "# Issue #1\nLine 1\r\nLine 2\n"
            dest = inject_issue_context(wt_path, content)

            self.assertTrue(dest.is_file())
            text = dest.read_text(encoding="utf-8")
            self.assertIn("Line 1", text)


if __name__ == "__main__":
    unittest.main()
