"""Tests for system and quota Pydantic v2 schemas."""

import unittest
from datetime import datetime, timezone

from agy_automation.api.modules.system.schemas import (
    QuotaBucket,
    QuotaGroup,
    QuotaResponse,
)


class TestQuotaSchemas(unittest.TestCase):
    """Test suite validating quota schemas and serialization."""

    def test_quota_bucket_schema(self):
        bucket = QuotaBucket(
            id="gemini-5h",
            name="Five Hour Limit Remaining",
            description="5-hour rolling quota",
            window="5h",
            remaining_fraction=0.975,
            remaining_percent=98,
            reset_time="2026-11-10T07:43:00Z",
        )
        self.assertEqual(bucket.id, "gemini-5h")
        self.assertEqual(bucket.remaining_fraction, 0.975)
        self.assertEqual(bucket.remaining_percent, 98)
        self.assertEqual(bucket.window, "5h")

    def test_quota_group_schema(self):
        bucket = QuotaBucket(
            id="gemini-weekly",
            name="Weekly Limit Remaining",
            window="weekly",
            remaining_fraction=1.0,
            remaining_percent=100,
        )
        group = QuotaGroup(
            name="Gemini Models",
            description="Gemini Flash & Pro",
            buckets=[bucket],
        )
        self.assertEqual(group.name, "Gemini Models")
        self.assertEqual(len(group.buckets), 1)
        self.assertEqual(group.buckets[0].id, "gemini-weekly")

    def test_quota_response_serialization(self):
        now = datetime.now(timezone.utc)
        resp = QuotaResponse(
            description="Overall quota description",
            groups=[],
            cached=True,
            updated_at=now,
            error=None,
        )
        data = resp.model_dump()
        self.assertEqual(data["description"], "Overall quota description")
        self.assertTrue(data["cached"])
        self.assertEqual(data["groups"], [])
        self.assertIsNone(data["error"])
