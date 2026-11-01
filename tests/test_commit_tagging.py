"""Tests for issue closing tag detection, commit message formatting, and extraction."""

import re
import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.review_merge import format_merge_message


class TestCommitTagging(unittest.TestCase):

    def test_format_merge_message_with_issue(self):
        msg = format_merge_message("issue-42", "main")
        self.assertEqual(msg, "Merge branch 'issue-42' into main (Fixes #42)")

        msg2 = format_merge_message("issue-105", "master")
        self.assertEqual(msg2, "Merge branch 'issue-105' into master (Fixes #105)")

    def test_format_merge_message_without_issue(self):
        msg = format_merge_message("session/refactor-auth", "main")
        self.assertEqual(msg, "Merge branch 'session/refactor-auth' into main")

        msg2 = format_merge_message("feature-login", "develop")
        self.assertEqual(msg2, "Merge branch 'feature-login' into develop")

    def test_worktree_name_issue_extraction(self):
        worktree_regex = r"^worktree-issue-([0-9]+)$"

        m1 = re.match(worktree_regex, "worktree-issue-42")
        self.assertIsNotNone(m1)
        self.assertEqual(m1.group(1), "42")

        m2 = re.match(worktree_regex, "worktree-issue-9999")
        self.assertIsNotNone(m2)
        self.assertEqual(m2.group(1), "9999")

        m3 = re.match(worktree_regex, "worktree-session-my-feature")
        self.assertIsNone(m3)

    def test_issue_context_header_extraction(self):
        header_regex = r"^#\ Issue\ #([0-9]+)"

        first_line = "# Issue #42: Fix null pointer in token parser"
        m1 = re.match(header_regex, first_line)
        self.assertIsNotNone(m1)
        self.assertEqual(m1.group(1), "42")

        non_issue_header = "# Session: Refactor authentication system"
        m2 = re.match(header_regex, non_issue_header)
        self.assertIsNone(m2)

    def test_closing_tag_subject_detection(self):
        issue_num = "42"
        tag_pattern = rf"(?i)(fixes|closes|resolves)\s+#{issue_num}\b"

        # Valid tagged subjects
        self.assertTrue(re.search(tag_pattern, "fix(parser): resolve null pointer (Fixes #42)"))
        self.assertTrue(re.search(tag_pattern, "feat(auth): add OAuth support (Closes #42)"))
        self.assertTrue(re.search(tag_pattern, "refactor: clean up (Resolves #42)"))
        self.assertTrue(re.search(tag_pattern, "fix: bug (fixes #42)"))

        # Untagged or different issue subjects
        self.assertFalse(re.search(tag_pattern, "fix(parser): resolve null pointer"))
        self.assertFalse(re.search(tag_pattern, "fix(parser): resolve null pointer (Fixes #420)"))
        self.assertFalse(re.search(tag_pattern, "fix(parser): resolve null pointer (Fixes #4)"))

    def test_subject_amend_formatting(self):
        issue_num = "42"
        original_subject = "fix(parser): resolve token error"
        new_subject = f"{original_subject} (Fixes #{issue_num})"

        self.assertEqual(new_subject, "fix(parser): resolve token error (Fixes #42)")
        self.assertTrue(new_subject.endswith(f"(Fixes #{issue_num})"))


if __name__ == "__main__":
    unittest.main()
