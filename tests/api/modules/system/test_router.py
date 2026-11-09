"""Integration tests for system endpoints."""

from unittest.mock import MagicMock, patch

from tests.api.test_helpers import InMemoryDatabaseTestCase
from tests.api.modules.system.test_service import SAMPLE_AGY_USAGE_OUTPUT
from agy_automation.api.modules.system import service


class TestSystemRouter(InMemoryDatabaseTestCase):
    """Test suite validating system API routes."""

    def setUp(self):
        super().setUp()
        service.reset_quota_cache()

    def tearDown(self):
        super().tearDown()
        service.reset_quota_cache()

    @patch("agy_automation.api.modules.system.service.subprocess.run")
    @patch("shutil.which")
    def test_get_quota_endpoint(self, mock_which, mock_subproc):
        mock_which.return_value = "/usr/local/bin/agy"
        mock_res = MagicMock()
        mock_res.returncode = 0
        import json
        mock_res.stdout = json.dumps(SAMPLE_AGY_USAGE_OUTPUT)
        mock_subproc.return_value = mock_res

        # Test path without trailing slash
        res = self.client.get("/api/system/quota")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["cached"])
        self.assertEqual(len(data["groups"]), 2)
        self.assertEqual(data["groups"][0]["name"], "Gemini Models")
        self.assertEqual(data["groups"][0]["buckets"][0]["remaining_percent"], 99)

        # Test path with trailing slash (no redirect)
        res_slash = self.client.get("/api/system/quota/")
        self.assertEqual(res_slash.status_code, 200)
        data_slash = res_slash.json()
        self.assertTrue(data_slash["cached"])  # Served from TTL cache

    @patch("agy_automation.api.modules.system.service.subprocess.run")
    @patch("shutil.which")
    def test_get_quota_force_refresh(self, mock_which, mock_subproc):
        mock_which.return_value = "/usr/local/bin/agy"
        mock_res = MagicMock()
        mock_res.returncode = 0
        import json
        mock_res.stdout = json.dumps(SAMPLE_AGY_USAGE_OUTPUT)
        mock_subproc.return_value = mock_res

        # Call once to warm cache
        self.client.get("/api/system/quota")
        self.assertEqual(mock_subproc.call_count, 1)

        # Call with force_refresh=true
        res = self.client.get("/api/system/quota?force_refresh=true")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["cached"])
        self.assertEqual(mock_subproc.call_count, 2)

    def test_pwa_root_and_spa_fallback(self):
        # 1. Root index.html serving
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("Antigravity Mobile", res_root.text)

        # 2. Manifest serving
        res_manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(res_manifest.status_code, 200)

        # 3. SPA fallback to index.html for client-side navigation
        res_spa = self.client.get("/runs/active-run-id")
        self.assertEqual(res_spa.status_code, 200)
        self.assertIn("Antigravity Mobile", res_spa.text)
