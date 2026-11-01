"""Tests for modern CLI subcommands (start, session, create-issue, review, cleanup) and GitHub-CLI style help."""

import unittest
from unittest.mock import MagicMock, patch

from agy_automation.cli.parser import create_parser, parse_cli_args


class TestCliSubcommands(unittest.TestCase):
    def test_start_subcommand(self):
        ns = parse_cli_args(["start", "78", "--build", "--engine=podman"])
        self.assertEqual(ns.command, "start")
        self.assertEqual(ns.issue, 78)
        self.assertTrue(ns.build)
        self.assertEqual(ns.engine, "podman")
        self.assertFalse(ns.interactive)

    def test_start_subcommand_interactive_flag(self):
        ns = parse_cli_args(["start", "78", "-i"])
        self.assertEqual(ns.command, "start")
        self.assertEqual(ns.issue, 78)
        self.assertTrue(ns.interactive)

    def test_session_subcommand(self):
        ns = parse_cli_args(["session", "refactor-api", "--dry-run"])
        self.assertEqual(ns.command, "session")
        self.assertEqual(ns.session, "refactor-api")
        self.assertTrue(ns.dry_run)

    def test_create_issue_subcommand(self):
        ns = parse_cli_args(["create-issue", "investigate memory spike on login"])
        self.assertEqual(ns.command, "create-issue")
        self.assertTrue(ns.new_issue)
        self.assertEqual(ns.prompt, "investigate memory spike on login")

    def test_review_subcommand(self):
        ns = parse_cli_args(["review", "worktree-issue-42"])
        self.assertEqual(ns.command, "review")
        self.assertEqual(ns.target, "worktree-issue-42")

    def test_cleanup_subcommand(self):
        ns = parse_cli_args(["cleanup", "worktree-issue-42", "--force"])
        self.assertEqual(ns.command, "cleanup")
        self.assertEqual(ns.target, "worktree-issue-42")
        self.assertTrue(ns.force)

    def test_top_level_help_formatting(self):
        parser = create_parser()
        help_text = parser.format_help()
        self.assertIn("USAGE", help_text)
        self.assertIn("CORE COMMANDS", help_text)
        self.assertIn("start", help_text)
        self.assertIn("session", help_text)
        self.assertIn("create-issue", help_text)
        self.assertIn("review", help_text)
        self.assertIn("cleanup", help_text)
        self.assertIn("GLOBAL FLAGS", help_text)
        self.assertIn("EXAMPLES", help_text)
        self.assertIn("LEARN MORE", help_text)

    def test_subcommand_help_formatting(self):
        parser = create_parser()
        # Find subparsers action
        subparsers_action = next(
            a for a in parser._actions if hasattr(a, "choices") and isinstance(a.choices, dict)
        )
        start_parser = subparsers_action.choices["start"]
        start_help = start_parser.format_help()
        self.assertIn("USAGE", start_help)
        self.assertIn("agy-automation start", start_help)
        self.assertIn("ARGUMENTS", start_help)
        self.assertIn("FLAGS", start_help)
        self.assertIn("EXAMPLES", start_help)

        session_parser = subparsers_action.choices["session"]
        session_help = session_parser.format_help()
        self.assertIn("USAGE", session_help)
        self.assertIn("agy-automation session", session_help)
        self.assertIn("session-name", session_help)


if __name__ == "__main__":
    unittest.main()
