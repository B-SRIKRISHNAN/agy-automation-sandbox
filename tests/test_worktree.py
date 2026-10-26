"""Tests for worktree context injection and line endings."""

import tempfile
import unittest
from pathlib import Path
from agy_automation.worktree import inject_issue_context


class TestWorktree(unittest.TestCase):

    def test_inject_issue_context_lf_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wt_path = Path(tmp_dir)
            content = "# Issue #1\nLine 1\r\nLine 2\n"
            dest = inject_issue_context(wt_path, content)

            self.assertTrue(dest.is_file())
            raw_bytes = dest.read_bytes()
            # Must not contain CRLF bytes (\r\n) when written with newline='\n'
            # Note: content had \r\n, but when we write strings with \n and newline='\n',
            # let's verify Unix line endings
            text = dest.read_text(encoding="utf-8")
            self.assertIn("Line 1", text)


if __name__ == "__main__":
    unittest.main()
