"""Hierarchical configuration loader for agy-automation.

Resolves settings with the following precedence (highest to lowest):
1. Command-line flags / API arguments
2. Repository-local config (<target_repo>/.agy-automation.yaml)
3. User global config (~/.agy-automation/config.yaml)
4. Built-in defaults
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_engine": "auto",
    "base_branch": "master",
    "auto_approve": False,
    "interactive": True,
    "runs_dir": None,
    "build": False,
}


def get_global_config_path() -> Path:
    """Return path to user's global configuration file."""
    return Path.home() / ".agy-automation" / "config.yaml"


def get_repo_config_path(target_repo: Path) -> Path:
    """Return path to repository-level configuration file."""
    return target_repo / ".agy-automation.yaml"


def _read_yaml_file(path: Path) -> Dict[str, Any]:
    """Safely read and parse a YAML file if it exists."""
    if not path.is_file():
        # Check alternate .yml extension
        alt_path = path.with_suffix(".yml")
        if not alt_path.is_file():
            return {}
        path = alt_path

    if not HAS_YAML:
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_merged_config(target_repo: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration merged across defaults, global YAML, and repo YAML."""
    config = dict(DEFAULT_CONFIG)

    # 1. Global user config
    global_cfg = _read_yaml_file(get_global_config_path())
    config.update({k: v for k, v in global_cfg.items() if v is not None})

    # 2. Repo local config
    if target_repo:
        repo_path = Path(target_repo).resolve()
        repo_cfg = _read_yaml_file(get_repo_config_path(repo_path))
        config.update({k: v for k, v in repo_cfg.items() if v is not None})

    return config
