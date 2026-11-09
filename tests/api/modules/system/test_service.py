"""Tests for quota service, parsing, and TTL caching."""

import json
import subprocess
import time
import unittest
from unittest.mock import MagicMock, patch

from agy_automation.api.modules.system import service

SAMPLE_AGY_USAGE_OUTPUT = {
    "command": {
        "name": "usage",
        "data": {
            "description": "Quota pools for active tiers.",
            "groups": [
                {
                    "name": "Gemini Models",
                    "description": "Models: Gemini Flash, Gemini Pro",
                    "buckets": [
                        {
                            "id": "gemini-weekly",
                            "name": "Weekly Limit Remaining",
                            "description": "Weekly bucket",
                            "window": "weekly",
                            "remaining_fraction": 0.9928,
                            "reset_time": "2026-11-16T21:13:44Z",
                        },
                        {
                            "id": "gemini-5h",
                            "name": "Five Hour Limit Remaining",
                            "description": "5-hour bucket",
                            "window": "5h",
                            "remaining_fraction": 0.9750,
                            "reset_time": "2026-11-10T02:13:44Z",
                        },
                    ],
                },
                {
                    "name": "Claude and GPT models",
                    "description": "Models: Claude Opus, Claude Sonnet",
                    "buckets": [
                        {
                            "id": "3p-weekly",
                            "name": "Weekly Limit Remaining",
                            "window": "weekly",
                            "remaining_fraction": 1.0,
                            "reset_time": "2026-11-16T21:45:07Z",
                        },
                    ],
                },
            ],
        },
    }
}


class TestQuotaService(unittest.TestCase):
    """Test suite validating quota parsing, subprocess execution, and TTL caching."""

    def setUp(self):
        service.reset_quota_cache()

    def tearDown(self):
        service.reset_quota_cache()

    def test_parse_quota_data(self):
        parsed = service.parse_quota_data(SAMPLE_AGY_USAGE_OUTPUT)
        self.assertEqual(len(parsed.groups), 2)
        self.assertEqual(parsed.groups[0].name, "Gemini Models")
        self.assertEqual(len(parsed.groups[0].buckets), 2)

        weekly = parsed.groups[0].buckets[0]
        self.assertEqual(weekly.id, "gemini-weekly")
        self.assertEqual(weekly.remaining_percent, 99)
        self.assertEqual(weekly.window, "weekly")

        five_h = parsed.groups[0].buckets[1]
        self.assertEqual(five_h.id, "gemini-5h")
        self.assertEqual(five_h.remaining_percent, 98)
        self.assertEqual(five_h.window, "5h")

        claude = parsed.groups[1]
        self.assertEqual(claude.buckets[0].remaining_percent, 100)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_fetch_agy_quota_caching(self, mock_which, mock_subproc):
        mock_which.return_value = "/usr/local/bin/agy"
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(SAMPLE_AGY_USAGE_OUTPUT)
        mock_subproc.return_value = mock_res

        # 1. First call: fetches fresh
        q1 = service.fetch_agy_quota(force_refresh=False)
        self.assertFalse(q1.cached)
        self.assertEqual(len(q1.groups), 2)
        self.assertEqual(mock_subproc.call_count, 1)

        # 2. Second call immediately: returns cached
        q2 = service.fetch_agy_quota(force_refresh=False)
        self.assertTrue(q2.cached)
        self.assertEqual(mock_subproc.call_count, 1)

        # 3. Third call with force_refresh: calls subprocess again
        q3 = service.fetch_agy_quota(force_refresh=True)
        self.assertFalse(q3.cached)
        self.assertEqual(mock_subproc.call_count, 2)

    @patch("shutil.which")
    def test_fetch_agy_quota_missing_binary(self, mock_which):
        mock_which.return_value = None
        resp = service.fetch_agy_quota()
        self.assertIn("not installed", resp.error.lower())
        self.assertEqual(resp.groups, [])

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_fetch_agy_quota_timeout(self, mock_which, mock_subproc):
        mock_which.return_value = "/usr/local/bin/agy"
        mock_subproc.side_effect = subprocess.TimeoutExpired(cmd=["agy"], timeout=15)

        resp = service.fetch_agy_quota()
        self.assertIn("Timed out", resp.error)
        self.assertEqual(resp.groups, [])

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_fetch_agy_quota_subprocess_error(self, mock_which, mock_subproc):
        mock_which.return_value = "/usr/local/bin/agy"
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stderr = "Error: user not authenticated"
        mock_subproc.return_value = mock_res

        resp = service.fetch_agy_quota()
        self.assertIn("user not authenticated", resp.error)
        self.assertEqual(resp.groups, [])
