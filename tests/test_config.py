"""Tests for config and environment detection."""

import sys
import tempfile
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.config import (
    ensure_repo_exclude,
    find_agent_instructions,
    get_target_repo,
    get_toolkit_root,
)


class TestConfig(unittest.TestCase):

    def test_get_toolkit_root(self):
        root = get_toolkit_root()
        self.assertTrue((root / "docker-compose.sandbox.yml").is_file() or (root / "scripts").is_dir())

    def test_get_target_repo(self):
        repo = get_target_repo()
        self.assertTrue((repo / ".git").exists())

    def test_ensure_repo_exclude(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            info_dir = git_dir / "info"
            info_dir.mkdir()
            exclude_file = info_dir / "exclude"
            exclude_file.write_text("# existing comments\n*.tmp\n", encoding="utf-8")

            # First run appends
            appended = ensure_repo_exclude(tmp_path)
            self.assertTrue(appended)
            content = exclude_file.read_text(encoding="utf-8")
            self.assertIn(".worktrees/", content)
            self.assertIn("ISSUE_CONTEXT.md", content)

            # Second run is idempotent
            appended2 = ensure_repo_exclude(tmp_path)
            self.assertFalse(appended2)

    def test_find_agent_instructions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # When missing
            found_path, found_name = find_agent_instructions(tmp_path)
            self.assertIsNone(found_path)
            self.assertEqual(found_name, "")

            # With mixed case
            instr_file = tmp_path / "AGENT_instructions.MD"
            instr_file.write_text("# Instructions\n", encoding="utf-8")

            found_path, found_name = find_agent_instructions(tmp_path)
            self.assertIsNotNone(found_path)
            self.assertEqual(found_name, "AGENT_instructions.MD")


if __name__ == "__main__":
    unittest.main()
