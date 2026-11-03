"""Integration tests for Runs API endpoints."""

import json
from unittest.mock import MagicMock, patch

from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.runs import repository as runs_repo
from agy_automation.api.modules.runs import service
from agy_automation.api.modules.runs.models import Run
from agy_automation.api.modules.runs.schemas import RunStatus
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestRunsRouter(InMemoryDatabaseTestCase):
    """End-to-end integration test suite for the /api/runs/ routes."""

    def setUp(self):
        super().setUp()
        self.project = Project(
            id="proj-router",
            name="router-repo",
            path="/tmp/router-repo",
            git_branch="master",
            is_active=True,
        )
        self.db.add(self.project)
        self.db.commit()

    @patch("threading.Thread")
    def test_trigger_run_success(self, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        payload = {
            "target_type": "issue",
            "target_id": "42",
            "auto_approve": False,
        }
        res = self.client.post("/api/runs/", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data["id"].startswith("run_"))
        self.assertEqual(data["project_id"], self.project.id)
        self.assertEqual(data["status"], "QUEUED")
        self.assertEqual(data["target_id"], "42")

    def test_trigger_run_no_active_project_returns_400(self):
        self.project.is_active = False
        self.db.commit()

        payload = {"target_id": "10"}
        res = self.client.post("/api/runs/", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("No active project found", res.json()["detail"])

    def test_list_runs_endpoint(self):
        run1 = Run(id="run-list-1", project_id=self.project.id, target_type="issue", target_id="1", status="QUEUED")
        run2 = Run(id="run-list-2", project_id=self.project.id, target_type="session", target_id="s1", status="COMPLETED")
        runs_repo.create(self.db, run1)
        runs_repo.create(self.db, run2)

        # 1. List all runs for active project
        res = self.client.get("/api/runs/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["runs"]), 2)

        # 2. Filter by status
        res_filtered = self.client.get("/api/runs/?status=COMPLETED")
        self.assertEqual(res_filtered.status_code, 200)
        data_filtered = res_filtered.json()
        self.assertEqual(data_filtered["total"], 1)
        self.assertEqual(data_filtered["runs"][0]["id"], "run-list-2")

    def test_get_run_detail(self):
        run = Run(id="run-detail-1", project_id=self.project.id, target_type="issue", target_id="5", status="RUNNING")
        runs_repo.create(self.db, run)

        res = self.client.get("/api/runs/run-detail-1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], "run-detail-1")
        self.assertEqual(data["status"], "RUNNING")

        # 404 for missing
        res_missing = self.client.get("/api/runs/missing")
        self.assertEqual(res_missing.status_code, 404)

    @patch("agy_automation.api.modules.runs.service.prepare_review_data")
    def test_get_run_diff(self, mock_prepare):
        mock_prepare.return_value = {
            "diff_stat": "2 files changed",
            "diff_snippet": "+ modifications",
            "commits": ["commit 1"],
        }
        run = Run(
            id="run-diff-api",
            project_id=self.project.id,
            target_type="issue",
            target_id="12",
            status="AWAITING_REVIEW",
            worktree_name="worktree-issue-12",
            branch_name="issue-12",
        )
        runs_repo.create(self.db, run)

        res = self.client.get("/api/runs/run-diff-api/diff")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["diff_stat"], "2 files changed")
        self.assertEqual(data["commits"], ["commit 1"])

    def test_review_run_endpoint(self):
        run = Run(
            id="run-review-api",
            project_id=self.project.id,
            target_type="issue",
            target_id="12",
            status=RunStatus.AWAITING_REVIEW.value,
        )
        runs_repo.create(self.db, run)
        service.run_manager.register_run("run-review-api")

        payload = {"approved": True, "push": False}
        res = self.client.put("/api/runs/run-review-api/review", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["run_id"], "run-review-api")
        self.assertTrue(data["merged"])

    def test_stream_run_logs_sse_endpoint(self):
        run = Run(
            id="run-stream-api",
            project_id=self.project.id,
            target_type="issue",
            target_id="8",
            status="COMPLETED",
        )
        runs_repo.create(self.db, run)

        res = self.client.get("/api/runs/run-stream-api/stream")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers.get("content-type", ""))
