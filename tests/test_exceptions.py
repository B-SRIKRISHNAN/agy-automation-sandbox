"""Tests for domain exception hierarchy and custom attributes."""

import unittest

from agy_automation.core.exceptions import (
    AutomationError,
    DirtyWorkspaceError,
    GitError,
    GitHubCliNotFoundError,
    GitHubError,
    IssueNotFoundError,
    MergeConflictError,
    SandboxExecutionError,
)


class TestExceptions(unittest.TestCase):
    def test_hierarchy(self):
        self.assertTrue(issubclass(GitError, AutomationError))
        self.assertTrue(issubclass(DirtyWorkspaceError, GitError))
        self.assertTrue(issubclass(MergeConflictError, GitError))
        self.assertTrue(issubclass(GitHubError, AutomationError))
        self.assertTrue(issubclass(GitHubCliNotFoundError, GitHubError))
        self.assertTrue(issubclass(IssueNotFoundError, GitHubError))
        # Ensure backward compatibility with RuntimeError
        self.assertTrue(issubclass(AutomationError, RuntimeError))

    def test_dirty_workspace_error(self):
        err = DirtyWorkspaceError(dirty_files=["file1.py", "file2.py"])
        self.assertEqual(err.dirty_files, ["file1.py", "file2.py"])
        self.assertIn("2 file(s)", str(err))

    def test_merge_conflict_error(self):
        err = MergeConflictError(conflict_files=["conflict.py"])
        self.assertEqual(err.conflict_files, ["conflict.py"])
        self.assertIn("1 file(s)", str(err))

    def test_sandbox_execution_error(self):
        err = SandboxExecutionError(returncode=137)
        self.assertEqual(err.returncode, 137)
        self.assertIn("137", str(err))


if __name__ == "__main__":
    unittest.main()
