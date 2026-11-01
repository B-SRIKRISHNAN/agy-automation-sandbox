"""Tests for GitHub issue creation service."""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agy_automation.create_issue import (
    confirm_and_create_issue,
    create_github_issue,
    extract_issue_number_from_url,
)


class TestCreateIssue(unittest.TestCase):
    def test_extract_issue_number_from_url(self):
        url = "https://github.com/owner/repo/issues/105"
        self.assertEqual(extract_issue_number_from_url(url), 105)

        invalid_url = "https://github.com/owner/repo/pull/105"
        self.assertIsNone(extract_issue_number_from_url(invalid_url))

    def test_create_github_issue_empty_fields_raise(self):
        with self.assertRaises(ValueError):
            create_github_issue(title="", body="Some body")

        with self.assertRaises(ValueError):
            create_github_issue(title="Some title", body="   ")

    def test_create_github_issue_success(self):
        mock_proc = subprocess.CompletedProcess(
            args=["gh", "issue", "create"],
            returncode=0,
            stdout="https://github.com/owner/repo/issues/42\n",
            stderr="",
        )
        with patch("agy_automation.create_issue.verify_gh_installed", return_value="/bin/gh"), \
             patch("subprocess.run", return_value=mock_proc) as mock_run:

            res = create_github_issue(
                title="Bug: Parser error on empty line",
                body="## Problem\nThe parser crashes on empty lines.",
                labels=["bug", "backend"],
                assignees=["developer"],
                repo_dir=Path("/mock/repo"),
            )

            self.assertEqual(res["number"], 42)
            self.assertEqual(res["url"], "https://github.com/owner/repo/issues/42")
            self.assertEqual(res["title"], "Bug: Parser error on empty line")
            self.assertEqual(res["labels"], ["bug", "backend"])

            # Verify command arguments
            cmd_called = mock_run.call_args[0][0]
            self.assertIn("--title", cmd_called)
            self.assertIn("Bug: Parser error on empty line", cmd_called)
            self.assertIn("--label", cmd_called)
            self.assertIn("bug", cmd_called)
            self.assertIn("--assignee", cmd_called)
            self.assertIn("developer", cmd_called)

    def test_create_github_issue_failure_raises(self):
        mock_proc = subprocess.CompletedProcess(
            args=["gh", "issue", "create"],
            returncode=1,
            stdout="",
            stderr="GraphQL: Resource not found",
        )
        with patch("agy_automation.create_issue.verify_gh_installed", return_value="/bin/gh"), \
             patch("subprocess.run", return_value=mock_proc):

            with self.assertRaises(RuntimeError) as ctx:
                create_github_issue(title="Test", body="Body")
            self.assertIn("GitHub CLI issue creation failed", str(ctx.exception))

    def test_confirm_and_create_issue_non_interactive(self):
        expected = {
            "number": 55,
            "url": "https://github.com/owner/repo/issues/55",
            "title": "Title",
            "body": "Body",
            "labels": [],
        }
        with patch("agy_automation.create_issue.create_github_issue", return_value=expected):
            res = confirm_and_create_issue(
                title="Title",
                body="Body",
                interactive=False,
            )
            self.assertEqual(res, expected)

    def test_confirm_and_create_issue_interactive_approved(self):
        expected = {
            "number": 56,
            "url": "https://github.com/owner/repo/issues/56",
            "title": "Title",
            "body": "Body",
            "labels": [],
        }
        with patch("builtins.input", return_value="y"), \
             patch("agy_automation.create_issue.create_github_issue", return_value=expected):
            res = confirm_and_create_issue(
                title="Title",
                body="Body",
                interactive=True,
            )
            self.assertEqual(res, expected)

    def test_confirm_and_create_issue_interactive_declined(self):
        with patch("builtins.input", return_value="n"), \
             patch("agy_automation.create_issue.create_github_issue") as mock_create:
            res = confirm_and_create_issue(
                title="Title",
                body="Body",
                interactive=True,
            )
            self.assertIsNone(res)
            mock_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
