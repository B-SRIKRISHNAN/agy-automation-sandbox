"""Tests for Runs service and coordination layer."""

import subprocess
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.runs import repository as runs_repo
from agy_automation.api.modules.runs import service
from agy_automation.api.modules.runs.models import Run
from agy_automation.api.modules.runs.schemas import RunCreateRequest, RunReviewRequest, RunStatus
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestRunService(InMemoryDatabaseTestCase):
    """Test suite validating run lifecycle, coordination, and resumption in RunService."""

    def setUp(self):
        super().setUp()
        self.project = Project(
            id="proj-svc",
            name="service-repo",
            path="/tmp/service-repo",
            git_branch="main",
            is_active=True,
        )
        self.db.add(self.project)
        self.db.commit()

    def test_start_run_no_active_project_raises_400(self):
        self.project.is_active = False
        self.db.commit()

        req = RunCreateRequest(target_id="12")
        with self.assertRaises(HTTPException) as ctx:
            service.start_run(self.db, req)
        self.assertEqual(ctx.exception.status_code, 400)

    @patch("threading.Thread")
    def test_start_run_spawns_worker_and_registers(self, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        req = RunCreateRequest(
            project_id=self.project.id,
            target_type="issue",
            target_id="42",
            auto_approve=False,
            conversation_id="conv-123",
        )
        run = service.start_run(self.db, req)

        self.assertIsNotNone(run.id)
        self.assertEqual(run.project_id, self.project.id)
        self.assertEqual(run.target_id, "42")
        self.assertEqual(run.status, RunStatus.QUEUED.value)
        self.assertEqual(run.conversation_id, "conv-123")
        self.assertEqual(run.worktree_name, "worktree-issue-42")
        self.assertEqual(run.branch_name, "issue-42")
        self.assertEqual(run.container_name, "agy-sandbox-service-repo-worktree-issue-42")
        mock_thread.start.assert_called_once()

    def test_run_manager_coordination_lifecycle(self):
        mgr = service.RunManager()
        run_id = "test-coord-1"

        mgr.register_run(run_id)
        self.assertTrue(mgr.is_waiting(run_id))

        # Test resolving decision
        resolved = mgr.resolve_decision(run_id, approved=True, push=True)
        self.assertTrue(resolved)
        self.assertFalse(mgr.is_waiting(run_id))
        self.assertTrue(mgr.get_push_decision(run_id))

        # Test wait_for_decision returns the approved value immediately
        decision = mgr.wait_for_decision(run_id, timeout=0.1)
        self.assertTrue(decision)

        mgr.cleanup_run(run_id)
        self.assertFalse(mgr.is_waiting(run_id))

    def test_submit_review_run_not_found_raises_404(self):
        req = RunReviewRequest(approved=True)
        with self.assertRaises(HTTPException) as ctx:
            service.submit_review(self.db, "missing-run", req)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_submit_review_not_awaiting_review_raises_400(self):
        run = Run(
            id="run-queued",
            project_id=self.project.id,
            target_type="issue",
            target_id="1",
            status=RunStatus.RUNNING.value,
        )
        runs_repo.create(self.db, run)

        req = RunReviewRequest(approved=True)
        with self.assertRaises(HTTPException) as ctx:
            service.submit_review(self.db, "run-queued", req)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_submit_review_active_worker_unblocks(self):
        run = Run(
            id="run-active-waiting",
            project_id=self.project.id,
            target_type="issue",
            target_id="1",
            status=RunStatus.AWAITING_REVIEW.value,
        )
        runs_repo.create(self.db, run)
        service.run_manager.register_run("run-active-waiting")

        req = RunReviewRequest(approved=True, push=False)
        resp = service.submit_review(self.db, "run-active-waiting", req)

        self.assertEqual(resp.status, "PROCESSING")
        self.assertTrue(resp.merged)
        self.assertFalse(resp.pushed)

    @patch("agy_automation.api.modules.runs.service.push_changes")
    @patch("agy_automation.api.modules.runs.service.review_and_merge")
    def test_submit_review_resumption_offline_merge_and_push(self, mock_merge, mock_push):
        mock_merge.return_value = True
        mock_push.return_value = True

        run = Run(
            id="run-resumed",
            project_id=self.project.id,
            target_type="issue",
            target_id="1",
            status=RunStatus.AWAITING_REVIEW.value,
            worktree_name="worktree-issue-1",
            branch_name="issue-1",
            base_branch="main",
        )
        runs_repo.create(self.db, run)
        # Ensure not in run_manager (simulating server reboot)
        service.run_manager.cleanup_run("run-resumed")

        req = RunReviewRequest(approved=True, push=True)
        resp = service.submit_review(self.db, "run-resumed", req)

        self.assertEqual(resp.status, RunStatus.COMPLETED.value)
        self.assertTrue(resp.merged)
        self.assertTrue(resp.pushed)
        mock_merge.assert_called_once()
        mock_push.assert_called_once()

        updated_run = runs_repo.get_by_id(self.db, "run-resumed")
        self.assertEqual(updated_run.status, RunStatus.COMPLETED.value)

    def test_submit_review_resumption_rejected_marks_aborted(self):
        run = Run(
            id="run-reject",
            project_id=self.project.id,
            target_type="session",
            target_id="scratch",
            status=RunStatus.AWAITING_REVIEW.value,
        )
        runs_repo.create(self.db, run)
        service.run_manager.cleanup_run("run-reject")

        req = RunReviewRequest(approved=False)
        resp = service.submit_review(self.db, "run-reject", req)

        self.assertEqual(resp.status, RunStatus.ABORTED.value)
        self.assertFalse(resp.merged)

        updated_run = runs_repo.get_by_id(self.db, "run-reject")
        self.assertEqual(updated_run.status, RunStatus.ABORTED.value)

    @patch("agy_automation.api.modules.runs.service.prepare_review_data")
    def test_get_run_diff_success(self, mock_prepare):
        mock_prepare.return_value = {
            "diff_stat": "1 file changed, 5 insertions(+)",
            "diff_snippet": "+ hello world",
            "commits": ["commit 1: fix issue"],
        }
        run = Run(
            id="run-diff-test",
            project_id=self.project.id,
            target_type="issue",
            target_id="7",
            status=RunStatus.AWAITING_REVIEW.value,
            worktree_name="worktree-issue-7",
            branch_name="issue-7",
        )
        runs_repo.create(self.db, run)

        diff_resp = service.get_run_diff(self.db, "run-diff-test")
        self.assertEqual(diff_resp.diff_stat, "1 file changed, 5 insertions(+)")
        self.assertEqual(len(diff_resp.commits), 1)

    def test_abort_run_not_found_raises_404(self):
        with self.assertRaises(HTTPException) as ctx:
            service.abort_run(self.db, "missing-abort-run")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_abort_run_active_marks_aborted(self):
        run = Run(
            id="run-to-abort",
            project_id=self.project.id,
            target_type="issue",
            target_id="15",
            status=RunStatus.RUNNING.value,
        )
        runs_repo.create(self.db, run)
        service.run_manager.register_run("run-to-abort")

        aborted = service.abort_run(self.db, "run-to-abort")
        self.assertEqual(aborted.status, RunStatus.ABORTED.value)
        self.assertIn("Aborted by user", aborted.error_message)
        self.assertTrue(service.run_manager.is_aborted("run-to-abort"))

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_abort_run_terminates_specific_container(self, mock_which, mock_subproc):
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd == "docker" else None
        run = Run(
            id="run-container-abort",
            project_id=self.project.id,
            target_type="issue",
            target_id="15",
            container_name="agy-sandbox-service-repo-worktree-issue-15",
            status=RunStatus.RUNNING.value,
        )
        runs_repo.create(self.db, run)
        service.run_manager.register_run("run-container-abort")

        service.abort_run(self.db, "run-container-abort")
        mock_subproc.assert_called_with(
            ["/usr/bin/docker", "rm", "-f", "agy-sandbox-service-repo-worktree-issue-15"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )

    def test_abort_run_idempotent_on_completed(self):
        run = Run(
            id="run-already-completed",
            project_id=self.project.id,
            target_type="issue",
            target_id="16",
            status=RunStatus.COMPLETED.value,
        )
        runs_repo.create(self.db, run)

        result = service.abort_run(self.db, "run-already-completed")
        self.assertEqual(result.status, RunStatus.COMPLETED.value)
