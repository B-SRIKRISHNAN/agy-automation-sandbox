"""Integration tests for Project Issues router endpoints using TestClient."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestProjectIssuesRouter(InMemoryDatabaseTestCase):
    """Integration tests for /api/projects/active/issues and /{id}/issues endpoints."""

    def test_active_issues_no_active_project_returns_400(self):
        # Database has no active project
        resp = self.client.get("/api/projects/active/issues")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No active project selected", resp.json()["detail"])

    @patch("agy_automation.api.modules.projects.service.subprocess.run")
    @patch("agy_automation.api.modules.projects.issues.service.list_github_issues")
    @patch("agy_automation.api.modules.projects.issues.service.get_issue_provider_status")
    def test_active_issues_lifecycle(self, mock_status, mock_list, mock_git):
        mock_git.return_value = MagicMock(returncode=0, stdout="true\n")
        mock_status.return_value = {
            "available": True,
            "gh_installed": True,
            "authenticated": True,
            "has_remote": True,
            "remote_url": "git@github.com:org/repo.git",
            "reason": None,
        }
        mock_list.return_value = [
            {
                "number": 101,
                "title": "Fix navbar alignment",
                "state": "OPEN",
                "author": {"login": "octodev"},
                "labels": [{"name": "frontend"}],
                "updatedAt": "2026-11-02",
                "url": "https://github.com/org/repo/issues/101",
            }
        ]

        with tempfile.TemporaryDirectory() as td:
            repo_dir = Path(td)
            (repo_dir / ".git").mkdir()

            # 1. Register project (auto-activated)
            reg_resp = self.client.post("/api/projects", json={"path": str(repo_dir)})
            self.assertEqual(reg_resp.status_code, 201)
            project_id = reg_resp.json()["id"]

            # 2. Check provider status
            status_resp = self.client.get("/api/projects/active/issues/status")
            self.assertEqual(status_resp.status_code, 200)
            self.assertTrue(status_resp.json()["available"])

            # 3. List active issues
            list_resp = self.client.get("/api/projects/active/issues")
            self.assertEqual(list_resp.status_code, 200)
            data = list_resp.json()
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["issues"][0]["number"], 101)

            # 4. List issues by project ID
            by_id_resp = self.client.get(f"/api/projects/{project_id}/issues")
            self.assertEqual(by_id_resp.status_code, 200)
            self.assertEqual(by_id_resp.json()["total"], 1)

            # 5. Non-existent project ID returns 404
            missing_resp = self.client.get("/api/projects/non-existent-uuid/issues")
            self.assertEqual(missing_resp.status_code, 404)

    @patch("agy_automation.api.modules.projects.service.subprocess.run")
    @patch("agy_automation.api.modules.projects.issues.service.create_github_issue")
    def test_create_active_issue(self, mock_create, mock_git):
        mock_git.return_value = MagicMock(returncode=0, stdout="true\n")
        mock_create.return_value = {
            "number": 202,
            "title": "New feature request",
            "body": "Feature body text",
            "url": "https://github.com/org/repo/issues/202",
            "labels": ["enhancement"],
        }

        with tempfile.TemporaryDirectory() as td:
            repo_dir = Path(td)
            (repo_dir / ".git").mkdir()

            # Register project
            self.client.post("/api/projects", json={"path": str(repo_dir)})

            # Create issue
            create_resp = self.client.post(
                "/api/projects/active/issues",
                json={"title": "New feature request", "body": "Feature body text", "labels": ["enhancement"]},
            )
            self.assertEqual(create_resp.status_code, 201)
            data = create_resp.json()
            self.assertEqual(data["number"], 202)
            self.assertEqual(data["title"], "New feature request")


if __name__ == "__main__":
    unittest.main()
