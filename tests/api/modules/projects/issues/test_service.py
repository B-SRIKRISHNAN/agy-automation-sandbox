"""Unit tests for Projects Issues service layer."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from agy_automation.api.modules.projects.issues import service
from agy_automation.api.modules.projects.issues.schemas import IssueCreateRequest
from agy_automation.api.modules.projects.models import Project
from agy_automation.core.exceptions import IssueCreationError, IssueNotFoundError


class TestIssueService(unittest.TestCase):
    """Test business logic and external call handling in issue service."""

    def setUp(self):
        self.mock_project = Project(
            id="proj-123",
            name="test-repo",
            path="/abs/test-repo",
            git_remote="git@github.com:org/repo.git",
            is_active=True,
        )

    @patch("agy_automation.api.modules.projects.issues.service.get_issue_provider_status")
    def test_get_provider_status(self, mock_status):
        mock_status.return_value = {
            "available": True,
            "gh_installed": True,
            "authenticated": True,
            "has_remote": True,
            "remote_url": "git@github.com:org/repo.git",
            "reason": None,
        }

        res = service.get_provider_status_for_project(self.mock_project)
        self.assertTrue(res.available)
        self.assertEqual(res.remote_url, "git@github.com:org/repo.git")

    @patch("agy_automation.api.modules.projects.issues.service.list_github_issues")
    def test_list_issues_formatting(self, mock_list):
        mock_list.return_value = [
            {
                "number": 10,
                "title": "Bug report",
                "state": "OPEN",
                "author": {"login": "tester"},
                "labels": [{"name": "bug"}, {"name": "ui"}],
                "updatedAt": "2026-11-02",
                "url": "https://github.com/org/repo/issues/10",
            }
        ]

        res = service.list_issues_for_project(self.mock_project, state="open", limit=10)
        self.assertEqual(res.total, 1)
        item = res.issues[0]
        self.assertEqual(item.number, 10)
        self.assertEqual(item.author, "tester")
        self.assertEqual(item.labels, ["bug", "ui"])

    @patch("agy_automation.api.modules.projects.issues.service.fetch_issue_payload")
    def test_get_issue_detail_not_found_raises_404(self, mock_fetch):
        mock_fetch.side_effect = IssueNotFoundError("Not found")

        with self.assertRaises(HTTPException) as ctx:
            service.get_issue_detail_for_project(self.mock_project, 999)
        self.assertEqual(ctx.exception.status_code, 404)

    @patch("agy_automation.api.modules.projects.issues.service.create_github_issue")
    def test_create_issue_failure_raises_422(self, mock_create):
        mock_create.side_effect = IssueCreationError("Repo not found")

        payload = IssueCreateRequest(title="Failing issue", body="Detail")
        with self.assertRaises(HTTPException) as ctx:
            service.create_issue_for_project(self.mock_project, payload)
        self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
