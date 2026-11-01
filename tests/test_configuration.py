"""Tests for hierarchical YAML configuration resolution."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agy_automation.core.configuration import DEFAULT_CONFIG, load_merged_config


class TestConfiguration(unittest.TestCase):
    def test_default_config(self):
        with patch("agy_automation.core.configuration.get_global_config_path") as mock_global, \
             patch("agy_automation.core.configuration.get_repo_config_path") as mock_repo:
            mock_global.return_value = Path("/nonexistent/global.yaml")
            mock_repo.return_value = Path("/nonexistent/repo.yaml")

            cfg = load_merged_config()
            self.assertEqual(cfg["default_engine"], "auto")
            self.assertEqual(cfg["base_branch"], "master")
            self.assertEqual(cfg["auto_approve"], False)

    def test_repo_config_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir)
            cfg_file = repo_path / ".agy-automation.yaml"
            cfg_file.write_text("default_engine: podman\nbase_branch: main\nauto_approve: true\n", encoding="utf-8")

            with patch("agy_automation.core.configuration.get_global_config_path") as mock_global:
                mock_global.return_value = Path("/nonexistent/global.yaml")
                cfg = load_merged_config(repo_path)
                self.assertEqual(cfg["default_engine"], "podman")
                self.assertEqual(cfg["base_branch"], "main")
                self.assertEqual(cfg["auto_approve"], True)


if __name__ == "__main__":
    unittest.main()
