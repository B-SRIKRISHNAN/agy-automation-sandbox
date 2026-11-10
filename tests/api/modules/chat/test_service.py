"""Tests for chat formulation module, lifecycle, termination, and runner handoff."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from agy_automation.api.modules.chat.schemas import (
    ChatMessageRequest,
    ChatSessionCreateRequest,
    CreateAndRunRequest,
)
from agy_automation.api.modules.chat.service import chat_manager
from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.runs.models import Run
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestChatModule(InMemoryDatabaseTestCase):
    """Test suite validating interactive issue formulation sessions and termination."""

    def setUp(self):
        super().setUp()
        self.project = Project(
            id="proj-chat",
            name="chat-test-repo",
            path="/tmp/chat-test-repo",
            git_branch="main",
            is_active=True,
        )
        self.db.add(self.project)
        self.db.commit()

    @patch("agy_automation.api.modules.chat.service.create_worktree")
    @patch("agy_automation.api.modules.chat.service.inject_issue_context")
    def test_create_and_get_chat_session(self, mock_inject, mock_create_wt):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_create_wt.return_value = Path(tmp_dir)

            req = ChatSessionCreateRequest(project_id=self.project.id, initial_prompt="")
            session = chat_manager.create_session(self.db, req)

            self.assertIsNotNone(session.session_id)
            self.assertEqual(session.status, "ACTIVE")
            self.assertEqual(session.project_id, self.project.id)

            fetched = chat_manager.get_session(session.session_id)
            self.assertEqual(fetched.session_id, session.session_id)
            self.assertEqual(fetched.status, "ACTIVE")

    @patch("agy_automation.api.modules.chat.service.create_worktree")
    @patch("agy_automation.api.modules.chat.service.inject_issue_context")
    @patch("agy_automation.api.modules.chat.service.cleanup_worktree")
    def test_terminate_chat_session_immediately(self, mock_cleanup, mock_inject, mock_create_wt):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_create_wt.return_value = Path(tmp_dir)

            req = ChatSessionCreateRequest(project_id=self.project.id, initial_prompt="")
            session = chat_manager.create_session(self.db, req)

            # Mock an active subprocess
            mock_proc = MagicMock()
            session.active_proc = mock_proc

            terminated = chat_manager.terminate_session(self.db, session.session_id)
            self.assertEqual(terminated.status, "TERMINATED")
            mock_proc.terminate.assert_called_once()
            mock_cleanup.assert_called_once()

    @patch("agy_automation.api.modules.chat.service.create_worktree")
    @patch("agy_automation.api.modules.chat.service.inject_issue_context")
    @patch("agy_automation.api.modules.chat.service.cleanup_worktree")
    @patch("agy_automation.api.modules.chat.service.issues_service.create_issue_for_project")
    @patch("agy_automation.api.modules.chat.service.runs_service.start_run")
    def test_create_and_run_handoff(self, mock_start_run, mock_create_issue, mock_cleanup, mock_inject, mock_create_wt):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_create_wt.return_value = Path(tmp_dir)

            req = ChatSessionCreateRequest(project_id=self.project.id, initial_prompt="")
            session = chat_manager.create_session(self.db, req)

            mock_issue = MagicMock()
            mock_issue.number = 55
            mock_issue.url = "https://github.com/org/repo/issues/55"
            mock_create_issue.return_value = mock_issue

            mock_run = MagicMock()
            mock_run.id = "run-from-chat-123"
            mock_start_run.return_value = mock_run

            hand_req = CreateAndRunRequest(
                title="Formulated Title",
                body="Formulated Body with acceptance criteria",
                auto_approve=False,
            )
            res = chat_manager.create_and_run(self.db, session.session_id, hand_req)

            self.assertEqual(res.issue_number, 55)
            self.assertEqual(res.run_id, "run-from-chat-123")
            mock_create_issue.assert_called_once()
            mock_start_run.assert_called_once()

    @patch("agy_automation.api.modules.chat.service.create_worktree")
    @patch("agy_automation.api.modules.chat.service.inject_issue_context")
    def test_chat_router_endpoints(self, mock_inject, mock_create_wt):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_create_wt.return_value = Path(tmp_dir)

            # 1. Create session via POST /api/chat-sessions
            res = self.client.post("/api/chat-sessions", json={"project_id": self.project.id, "initial_prompt": ""})
            self.assertEqual(res.status_code, 201)
            data = res.json()
            session_id = data["session_id"]
            self.assertEqual(data["status"], "ACTIVE")

            # 2. Get session via GET /api/chat-sessions/{id}
            get_res = self.client.get(f"/api/chat-sessions/{session_id}")
            self.assertEqual(get_res.status_code, 200)
            self.assertEqual(get_res.json()["session_id"], session_id)

            # 3. Terminate session via POST /api/chat-sessions/{id}/terminate
            term_res = self.client.post(f"/api/chat-sessions/{session_id}/terminate")
            self.assertEqual(term_res.status_code, 200)
            self.assertEqual(term_res.json()["status"], "TERMINATED")
