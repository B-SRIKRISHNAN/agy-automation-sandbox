"""Git utility wrappers using standard library subprocess and shutil.which()."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def get_git_executable() -> str:
    """Find git executable using shutil.which() to properly resolve on Windows and Linux."""
    git_bin = shutil.which("git")
    if not git_bin:
        raise RuntimeError("Git is not installed or not found in system PATH.")
    return git_bin


def run_git(
    args: List[str],
    cwd: Optional[Path] = None,
    check: bool = False,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Execute a git command with UTF-8 encoding and optional output capture."""
    git_bin = get_git_executable()
    cmd = [git_bin] + args

    kwargs = {
        "cwd": str(cwd) if cwd else None,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    result = subprocess.run(cmd, check=check, **kwargs)
    return result


def get_current_branch(cwd: Optional[Path] = None) -> str:
    """Get the active git branch name, or empty string if detached/error."""
    res = run_git(["branch", "--show-current"], cwd=cwd)
    if res.returncode == 0:
        return res.stdout.strip()
    return ""


def prune_worktrees(repo_dir: Path) -> None:
    """Prune stale git worktrees."""
    run_git(["worktree", "prune", "--expire", "now"], cwd=repo_dir)


def configure_relative_paths(repo_dir: Path) -> None:
    """Configure git to use relative paths for worktrees for cross-OS container portability."""
    run_git(["config", "worktree.useRelativePaths", "true"], cwd=repo_dir)


def worktree_repair(repo_dir: Path, worktree_path: Optional[Path] = None) -> None:
    """Repair worktree linkage."""
    args = ["worktree", "repair"]
    if worktree_path:
        args.append(str(worktree_path))
    run_git(args, cwd=repo_dir)


def list_worktrees(repo_dir: Path) -> List[Tuple[str, str, str]]:
    """List registered worktrees from 'git worktree list --porcelain'."""
    res = run_git(["worktree", "list", "--porcelain"], cwd=repo_dir)
    if res.returncode != 0 or not res.stdout:
        return []

    worktrees = []
    current_path = ""
    current_head = ""
    current_branch = ""

    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            if current_path:
                worktrees.append((current_path, current_head, current_branch))
                current_path, current_head, current_branch = "", "", ""
            continue
        if line.startswith("worktree "):
            current_path = line[9:].strip()
        elif line.startswith("HEAD "):
            current_head = line[5:].strip()
        elif line.startswith("branch "):
            current_branch = line[7:].strip()

    if current_path:
        worktrees.append((current_path, current_head, current_branch))

    return worktrees


def is_branch_existing(branch_name: str, repo_dir: Path) -> bool:
    """Check if branch exists locally."""
    res = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo_dir)
    return res.returncode == 0


def get_commits_between(base_branch: str, feature_branch: str, repo_dir: Path) -> List[str]:
    """Get list of commits on feature_branch targeting base_branch."""
    res = run_git(["log", f"{base_branch}..{feature_branch}", "--oneline"], cwd=repo_dir)
    if res.returncode == 0 and res.stdout.strip():
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    return []


def get_diff_stat(base_branch: str, feature_branch: str, repo_dir: Path) -> str:
    """Get diff stat between base_branch and feature_branch."""
    res = run_git(["diff", f"{base_branch}..{feature_branch}", "--stat"], cwd=repo_dir)
    return res.stdout.strip() if res.returncode == 0 else ""


def get_diff_raw(base_branch: str, feature_branch: str, repo_dir: Path) -> str:
    """Get unified diff between base_branch and feature_branch."""
    res = run_git(["diff", f"{base_branch}..{feature_branch}"], cwd=repo_dir)
    return res.stdout.strip() if res.returncode == 0 else ""


def get_dirty_tracked_files(repo_dir: Path) -> List[str]:
    """Get modified tracked files in the workspace (excluding untracked '??')."""
    res = run_git(["status", "--porcelain"], cwd=repo_dir)
    if res.returncode != 0 or not res.stdout:
        return []
    dirty = []
    for line in res.stdout.splitlines():
        line = line.rstrip()
        if line and not line.startswith("??"):
            dirty.append(line)
    return dirty
