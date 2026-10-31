"""Tests for permissionless session mode and name sanitization."""

import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.git_utils import sanitize_session_name
from agy_automation.orchestrator import run_pipeline


class TestSessionMode(unittest.TestCase):

    def test_sanitize_session_name_valid(self):
        self.assertEqual(sanitize_session_name("refactor-auth"), "refactor-auth")
        self.assertEqual(sanitize_session_name("my_task.v1"), "my_task.v1")

    def test_sanitize_session_name_spaces_and_special(self):
        self.assertEqual(sanitize_session_name("Fix Login & CORS!"), "fix-login-cors")
        self.assertEqual(sanitize_session_name("  feature/new-api  "), "feature-new-api")

    def test_sanitize_session_name_empty(self):
        self.assertEqual(sanitize_session_name(""), "session")
        self.assertEqual(sanitize_session_name("   "), "session")
        self.assertEqual(sanitize_session_name("!!!"), "session")

    def test_orchestrator_session_dry_run(self):
        repo_root = Path(__file__).resolve().parent.parent
        exit_code = run_pipeline(
            session_name="test-session-feature",
            dry_run=True,
            target_repo=repo_root,
        )
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
