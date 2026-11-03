"""Tests for Runs SQLAlchemy repository operations."""

from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.runs import repository as runs_repo
from agy_automation.api.modules.runs.models import Run
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestRunRepository(InMemoryDatabaseTestCase):
    """Test suite for repository CRUD operations on runs."""

    def setUp(self):
        super().setUp()
        self.project = Project(
            id="proj-alpha",
            name="repo-alpha",
            path="/tmp/repo-alpha",
            is_active=True,
        )
        self.db.add(self.project)
        self.db.commit()

    def test_create_and_get_by_id(self):
        run = Run(
            id="run-repo-1",
            project_id=self.project.id,
            target_type="issue",
            target_id="10",
        )
        created = runs_repo.create(self.db, run)
        self.assertEqual(created.id, "run-repo-1")

        fetched = runs_repo.get_by_id(self.db, "run-repo-1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.target_id, "10")

    def test_get_by_id_not_found_returns_none(self):
        self.assertIsNone(runs_repo.get_by_id(self.db, "non-existent"))

    def test_list_by_project_and_status(self):
        run1 = Run(id="run-1", project_id=self.project.id, target_type="issue", target_id="1", status="QUEUED")
        run2 = Run(id="run-2", project_id=self.project.id, target_type="issue", target_id="2", status="COMPLETED")
        runs_repo.create(self.db, run1)
        runs_repo.create(self.db, run2)

        # List all for project
        all_runs = runs_repo.list_by_project(self.db, project_id=self.project.id)
        self.assertEqual(len(all_runs), 2)

        # Filter by status
        completed = runs_repo.list_by_project(self.db, project_id=self.project.id, status="COMPLETED")
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].id, "run-2")

    def test_update_status_and_finished_at(self):
        run = Run(id="run-status", project_id=self.project.id, target_type="session", target_id="demo")
        runs_repo.create(self.db, run)

        updated = runs_repo.update_status(
            self.db,
            "run-status",
            status="FAILED",
            error_message="Exit code 1",
            finished=True,
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "FAILED")
        self.assertEqual(updated.error_message, "Exit code 1")
        self.assertIsNotNone(updated.finished_at)

    def test_update_details(self):
        run = Run(id="run-details", project_id=self.project.id, target_type="issue", target_id="99")
        runs_repo.create(self.db, run)

        updated = runs_repo.update_details(
            self.db,
            "run-details",
            worktree_name="worktree-issue-99",
            branch_name="issue-99",
            base_branch="develop",
            log_dir="/tmp/runs/run-details",
            conversation_id="conv-789",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.worktree_name, "worktree-issue-99")
        self.assertEqual(updated.branch_name, "issue-99")
        self.assertEqual(updated.base_branch, "develop")
        self.assertEqual(updated.log_dir, "/tmp/runs/run-details")
        self.assertEqual(updated.conversation_id, "conv-789")
