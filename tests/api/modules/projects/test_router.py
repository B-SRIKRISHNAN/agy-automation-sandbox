"""Layer 5: Controller and integration tests for Projects router using TestClient."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.api.test_helpers import InMemoryDatabaseTestCase


class TestProjectsRouter(InMemoryDatabaseTestCase):
    """Integration test suite for /api/projects endpoints."""

    def test_health_check_and_timing_header(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok", "version": "1.0.0"})
        self.assertIn("x-process-time", resp.headers)

    def test_post_projects_relative_path_rejected_422(self):
        resp = self.client.post("/api/projects", json={"path": "relative/path"})
        self.assertEqual(resp.status_code, 422)

    def test_post_projects_non_git_dir_rejected_422(self):
        with tempfile.TemporaryDirectory() as td:
            resp = self.client.post("/api/projects", json={"path": td})
            self.assertEqual(resp.status_code, 422)
            self.assertIn("not a Git repository", resp.json()["detail"])

    @patch("agy_automation.api.modules.projects.service.subprocess.run")
    def test_register_and_select_lifecycle(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n")

        # 1. Active project is 204 initially
        resp = self.client.get("/api/projects/active")
        self.assertEqual(resp.status_code, 204)

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            p1_path = Path(td1)
            (p1_path / ".git").mkdir()
            p2_path = Path(td2)
            (p2_path / ".git").mkdir()

            # 2. Register first project (Expect 201 Created and auto-active)
            r1 = self.client.post("/api/projects", json={"path": str(p1_path)})
            self.assertEqual(r1.status_code, 201)
            p1_data = r1.json()
            self.assertTrue(p1_data["is_active"])
            p1_id = p1_data["id"]

            # 3. Register second project (Expect 201 Created and inactive)
            r2 = self.client.post("/api/projects", json={"path": str(p2_path)})
            self.assertEqual(r2.status_code, 201)
            p2_data = r2.json()
            self.assertFalse(p2_data["is_active"])
            p2_id = p2_data["id"]

            # 4. Active project is now p1
            active_resp = self.client.get("/api/projects/active")
            self.assertEqual(active_resp.status_code, 200)
            self.assertEqual(active_resp.json()["id"], p1_id)

            # 5. List projects
            list_resp = self.client.get("/api/projects")
            self.assertEqual(list_resp.status_code, 200)
            self.assertEqual(list_resp.json()["total"], 2)

            # 6. Re-register p1 idempotently (Expect 200 OK)
            r1_re = self.client.post("/api/projects", json={"path": str(p1_path)})
            self.assertEqual(r1_re.status_code, 200)
            self.assertEqual(r1_re.json()["id"], p1_id)

            # 7. Select p2 as active (using POST)
            sel_resp = self.client.post(f"/api/projects/{p2_id}/select")
            self.assertEqual(sel_resp.status_code, 200)
            self.assertTrue(sel_resp.json()["is_active"])

            # 7b. Select p1 as active using PUT alias
            sel_put_resp = self.client.put(f"/api/projects/{p1_id}/select")
            self.assertEqual(sel_put_resp.status_code, 200)
            self.assertTrue(sel_put_resp.json()["is_active"])

            # Re-select p2 with POST for deletion test
            self.client.post(f"/api/projects/{p2_id}/select")

            # Verify active is now p2
            active_resp2 = self.client.get("/api/projects/active")
            self.assertEqual(active_resp2.status_code, 200)
            self.assertEqual(active_resp2.json()["id"], p2_id)

            # 8. Select non-existent project returns 404
            sel_404 = self.client.post("/api/projects/unknown-uuid/select")
            self.assertEqual(sel_404.status_code, 404)

            # 9. Delete p2 (active), p1 should be promoted
            del_resp = self.client.delete(f"/api/projects/{p2_id}")
            self.assertEqual(del_resp.status_code, 200)

            active_resp3 = self.client.get("/api/projects/active")
            self.assertEqual(active_resp3.status_code, 200)
            self.assertEqual(active_resp3.json()["id"], p1_id)

            # 10. Delete non-existent project returns 404
            del_404 = self.client.delete("/api/projects/unknown-uuid")
            self.assertEqual(del_404.status_code, 404)


if __name__ == "__main__":
    unittest.main()
