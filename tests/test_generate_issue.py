"""Tests for interactive issue generation and parsing."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agy_automation.generate_issue import (
    generate_issue_statement,
    parse_generated_issue,
)


class TestGenerateIssue(unittest.TestCase):
    def test_parse_generated_issue_hash_title_prefix(self):
        content = """# Title: fix(parser): handle empty strings properly

## Problem Description
The parser crashes when given an empty string.

## Expected Solution
Return an empty AST node instead of raising an unhandled exception.
"""
        title, body = parse_generated_issue(content)
        self.assertEqual(title, "fix(parser): handle empty strings properly")
        self.assertIn("## Problem Description", body)
        self.assertIn("## Expected Solution", body)

    def test_parse_generated_issue_hash_prefix(self):
        content = """# Add caching layer for database queries

## Problem Description
Database queries are repeated on every turn.
"""
        title, body = parse_generated_issue(content)
        self.assertEqual(title, "Add caching layer for database queries")
        self.assertIn("Database queries are repeated", body)

    def test_parse_generated_issue_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_generated_issue("")

    def test_generate_issue_statement_lifecycle(self):
        repo_dir = Path("/mock/repo")
        mock_wt_path = Path("/mock/repo/.worktrees/worktree-draft-test")
        mock_logger = MagicMock()

        # Mock worktree creation and write a mock NEW_ISSUE.md into it
        def mock_create_wt(*args, **kwargs):
            return mock_wt_path

        mock_content = """# Title: fix(auth): prevent token leakage

## Problem Description
Auth tokens appear in raw error logs.

## Expected Solution
Sanitize tokens before writing to stderr.
"""

        with patch("agy_automation.generate_issue.create_worktree", side_effect=mock_create_wt), \
             patch("agy_automation.generate_issue.inject_issue_context"), \
             patch("builtins.open", unittest.mock.mock_open(read_data=mock_content)), \
             patch.object(Path, "is_file", return_value=True), \
             patch("agy_automation.generate_issue.run_sandbox", return_value=0), \
             patch("agy_automation.generate_issue.cleanup_worktree") as mock_cleanup:

            title, body = generate_issue_statement(
                initial_prompt="Tokens leak in error logs",
                target_repo=repo_dir,
                session_slug="test-draft",
                interactive=True,
                session_logger=mock_logger,
            )

            self.assertEqual(title, "fix(auth): prevent token leakage")
            self.assertIn("Auth tokens appear in raw error logs", body)
            mock_cleanup.assert_called_once_with(
                "worktree-test-draft", "session/test-draft", force=True, repo_dir=repo_dir
            )
            mock_logger.log_event.assert_any_call(
                "coordinator", "formulation", "session_finished", {
                    "title": "fix(auth): prevent token leakage",
                    "body_length": len(body),
                }
            )


if __name__ == "__main__":
    unittest.main()
