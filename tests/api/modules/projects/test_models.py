"""Layer 1: Unit tests for Projects SQLAlchemy ORM models."""

import unittest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from agy_automation.api.modules.projects.models import Project
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestProjectModel(InMemoryDatabaseTestCase):
    """Test ORM model attributes, defaults, and constraints."""

    def test_project_model_defaults_and_types(self):
        project = Project(
            name="demo-repo",
            path="/tmp/demo-repo",
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        self.assertIsNotNone(project.id)
        self.assertEqual(len(project.id), 36)  # UUID4 string
        self.assertEqual(project.name, "demo-repo")
        self.assertEqual(project.path, "/tmp/demo-repo")
        self.assertEqual(project.git_remote, "")
        self.assertEqual(project.git_branch, "")
        self.assertEqual(project.instructions_path, "")
        self.assertFalse(project.is_active)
        self.assertIsInstance(project.created_at, datetime)
        self.assertIsInstance(project.updated_at, datetime)

    def test_project_path_unique_constraint(self):
        p1 = Project(name="repo1", path="/unique/path")
        p2 = Project(name="repo2", path="/unique/path")
        self.db.add(p1)
        self.db.commit()

        self.db.add(p2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
