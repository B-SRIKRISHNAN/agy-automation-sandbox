"""Tests for system storage telemetry and orphan pruning."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.runs.models import Run
from agy_automation.api.modules.system import service
from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestSystemStorage(InMemoryDatabaseTestCase):
    """Test suite for storage breakdown and pruning logic."""

    def setUp(self):
        super().setUp()
        self.temp_repo = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.temp_repo.name)
        self.worktrees_dir = self.repo_dir / ".worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        self.project = Project(
            id="proj-storage",
            name="storage-repo",
            path=str(self.repo_dir),
            git_branch="master",
            is_active=True,
        )
        self.db.add(self.project)
        self.db.commit()

    def tearDown(self):
        super().tearDown()
        self.temp_repo.cleanup()

    def test_get_storage_info_distinguishes_active_and_orphaned(self):
        # Create an active worktree linked to a RUNNING run
        active_wt = self.worktrees_dir / "worktree-active-run"
        active_wt.mkdir()
        (active_wt / "test.txt").write_text("active content")

        active_run = Run(
            id="run-active-1",
            project_id=self.project.id,
            target_type="issue",
            target_id="10",
            status="RUNNING",
            worktree_name="worktree-active-run",
            branch_name="issue-10",
        )
        self.db.add(active_run)

        # Create an orphaned worktree
        orphan_wt = self.worktrees_dir / "worktree-orphaned-old"
        orphan_wt.mkdir()
        (orphan_wt / "large.txt").write_text("orphaned data" * 100)

        self.db.commit()

        info = service.get_storage_info(self.db, project_id=self.project.id)
        self.assertEqual(info.worktrees_total_count, 2)
        self.assertEqual(info.worktrees_orphaned_count, 1)

        orphans = [item for item in info.items if item.is_orphaned]
        self.assertEqual(len(orphans), 1)
        self.assertEqual(orphans[0].name, "worktree-orphaned-old")

        actives = [item for item in info.items if not item.is_orphaned]
        self.assertEqual(len(actives), 1)
        self.assertEqual(actives[0].name, "worktree-active-run")
        self.assertEqual(actives[0].run_id, "run-active-1")

    @patch("agy_automation.api.modules.system.service.cleanup_worktree")
    def test_prune_storage_cleans_only_orphaned(self, mock_cleanup):
        orphan_wt = self.worktrees_dir / "worktree-to-prune"
        orphan_wt.mkdir()
        (orphan_wt / "junk.txt").write_text("junk" * 50)

        res = service.prune_storage(self.db, project_id=self.project.id)
        mock_cleanup.assert_called_once()
        self.assertIn("worktree-to-prune", res.pruned_worktrees)
        self.assertGreater(res.reclaimed_bytes, 0)

    def test_storage_router_endpoints(self):
        res_info = self.client.get("/api/system/storage")
        self.assertEqual(res_info.status_code, 200)
        data = res_info.json()
        self.assertEqual(data["project_id"], self.project.id)

        with patch("agy_automation.api.modules.system.service.cleanup_worktree"):
            res_prune = self.client.post("/api/system/storage/prune")
            self.assertEqual(res_prune.status_code, 200)
            prune_data = res_prune.json()
            self.assertIn("Cleaned up", prune_data["message"])
