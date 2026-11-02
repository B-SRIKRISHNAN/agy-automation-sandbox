"""Tests for issue payload parsing and markdown context generation."""

import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.fetch_issue import (
    build_markdown_context,
    fetch_issue_payload,
    get_issue_provider_status,
    list_github_issues,
)
from unittest.mock import MagicMock, patch


class TestFetchIssue(unittest.TestCase):

    def test_build_markdown_context_full(self):
        payload = {
            "number": 42,
            "title": "Fix memory leak in parser",
            "url": "https://github.com/org/repo/issues/42",
            "author": {"login": "octocat"},
            "labels": [{"name": "bug"}, {"name": "priority"}],
            "body": "There is a severe memory leak when parsing AST.",
            "comments": [
                {"author": {"login": "reviewer"}, "body": "Observed on Node 22."},
                {"author": {"login": "contributor"}, "body": "Working on a repro."},
            ],
        }

        context = build_markdown_context(payload)
        self.assertIn("# Issue #42: Fix memory leak in parser", context)
        self.assertIn("**URL**: https://github.com/org/repo/issues/42", context)
        self.assertIn("**Author**: octocat", context)
        self.assertIn("**Labels**: bug, priority", context)
        self.assertIn("## Description\nThere is a severe memory leak when parsing AST.", context)
        self.assertIn("### Comment by @reviewer\nObserved on Node 22.", context)
        self.assertIn("### Comment by @contributor\nWorking on a repro.", context)

    def test_build_markdown_context_empty_comments_and_labels(self):
        payload = {
            "number": 10,
            "title": "Update README",
            "url": "https://github.com/org/repo/issues/10",
            "author": None,
            "labels": [],
            "body": "",
            "comments": [],
        }

        context = build_markdown_context(payload)
        self.assertIn("# Issue #10: Update README", context)
        self.assertIn("**Author**: Unknown", context)
        self.assertIn("**Labels**: None", context)
        self.assertIn("*(No comments)*", context)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_list_github_issues_mocked(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/gh"
        fake_issues = [
            {"number": 1, "title": "Issue 1", "state": "OPEN", "author": {"login": "dev1"}},
            {"number": 2, "title": "Issue 2", "state": "OPEN", "author": {"login": "dev2"}},
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"number": 1, "title": "Issue 1", "state": "OPEN", "author": {"login": "dev1"}}, {"number": 2, "title": "Issue 2", "state": "OPEN", "author": {"login": "dev2"}}]')

        issues = list_github_issues(repo_dir=Path("/mock/repo"), state="open", limit=10)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0]["number"], 1)
        self.assertEqual(issues[1]["title"], "Issue 2")

        # Verify cwd was passed
        self.assertEqual(mock_run.call_args[1].get("cwd"), "/mock/repo")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_get_issue_provider_status_available(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/gh"
        # Mock auth status (code 0) and remote get-url (code 0)
        def fake_run(cmd, *args, **kwargs):
            if "auth" in cmd:
                return MagicMock(returncode=0, stdout="Logged in\n")
            elif "remote" in cmd:
                return MagicMock(returncode=0, stdout="git@github.com:org/repo.git\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = fake_run

        status = get_issue_provider_status(repo_dir=Path("/mock/repo"))
        self.assertTrue(status["gh_installed"])
        self.assertTrue(status["authenticated"])


if __name__ == "__main__":
    unittest.main()
