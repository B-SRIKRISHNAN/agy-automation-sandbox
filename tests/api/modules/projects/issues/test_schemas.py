"""Unit tests for Projects Issues Pydantic schemas."""

import unittest
from pydantic import ValidationError

from agy_automation.api.modules.projects.issues.schemas import (
    IssueCreateRequest,
    IssueDetail,
    IssueListItem,
    IssueListResponse,
    IssueProviderStatusResponse,
)


class TestIssueSchemas(unittest.TestCase):
    """Test validation and serialization of issue schemas."""

    def test_issue_create_request_valid(self):
        req = IssueCreateRequest(title="Bug title", body="Bug description", labels=["bug", "v1"])
        self.assertEqual(req.title, "Bug title")
        self.assertEqual(req.body, "Bug description")
        self.assertEqual(req.labels, ["bug", "v1"])

    def test_issue_create_request_empty_title_rejected(self):
        for empty in ["", "   ", "\t\n"]:
            with self.subTest(empty=empty):
                with self.assertRaises(ValidationError):
                    IssueCreateRequest(title=empty, body="Valid body")

    def test_issue_create_request_empty_body_rejected(self):
        for empty in ["", "   ", "\t\n"]:
            with self.subTest(empty=empty):
                with self.assertRaises(ValidationError):
                    IssueCreateRequest(title="Valid title", body=empty)

    def test_issue_list_item_serialization(self):
        item = IssueListItem(
            number=42,
            title="Fix bug",
            state="OPEN",
            author="octocat",
            labels=["bug"],
            updated_at="2026-11-02T22:00:00Z",
            url="https://github.com/org/repo/issues/42",
        )
        self.assertEqual(item.number, 42)
        self.assertEqual(item.author, "octocat")

    def test_issue_list_response(self):
        item = IssueListItem(number=1, title="Issue 1", state="OPEN", author="dev")
        resp = IssueListResponse(issues=[item], total=1, state="open")
        self.assertEqual(resp.total, 1)
        self.assertEqual(resp.state, "open")

    def test_provider_status_response(self):
        status = IssueProviderStatusResponse(
            available=True,
            gh_installed=True,
            authenticated=True,
            has_remote=True,
            remote_url="git@github.com:org/repo.git",
            reason=None,
        )
        self.assertTrue(status.available)
        self.assertTrue(status.authenticated)


if __name__ == "__main__":
    unittest.main()
