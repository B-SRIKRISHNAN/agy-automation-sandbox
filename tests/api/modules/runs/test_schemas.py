"""Tests for Runs Pydantic v2 schemas."""

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from agy_automation.api.modules.runs.schemas import (
    RunCreateRequest,
    RunDiffResponse,
    RunListResponse,
    RunResponse,
    RunReviewRequest,
    RunReviewResponse,
    RunStatus,
)


class TestRunSchemas(unittest.TestCase):
    """Test suite for validating Pydantic schemas in the runs module."""

    def test_run_create_request_valid(self):
        req = RunCreateRequest(
            target_type="issue",
            target_id="101",
            auto_approve=True,
            engine="podman",
            conversation_id="conv-xyz",
        )
        self.assertEqual(req.target_type, "issue")
        self.assertEqual(req.target_id, "101")
        self.assertTrue(req.auto_approve)
        self.assertEqual(req.engine, "podman")
        self.assertEqual(req.conversation_id, "conv-xyz")

    def test_run_create_request_empty_target_id_rejected(self):
        with self.assertRaises(ValidationError):
            RunCreateRequest(target_id="")

    def test_run_response_serialization(self):
        now = datetime.now(timezone.utc)
        resp = RunResponse(
            id="run-1",
            project_id="proj-1",
            target_type="session",
            target_id="test-session",
            status=RunStatus.RUNNING.value,
            base_branch="main",
            created_at=now,
            updated_at=now,
        )
        data = resp.model_dump()
        self.assertEqual(data["id"], "run-1")
        self.assertEqual(data["status"], "RUNNING")
        self.assertFalse(data["auto_approve"])

    def test_run_list_response(self):
        now = datetime.now(timezone.utc)
        item = RunResponse(
            id="run-1",
            project_id="proj-1",
            target_type="issue",
            target_id="5",
            status="QUEUED",
            created_at=now,
            updated_at=now,
        )
        collection = RunListResponse(runs=[item], total=1)
        self.assertEqual(collection.total, 1)
        self.assertEqual(len(collection.runs), 1)

    def test_run_review_request(self):
        req = RunReviewRequest(approved=True, push=True)
        self.assertTrue(req.approved)
        self.assertTrue(req.push)

        req_default = RunReviewRequest(approved=False)
        self.assertFalse(req_default.approved)
        self.assertFalse(req_default.push)

    def test_run_diff_response_defaults(self):
        diff = RunDiffResponse(
            run_id="run-99",
            base_branch="master",
            diff_stat="1 file changed",
            diff_snippet="+ new code",
        )
        self.assertEqual(diff.commits, [])
        self.assertEqual(diff.diff_stat, "1 file changed")
