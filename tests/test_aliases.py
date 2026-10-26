"""Tests for script-equivalent module aliases and their matching exports."""

import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import agy_automation.cleanup as cleanup_mod
import agy_automation.cleanup_worktree as cleanup_worktree_mod
import agy_automation.create_worktree as create_worktree_mod
import agy_automation.push as push_mod
import agy_automation.push_changes as push_changes_mod
import agy_automation.run_sandbox as run_sandbox_mod
import agy_automation.sandbox as sandbox_mod
import agy_automation.worktree as worktree_mod


class TestAliases(unittest.TestCase):

    def test_create_worktree_alias(self):
        self.assertIs(create_worktree_mod.create_worktree, worktree_mod.create_worktree)
        self.assertIs(create_worktree_mod.inject_issue_context, worktree_mod.inject_issue_context)
        self.assertIs(create_worktree_mod.main, worktree_mod.main)

    def test_run_sandbox_alias(self):
        self.assertIs(run_sandbox_mod.run_sandbox, sandbox_mod.run_sandbox)
        self.assertIs(run_sandbox_mod.main, sandbox_mod.main)

    def test_push_changes_alias(self):
        self.assertIs(push_changes_mod.push_changes, push_mod.push_changes)
        self.assertIs(push_changes_mod.main, push_mod.main)

    def test_cleanup_worktree_alias(self):
        self.assertIs(cleanup_worktree_mod.cleanup_worktree, cleanup_mod.cleanup_worktree)
        self.assertIs(cleanup_worktree_mod.main, cleanup_mod.main)


if __name__ == "__main__":
    unittest.main()
