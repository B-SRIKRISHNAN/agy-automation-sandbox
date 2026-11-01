"""Tests for worktree context injection, line endings, and relative path normalization."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.worktree import create_worktree, inject_issue_context


class TestWorktree(unittest.TestCase):

    def test_inject_issue_context_lf_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wt_path = Path(tmp_dir)
            content = "# Issue #1\nLine 1\r\nLine 2\n"
            dest = inject_issue_context(wt_path, content)

            self.assertTrue(dest.is_file())
            text = dest.read_text(encoding="utf-8")
            self.assertIn("Line 1", text)

    def test_create_worktree_normalizes_gitdir_to_relative(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir)
            wt_name = "test-wt-rel"
            br_name = "test-br-rel"
            wt_dir = repo_path / ".worktrees" / wt_name

            def mock_run_git_impl(args, cwd=None, check=False, capture_output=True):
                if "worktree" in args and "add" in args:
                    wt_dir.mkdir(parents=True, exist_ok=True)
                    # Simulate Git creating an absolute path gitfile
                    (wt_dir / ".git").write_text(f"gitdir: {repo_path}/.git/worktrees/{wt_name}\n")
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

            with patch("agy_automation.core.worktree.run_git", side_effect=mock_run_git_impl), \
                 patch("agy_automation.core.worktree.get_current_branch", return_value="master"), \
                 patch("agy_automation.core.worktree.is_branch_existing", return_value=False), \
                 patch("agy_automation.core.worktree.list_worktrees", return_value=[]):

                res_path = create_worktree(
                    worktree_name=wt_name,
                    branch_name=br_name,
                    repo_dir=repo_path,
                )

                self.assertTrue((res_path / ".git").is_file())
                content = (res_path / ".git").read_text(encoding="utf-8")
                self.assertEqual(content.strip(), f"gitdir: ../../.git/worktrees/{wt_name}")


if __name__ == "__main__":
    unittest.main()
