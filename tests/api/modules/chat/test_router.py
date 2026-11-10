"""Integration tests for Chat Formulation API endpoints."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from agy_automation.api.modules.projects.models import Project
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestChatRouter(InMemoryDatabaseTestCase):
    """End-to-end integration test suite for /api/chat-sessions/ routes."""

    def setUp(self):
        super().setUp()
        self.project = Project(
            id="proj-chat-router",
            name="chat-router-repo",
            path="/tmp/chat-router-repo",
            git_branch="master",
            is_active=True,
        )
        self.db.add(self.project)
        self.db.commit()

    @patch("agy_automation.api.modules.chat.service.create_worktree")
    @patch("agy_automation.api.modules.chat.service.inject_issue_context")
    def test_create_and_get_session(self, mock_inject, mock_create_wt):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_create_wt.return_value = Path(tmp_dir)

            payload = {
                "project_id": self.project.id,
                "initial_prompt": "Let's explore the codebase",
            }
            res = self.client.post("/api/chat-sessions", json=payload)
            self.assertEqual(res.status_code, 201)
            data = res.json()
            session_id = data["session_id"]
            self.assertEqual(data["status"], "ACTIVE")

            res_get = self.client.get(f"/api/chat-sessions/{session_id}")
            self.assertEqual(res_get.status_code, 200)
            self.assertEqual(res_get.json()["session_id"], session_id)

    @patch("agy_automation.api.modules.chat.service.create_worktree")
    @patch("agy_automation.api.modules.chat.service.inject_issue_context")
    @patch("agy_automation.api.modules.chat.service.cleanup_worktree")
    def test_terminate_session_endpoint(self, mock_cleanup, mock_inject, mock_create_wt):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_create_wt.return_value = Path(tmp_dir)

            res = self.client.post("/api/chat-sessions", json={"project_id": self.project.id})
            session_id = res.json()["session_id"]

            term_res = self.client.post(f"/api/chat-sessions/{session_id}/terminate")
            self.assertEqual(term_res.status_code, 200)
            self.assertEqual(term_res.json()["status"], "TERMINATED")
