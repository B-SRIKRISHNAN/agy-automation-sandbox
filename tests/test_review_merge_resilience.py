"""Tests for review and merge resilience, workspace dirty retry loop, and conflict handling."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from agy_automation.git_utils import (
    abort_merge,
    get_unmerged_files,
    get_workspace_status,
    is_merge_in_progress,
)
from agy_automation.review_merge import ensure_clean_workspace, review_and_merge


class TestReviewMergeResilience(unittest.TestCase):
    def test_get_workspace_status_split(self):
        sample_status = " M src/agy_automation/app.py\n?? untracked_notes.txt\nA  new_feature.py\n?? .temp_scratch\n"
        mock_proc = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout=sample_status,
            stderr="",
        )
        with patch("agy_automation.git_utils.run_git", return_value=mock_proc):
            dirty, untracked = get_workspace_status(Path("/mock/repo"))

        self.assertEqual(len(dirty), 2)
        self.assertIn(" M src/agy_automation/app.py", dirty)
        self.assertIn("A  new_feature.py", dirty)
        self.assertEqual(len(untracked), 2)
        self.assertIn("untracked_notes.txt", untracked)
        self.assertIn(".temp_scratch", untracked)

    def test_get_unmerged_files(self):
        mock_proc = subprocess.CompletedProcess(
            args=["git", "diff", "--name-only", "--diff-filter=U"],
            returncode=0,
            stdout="src/file1.py\ntests/test_file2.py\n",
            stderr="",
        )
        with patch("agy_automation.git_utils.run_git", return_value=mock_proc):
            conflicts = get_unmerged_files(Path("/mock/repo"))

        self.assertEqual(conflicts, ["src/file1.py", "tests/test_file2.py"])

    def test_is_merge_in_progress(self):
        repo_dir = Path("/mock/repo")
        with patch.object(Path, "is_file", return_value=True):
            self.assertTrue(is_merge_in_progress(repo_dir))

        with patch.object(Path, "is_file", return_value=False):
            mock_proc = subprocess.CompletedProcess(args=[], returncode=1)
            with patch("agy_automation.git_utils.run_git", return_value=mock_proc):
                self.assertFalse(is_merge_in_progress(repo_dir))

    def test_ensure_clean_workspace_immediately_clean(self):
        with patch("agy_automation.review_merge.get_workspace_status", return_value=([], [])):
            mock_logger = MagicMock()
            clean = ensure_clean_workspace(Path("/mock"), "master", session_logger=mock_logger, interactive=True)
            self.assertTrue(clean)

    def test_ensure_clean_workspace_non_interactive_aborts(self):
        with patch("agy_automation.review_merge.get_workspace_status", return_value=([" M file.py"], [])):
            mock_logger = MagicMock()
            clean = ensure_clean_workspace(Path("/mock"), "master", session_logger=mock_logger, interactive=False)
            self.assertFalse(clean)
            mock_logger.log_event.assert_any_call(
                "coordinator", "merge", "merge_aborted_dirty_workspace_unattended"
            )

    def test_ensure_clean_workspace_user_abort(self):
        with patch("agy_automation.review_merge.get_workspace_status", return_value=([" M file.py"], [])):
            with patch("builtins.input", return_value="abort"):
                mock_logger = MagicMock()
                clean = ensure_clean_workspace(Path("/mock"), "master", session_logger=mock_logger, interactive=True)
                self.assertFalse(clean)
                mock_logger.log_event.assert_any_call(
                    "coordinator", "merge", "workspace_clean_aborted_by_user"
                )

    def test_ensure_clean_workspace_user_cleans_and_retries(self):
        # First call dirty, second call clean
        status_side_effects = [
            ([" M file.py"], []),
            ([], []),
        ]
        with patch("agy_automation.review_merge.get_workspace_status", side_effect=status_side_effects):
            with patch("builtins.input", return_value=""):
                mock_logger = MagicMock()
                clean = ensure_clean_workspace(Path("/mock"), "master", session_logger=mock_logger, interactive=True)
                self.assertTrue(clean)
                mock_logger.log_event.assert_any_call(
                    "coordinator", "merge", "workspace_clean_verified", {"attempts": 2}
                )

    def test_review_and_merge_conflict_interactive_resolution(self):
        mock_logger = MagicMock()
        repo = Path("/mock/repo")

        def mock_run_git_impl(args, cwd=None, check=False, capture_output=True):
            if "checkout" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "--ff-only" in args:
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="Not FF")
            if "merge" in args and "-m" in args:
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="CONFLICT (content)", stderr="")
            if "commit" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Merge committed", stderr="")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("agy_automation.review_merge.get_commits_between", return_value=["c1 Commit 1"]), \
             patch("agy_automation.review_merge.get_diff_stat", return_value="app.py | 1 +"), \
             patch("agy_automation.review_merge.get_diff_raw", return_value="+new code"), \
             patch("agy_automation.review_merge.verify_agy_installed", return_value="/bin/agy"), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess(args=[], returncode=0)), \
             patch("agy_automation.review_merge.ensure_clean_workspace", return_value=True), \
             patch("agy_automation.review_merge.run_git", side_effect=mock_run_git_impl), \
             patch("agy_automation.review_merge.get_unmerged_files", side_effect=[["app.py"], []]), \
             patch("agy_automation.review_merge.is_merge_in_progress", return_value=True), \
             patch("agy_automation.review_merge.cleanup_worktree") as mock_cleanup, \
             patch("builtins.input", return_value=""):

            merged = review_and_merge(
                worktree_name="worktree-test",
                branch_name="feature-test",
                base_branch="master",
                auto_approve=True,
                interactive=True,
                repo_dir=repo,
                session_logger=mock_logger,
            )

            self.assertTrue(merged)
            mock_cleanup.assert_called_once()
            mock_logger.log_event.assert_any_call(
                "coordinator", "merge", "merge_conflict_detected", {"conflicts": ["app.py"]}
            )
            mock_logger.log_event.assert_any_call(
                "coordinator", "merge", "merge_conflicts_resolved_and_committed"
            )

    def test_review_and_merge_conflict_user_abort(self):
        mock_logger = MagicMock()
        repo = Path("/mock/repo")

        def mock_run_git_impl(args, cwd=None, check=False, capture_output=True):
            if "checkout" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "--ff-only" in args:
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="Not FF")
            if "merge" in args and "-m" in args:
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="CONFLICT (content)", stderr="")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("agy_automation.review_merge.get_commits_between", return_value=["c1 Commit 1"]), \
             patch("agy_automation.review_merge.get_diff_stat", return_value="app.py | 1 +"), \
             patch("agy_automation.review_merge.get_diff_raw", return_value="+new code"), \
             patch("agy_automation.review_merge.verify_agy_installed", return_value="/bin/agy"), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess(args=[], returncode=0)), \
             patch("agy_automation.review_merge.ensure_clean_workspace", return_value=True), \
             patch("agy_automation.review_merge.run_git", side_effect=mock_run_git_impl), \
             patch("agy_automation.review_merge.get_unmerged_files", return_value=["app.py"]), \
             patch("agy_automation.review_merge.is_merge_in_progress", return_value=True), \
             patch("agy_automation.review_merge.abort_merge") as mock_abort, \
             patch("builtins.input", return_value="abort"):

            merged = review_and_merge(
                worktree_name="worktree-test",
                branch_name="feature-test",
                base_branch="master",
                auto_approve=True,
                interactive=True,
                repo_dir=repo,
                session_logger=mock_logger,
            )

            self.assertFalse(merged)
            mock_abort.assert_called_once_with(repo)
            mock_logger.log_event.assert_any_call(
                "coordinator", "merge", "merge_conflict_aborted_by_user"
            )


if __name__ == "__main__":
    unittest.main()
