"""Tests for PipelineContext initialization, validation, and serialization."""

import unittest
from pathlib import Path

from agy_automation.core.context import PipelineContext


class TestPipelineContext(unittest.TestCase):
    def test_pipeline_context_defaults(self):
        ctx = PipelineContext(target_repo=Path("/mock/repo"), target_type="issue", target_id="101")
        self.assertEqual(ctx.target_type, "issue")
        self.assertEqual(ctx.target_id, "101")
        self.assertEqual(ctx.worktree_name, "worktree-issue-101")
        self.assertEqual(ctx.branch_name, "issue-101")
        self.assertEqual(ctx.base_branch, "master")
        self.assertEqual(ctx.engine, "auto")
        self.assertEqual(ctx.interactive, False)
        self.assertEqual(ctx.auto_approve, False)
        self.assertEqual(ctx.dry_run, False)

    def test_pipeline_context_session_naming(self):
        ctx = PipelineContext(
            target_repo=Path("/mock/repo"),
            target_type="session",
            target_id="feat/auth refactor!",
        )
        self.assertEqual(ctx.worktree_name, "worktree-feat-auth-refactor")
        self.assertEqual(ctx.branch_name, "session/feat-auth-refactor")

    def test_pipeline_context_to_dict(self):
        ctx = PipelineContext(
            target_repo=Path("/mock/repo"),
            target_type="issue",
            target_id="42",
            base_branch="develop",
            engine="podman",
        )
        d = ctx.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["target_type"], "issue")
        self.assertEqual(d["target_id"], "42")
        self.assertEqual(d["base_branch"], "develop")
        self.assertEqual(d["engine"], "podman")
        self.assertIn("worktree_path", d)


if __name__ == "__main__":
    unittest.main()
