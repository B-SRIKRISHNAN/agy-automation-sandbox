"""Tests for Run SQLAlchemy 2.0 ORM model."""

from datetime import datetime

from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.runs.models import Run
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestRunModel(InMemoryDatabaseTestCase):
    """Test suite validating Run model constraints and schema relationships."""

    def test_run_model_defaults_and_relationships(self):
        # 1. Create a parent project
        project = Project(
            id="proj-123",
            name="demo-repo",
            path="/tmp/demo-repo",
            git_branch="main",
            is_active=True,
        )
        self.db.add(project)
        self.db.commit()

        # 2. Create a Run targeting this project
        run = Run(
            id="run-test-001",
            project_id="proj-123",
            target_type="issue",
            target_id="42",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # 3. Assert defaults
        self.assertEqual(run.id, "run-test-001")
        self.assertEqual(run.project_id, "proj-123")
        self.assertEqual(run.target_type, "issue")
        self.assertEqual(run.target_id, "42")
        self.assertEqual(run.status, "QUEUED")
        self.assertEqual(run.base_branch, "master")
        self.assertFalse(run.auto_approve)
        self.assertEqual(run.engine, "auto")
        self.assertIsNone(run.worktree_name)
        self.assertIsNone(run.branch_name)
        self.assertIsNone(run.conversation_id)
        self.assertIsNone(run.finished_at)
        self.assertIsInstance(run.created_at, datetime)
        self.assertIsInstance(run.updated_at, datetime)

        # 4. Relationship navigation
        self.assertIsNotNone(run.project)
        self.assertEqual(run.project.name, "demo-repo")
        self.assertEqual(len(project.runs), 1)
        self.assertEqual(project.runs[0].id, "run-test-001")
