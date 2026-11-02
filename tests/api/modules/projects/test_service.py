"""Layer 4: Unit tests for Projects business logic and service layer."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from agy_automation.api.modules.projects import service


class TestProjectService(unittest.TestCase):
    """Test Git verification and metadata extraction logic."""

    def test_non_existent_directory_raises_422(self):
        with self.assertRaises(HTTPException) as ctx:
            service.inspect_git_repository("/non/existent/path/for/project")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("does not exist", str(ctx.exception.detail))

    def test_missing_git_directory_raises_422(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(HTTPException) as ctx:
                service.inspect_git_repository(td)
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertIn("not a Git repository", str(ctx.exception.detail))

    @patch("subprocess.run")
    def test_valid_git_repo_extraction(self, mock_run):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td)
            (repo_path / ".git").mkdir()

            # Mock git commands:
            # 1. rev-parse --is-inside-work-tree -> "true"
            # 2. remote get-url origin -> "git@github.com:example/repo.git"
            # 3. branch --show-current -> "master"
            def fake_run(cmd, *args, **kwargs):
                if "--is-inside-work-tree" in cmd:
                    return MagicMock(returncode=0, stdout="true\n")
                elif "remote" in cmd:
                    return MagicMock(returncode=0, stdout="git@github.com:example/repo.git\n")
                elif "branch" in cmd:
                    return MagicMock(returncode=0, stdout="master\n")
                return MagicMock(returncode=1, stdout="")

            mock_run.side_effect = fake_run

            meta = service.inspect_git_repository(str(repo_path))
            self.assertEqual(meta.path, str(repo_path.resolve()))
            self.assertEqual(meta.name, repo_path.name)
            self.assertEqual(meta.git_remote, "git@github.com:example/repo.git")
            self.assertEqual(meta.git_branch, "master")

    @patch("subprocess.run")
    def test_detects_custom_instructions_file(self, mock_run):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td)
            (repo_path / ".git").mkdir()
            instr_dir = repo_path / ".antigravity"
            instr_dir.mkdir()
            instr_file = instr_dir / "instructions.md"
            instr_file.write_text("Custom instruction content")

            mock_run.return_value = MagicMock(returncode=0, stdout="true\n")

            meta = service.inspect_git_repository(str(repo_path))
            self.assertEqual(meta.instructions_path, str(instr_file.resolve()))


if __name__ == "__main__":
    unittest.main()
