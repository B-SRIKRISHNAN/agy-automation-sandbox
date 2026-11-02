"""Business logic and Git validation for Projects."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from agy_automation.core.logging import get_logger

logger = get_logger("agy_automation.api.projects.service")


@dataclass
class ValidatedProjectMetadata:
    """Metadata extracted from a validated Git repository."""

    name: str
    path: str
    git_remote: str
    git_branch: str
    instructions_path: str


def inspect_git_repository(project_path_str: str) -> ValidatedProjectMetadata:
    """Validate directory and extract Git metadata.
    
    Raises HTTPException 422 if path does not exist, is not a directory,
    or is not a valid Git repository.
    """
    p = Path(project_path_str).resolve()

    if not p.exists() or not p.is_dir():
        logger.warning("Directory does not exist: %s", project_path_str)
        raise HTTPException(
            status_code=422,
            detail=f"Path does not exist or is not a directory: {project_path_str}",
        )

    # Check git health
    git_dir = p / ".git"
    if not git_dir.exists():
        logger.warning("Missing .git directory in: %s", project_path_str)
        raise HTTPException(
            status_code=422,
            detail=f"Directory is not a Git repository (missing .git): {project_path_str}",
        )

    try:
        check = subprocess.run(
            ["git", "-C", str(p), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if check.returncode != 0 or check.stdout.strip() != "true":
            raise HTTPException(
                status_code=422,
                detail=f"Path is not a valid git repository: {project_path_str}",
            )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=422,
            detail=f"Failed to inspect Git repository: {str(exc)}",
        )

    # Extract Git remote origin URL (optional)
    git_remote = ""
    try:
        rem_res = subprocess.run(
            ["git", "-C", str(p), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if rem_res.returncode == 0:
            git_remote = rem_res.stdout.strip()
    except Exception:
        pass

    # Extract current branch
    git_branch = ""
    try:
        br_res = subprocess.run(
            ["git", "-C", str(p), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
        if br_res.returncode == 0:
            git_branch = br_res.stdout.strip()
    except Exception:
        pass

    # Detect instruction file (.antigravity/instructions.md, .gemini/instructions.md)
    instructions_path = ""
    candidates = [
        p / ".antigravity" / "instructions.md",
        p / ".gemini" / "instructions.md",
        p / "instructions.md",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            instructions_path = str(cand.resolve())
            break

    name = p.name or "project"

    return ValidatedProjectMetadata(
        name=name,
        path=str(p),
        git_remote=git_remote,
        git_branch=git_branch,
        instructions_path=instructions_path,
    )
