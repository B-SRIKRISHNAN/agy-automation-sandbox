"""Configuration settings for the Antigravity Automation API."""

import os
from pathlib import Path


def get_default_db_url() -> str:
    """Resolve default SQLite database URL under user home or AGY_DATABASE_URL env."""
    override = os.environ.get("AGY_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if override:
        return override
    db_dir = Path.home() / ".agy-automation"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = (db_dir / "agy.db").resolve()
    return f"sqlite:///{db_path}"


HOST = os.environ.get("AGY_API_HOST", "0.0.0.0")
PORT = int(os.environ.get("AGY_API_PORT", "8000"))
DATABASE_URL = get_default_db_url()
