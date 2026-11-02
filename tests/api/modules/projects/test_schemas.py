"""Layer 2: Unit tests for Projects Pydantic v2 validation schemas."""

import unittest
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from agy_automation.api.modules.projects.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
)


class TestProjectSchemas(unittest.TestCase):
    """Test Pydantic schema validation rules."""

    def test_valid_absolute_path_accepted(self):
        schema = ProjectCreate(path="/home/user/my-repo")
        self.assertEqual(schema.path, str(Path("/home/user/my-repo").resolve()))

    def test_relative_path_rejected(self):
        invalid_paths = [
            "my-repo",
            "./my-repo",
            "../other-repo",
            "foo/bar/baz",
        ]
        for p in invalid_paths:
            with self.subTest(path=p):
                with self.assertRaises(ValidationError) as ctx:
                    ProjectCreate(path=p)
                self.assertIn("must be an absolute path", str(ctx.exception))

    def test_empty_path_rejected(self):
        for empty in ["", "   ", "\t\n"]:
            with self.subTest(empty=empty):
                with self.assertRaises(ValidationError) as ctx:
                    ProjectCreate(path=empty)
                self.assertIn("cannot be empty", str(ctx.exception))

    def test_project_response_serialization(self):
        now = datetime.now(timezone.utc)
        data = {
            "id": "12345678-1234-1234-1234-123456789012",
            "name": "test-repo",
            "path": "/abs/test-repo",
            "git_remote": "git@github.com:org/repo.git",
            "git_branch": "main",
            "instructions_path": "/abs/test-repo/.antigravity/instructions.md",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        resp = ProjectResponse.model_validate(data)
        self.assertEqual(resp.id, data["id"])
        self.assertEqual(resp.name, "test-repo")
        self.assertTrue(resp.is_active)

    def test_project_list_response_serialization(self):
        now = datetime.now(timezone.utc)
        item = ProjectResponse(
            id="1",
            name="p1",
            path="/p1",
            git_remote="",
            git_branch="main",
            instructions_path="",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        list_resp = ProjectListResponse(projects=[item], total=1)
        self.assertEqual(len(list_resp.projects), 1)
        self.assertEqual(list_resp.total, 1)


if __name__ == "__main__":
    unittest.main()
