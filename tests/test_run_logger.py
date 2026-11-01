"""Tests for OS-agnostic run logger, metadata envelope, and NDJSON streaming."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.run_logger import (
    RunSession,
    generate_run_id,
    get_default_runs_dir,
    sanitize_filename_component,
)


class TestRunLogger(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runs_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_filename_component(self):
        self.assertEqual(sanitize_filename_component("my-project"), "my-project")
        self.assertEqual(sanitize_filename_component("Project / with: invalid! chars*"), "Project_with_invalid_chars")
        self.assertEqual(sanitize_filename_component(""), "run")

    def test_generate_run_id(self):
        run_id = generate_run_id("my-repo", "issue-42")
        self.assertIn("my-repo", run_id)
        self.assertIn("issue-42", run_id)
        # Verify characters are safe across all OSes
        self.assertTrue(all(c.isalnum() or c in ("-", "_", ".") for c in run_id))

    def test_get_default_runs_dir_override(self):
        os.environ["AGY_RUNS_DIR"] = str(self.runs_dir)
        try:
            resolved = get_default_runs_dir()
            self.assertEqual(resolved, self.runs_dir)
            self.assertTrue(resolved.is_dir())
        finally:
            del os.environ["AGY_RUNS_DIR"]

    def test_run_session_lifecycle(self):
        session = RunSession(
            project_name="test-project",
            target="42",
            base_runs_dir=self.runs_dir,
        )

        # 1. Verify directory and initial files
        self.assertTrue(session.run_dir.is_dir())
        self.assertTrue(session.metadata_file.is_file())
        self.assertTrue(session.events_file.is_file())

        # 2. Inspect initial metadata (status: RUNNING)
        with open(session.metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["status"], "RUNNING")
        self.assertEqual(meta["target_project"]["name"], "test-project")
        self.assertEqual(meta["context"]["issue_number"], 42)
        self.assertIsNotNone(meta["timing"]["started_at"])
        self.assertIsNone(meta["timing"]["ended_at"])

        # 3. Update context
        session.update_context(
            repo_path="/path/to/test-project",
            base_branch="main",
            branch_name="issue-42",
            worktree_name="worktree-issue-42",
            engine="podman",
            issue_title="Fix tokenizer error",
        )

        with open(session.metadata_file, "r", encoding="utf-8") as f:
            meta2 = json.load(f)
        self.assertEqual(meta2["git"]["base_branch"], "main")
        self.assertEqual(meta2["git"]["branch_name"], "issue-42")
        self.assertEqual(meta2["context"]["issue_title"], "Fix tokenizer error")

        # 4. Log custom event
        session.log_event("coordinator", "fetch", "issue_fetched", {"author": "octocat"})

        # 5. Log native agy stream-json events
        # A: Tool active
        raw_tool_active = json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 2,
                "state": "ACTIVE",
                "step_type": "tool",
                "tool_name": "run_command",
                "tool_info": {
                    "name": "run_command",
                    "parameters": {"CommandLine": "pytest"}
                }
            }
        })
        session.log_raw_agent_event(raw_tool_active)

        # B: Step usage
        raw_step_usage = json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 3,
                "state": "DONE",
                "step_type": "agent_response",
                "duration_seconds": 2.5,
                "usage": {
                    "input_tokens": 500,
                    "output_tokens": 50,
                    "thinking_tokens": 20,
                    "total_tokens": 550
                }
            }
        })
        session.log_raw_agent_event(raw_step_usage)

        # Verify tool tally and token accumulation
        with open(session.metadata_file, "r", encoding="utf-8") as f:
            meta3 = json.load(f)
        self.assertEqual(meta3["metrics"]["tool_calls"].get("run_command"), 1)
        self.assertEqual(meta3["metrics"]["total_tokens"], 550)

        # C: Final result event
        raw_result = json.dumps({
            "event": "result",
            "result": {
                "status": "SUCCESS",
                "duration_seconds": 12.4,
                "num_turns": 3,
                "usage": {
                    "input_tokens": 1200,
                    "output_tokens": 150,
                    "thinking_tokens": 40,
                    "total_tokens": 1350
                }
            }
        })
        session.log_raw_agent_event(raw_result)

        # 6. Finish session
        session.finish(
            status="COMPLETED",
            merged=True,
            pushed=True,
            final_commit_hash="abc123456",
            final_commit_subject="fix(parser): resolve tokenizer (Fixes #42)",
        )

        with open(session.metadata_file, "r", encoding="utf-8") as f:
            meta_final = json.load(f)

        self.assertEqual(meta_final["status"], "COMPLETED")
        self.assertTrue(meta_final["results"]["merged"])
        self.assertTrue(meta_final["results"]["pushed"])
        self.assertEqual(meta_final["metrics"]["total_turns"], 3)
        self.assertEqual(meta_final["metrics"]["total_tokens"], 1350)
        self.assertIsNotNone(meta_final["timing"]["ended_at"])
        self.assertGreater(meta_final["timing"]["duration_seconds"], 0)

        # 7. Verify events.jsonl has chronological lines
        with open(session.events_file, "r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]

        self.assertGreater(len(events), 4)
        self.assertEqual(events[0]["phase"], "fetch")
        self.assertEqual(events[-1]["event"], "session_finished")

    def test_session_abort_recording(self):
        session = RunSession(
            project_name="abort-test",
            target="session-cancel",
            base_runs_dir=self.runs_dir,
        )

        session.finish(
            status="ABORTED",
            error="User aborted execution (Ctrl+C)",
        )

        with open(session.metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["status"], "ABORTED")
        self.assertEqual(meta["error"], "User aborted execution (Ctrl+C)")
        self.assertFalse(meta["results"]["merged"])


if __name__ == "__main__":
    unittest.main()
