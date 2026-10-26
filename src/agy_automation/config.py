"""Configuration and environment detection for agy-automation."""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


class Colors:
    """ANSI color codes with terminal detection and NO_COLOR support."""
    _enabled = sys.stdout.isatty() and "NO_COLOR" not in os.environ

    CYAN = "\033[96m" if _enabled else ""
    GREEN = "\033[92m" if _enabled else ""
    YELLOW = "\033[93m" if _enabled else ""
    RED = "\033[91m" if _enabled else ""
    MAGENTA = "\033[95m" if _enabled else ""
    GRAY = "\033[90m" if _enabled else ""
    WHITE = "\033[97m" if _enabled else ""
    RESET = "\033[0m" if _enabled else ""

    @classmethod
    def disable(cls):
        cls.CYAN = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.RED = ""
        cls.MAGENTA = ""
        cls.GRAY = ""
        cls.WHITE = ""
        cls.RESET = ""


def get_toolkit_root() -> Path:
    """Locate the toolkit directory where scripts and docker-compose.sandbox.yml live."""
    # Priority 1: Traverse upwards from this module's directory
    current = Path(__file__).resolve().parent
    for p in [current] + list(current.parents):
        if (p / "docker-compose.sandbox.yml").is_file() or (p / "scripts").is_dir():
            return p

    # Priority 2: Check current working directory and its parents
    cwd = Path.cwd().resolve()
    for p in [cwd] + list(cwd.parents):
        if (p / "docker-compose.sandbox.yml").is_file() or (p / "scripts").is_dir():
            return p

    # Fallback to root (parent of parent of src/agy_automation)
    return Path(__file__).resolve().parent.parent.parent


def get_target_repo(start_dir: Optional[Path] = None) -> Path:
    """Find the top-level Git repository root of the target project."""
    import shutil
    import subprocess

    git_bin = shutil.which("git")
    if not git_bin:
        raise RuntimeError("Git is not installed or not found in system PATH.")

    cwd = str(start_dir or Path.cwd())
    result = subprocess.run(
        [git_bin, "rev-parse", "--show-toplevel"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("Current working directory is not inside a Git repository.")

    return Path(result.stdout.strip()).resolve()


def ensure_repo_exclude(target_repo: Path) -> bool:
    """Ensure .worktrees/ and ISSUE_CONTEXT.md are locally excluded in .git/info/exclude."""
    git_dir = target_repo / ".git"
    if not git_dir.is_dir():
        return False

    exclude_file = git_dir / "info" / "exclude"
    if not exclude_file.parent.is_dir():
        exclude_file.parent.mkdir(parents=True, exist_ok=True)

    content = ""
    if exclude_file.is_file():
        try:
            content = exclude_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = exclude_file.read_text(encoding="utf-8", errors="replace")

    if not re.search(r"(?m)^\.worktrees/?$", content):
        with open(exclude_file, "a", encoding="utf-8", newline="\n") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(".worktrees/\nISSUE_CONTEXT.md\n")
        return True

    return False


def find_agent_instructions(target_repo: Path) -> Tuple[Optional[Path], str]:
    """Search target repository root case-insensitively for AGENT_INSTRUCTIONS.md."""
    common_names = ["AGENT_INSTRUCTIONS.md", "AGENT_INSTRUCTIONS.MD", "agent_instructions.md"]
    for name in common_names:
        candidate = target_repo / name
        if candidate.is_file():
            return candidate, candidate.name

    try:
        for entry in target_repo.iterdir():
            if entry.is_file() and entry.name.lower() == "agent_instructions.md":
                return entry, entry.name
    except (OSError, PermissionError):
        pass

    return None, ""
