"""Layer 3: Unit tests for Projects repository and DB queries."""

import unittest

from agy_automation.api.modules.projects import repository
from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.projects.service import ValidatedProjectMetadata
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestProjectRepository(InMemoryDatabaseTestCase):
    """Test repository operations with isolated in-memory SQLite."""

    def test_first_project_auto_activates(self):
        meta1 = ValidatedProjectMetadata(
            name="proj1",
            path="/path/proj1",
            git_remote="",
            git_branch="main",
            instructions_path="",
        )
        p1, created1 = repository.register_or_update(self.db, meta1)
        self.assertTrue(created1)
        self.assertTrue(p1.is_active)

        # Second project should not be active
        meta2 = ValidatedProjectMetadata(
            name="proj2",
            path="/path/proj2",
            git_remote="",
            git_branch="master",
            instructions_path="",
        )
        p2, created2 = repository.register_or_update(self.db, meta2)
        self.assertTrue(created2)
        self.assertFalse(p2.is_active)

        active = repository.get_active(self.db)
        self.assertIsNotNone(active)
        self.assertEqual(active.id, p1.id)

    def test_register_existing_project_updates_metadata(self):
        meta = ValidatedProjectMetadata(
            name="proj1",
            path="/path/proj1",
            git_remote="old_remote",
            git_branch="old_branch",
            instructions_path="",
        )
        p1, created = repository.register_or_update(self.db, meta)
        self.assertTrue(created)
        self.assertEqual(p1.git_remote, "old_remote")

        # Update
        meta_updated = ValidatedProjectMetadata(
            name="proj1-renamed",
            path="/path/proj1",
            git_remote="new_remote",
            git_branch="new_branch",
            instructions_path="/path/proj1/instructions.md",
        )
        p2, created2 = repository.register_or_update(self.db, meta_updated)
        self.assertFalse(created2)
        self.assertEqual(p2.id, p1.id)
        self.assertEqual(p2.name, "proj1-renamed")
        self.assertEqual(p2.git_remote, "new_remote")
        self.assertEqual(p2.git_branch, "new_branch")
        self.assertEqual(p2.instructions_path, "/path/proj1/instructions.md")

    def test_atomic_set_active(self):
        meta1 = ValidatedProjectMetadata("p1", "/path/p1", "", "main", "")
        meta2 = ValidatedProjectMetadata("p2", "/path/p2", "", "main", "")
        meta3 = ValidatedProjectMetadata("p3", "/path/p3", "", "main", "")

        p1, _ = repository.register_or_update(self.db, meta1)
        p2, _ = repository.register_or_update(self.db, meta2)
        p3, _ = repository.register_or_update(self.db, meta3)

        self.assertTrue(p1.is_active)
        self.assertFalse(p2.is_active)
        self.assertFalse(p3.is_active)

        # Switch to p2
        switched = repository.set_active(self.db, p2.id)
        self.assertIsNotNone(switched)
        self.assertTrue(switched.is_active)

        # Verify only 1 project has is_active == True
        active_count = self.db.query(Project).filter(Project.is_active.is_(True)).count()
        self.assertEqual(active_count, 1)

        self.db.refresh(p1)
        self.db.refresh(p2)
        self.db.refresh(p3)
        self.assertFalse(p1.is_active)
        self.assertTrue(p2.is_active)
        self.assertFalse(p3.is_active)

    def test_set_active_non_existent_returns_none(self):
        result = repository.set_active(self.db, "non-existent-uuid")
        self.assertIsNone(result)

    def test_delete_project_promotes_next_if_active(self):
        meta1 = ValidatedProjectMetadata("p1", "/path/p1", "", "main", "")
        meta2 = ValidatedProjectMetadata("p2", "/path/p2", "", "main", "")
        p1, _ = repository.register_or_update(self.db, meta1)
        p2, _ = repository.register_or_update(self.db, meta2)

        self.assertTrue(p1.is_active)

        # Delete active project p1
        deleted = repository.delete_project(self.db, p1.id)
        self.assertTrue(deleted)

        # p2 should now be promoted to active
        self.db.refresh(p2)
        self.assertTrue(p2.is_active)


if __name__ == "__main__":
    unittest.main()
