"""Tests for issue payload parsing and markdown context generation."""

import unittest
from agy_automation.fetch_issue import build_markdown_context


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


if __name__ == "__main__":
    unittest.main()
