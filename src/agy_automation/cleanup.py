"""Worktree cleanup, metadata pruning, and branch deletion."""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from .config import Colors, get_target_repo
from .git_utils import (
    get_current_branch,
    is_branch_existing,
    list_worktrees,
    prune_worktrees,
    run_git,
)


def cleanup_worktree(
    worktree_name: str = "agent-worktree1",
    branch_name: str = "agent-branch1",
    force: bool = False,
    repo_dir: Optional[Path] = None,
) -> bool:
    """Safely remove a git worktree, prune metadata, and delete its branch."""
    if repo_dir is None:
        repo_dir = get_target_repo()

    worktree_path = repo_dir / ".worktrees" / worktree_name

    # Ensure current process cwd is not inside the worktree directory being removed
    try:
        current_cwd = Path.cwd().resolve()
        if str(current_cwd).lower().startswith(str(worktree_path.resolve()).lower()):
            print(f"{Colors.YELLOW}[INFO] Current directory is inside the worktree to be removed. Switching to repo root...{Colors.RESET}")
            os.chdir(str(repo_dir))
    except Exception:
        pass

    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Cleaning up Git Worktree: {worktree_name}                {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Worktree Path : {worktree_path}{Colors.RESET}")
    print(f"{Colors.GRAY}Branch Name   : {branch_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Force Mode    : {'Enabled' if force else 'Disabled'}{Colors.RESET}")

    # 1. Check if registered
    registered_worktrees = list_worktrees(repo_dir)
    normalized_wt_path = str(worktree_path.resolve()).replace("\\", "/").rstrip("/")
    is_registered = any(
        str(Path(w[0]).resolve()).replace("\\", "/").rstrip("/") == normalized_wt_path
        for w in registered_worktrees
    )

    if is_registered:
        print(f"\n{Colors.CYAN}[1/3] Removing git worktree entry...{Colors.RESET}")
        cmd = ["worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(str(worktree_path))
        res = run_git(cmd, cwd=repo_dir)
        if res.returncode != 0 and not force:
            print(f"{Colors.YELLOW}[WARNING] 'git worktree remove' reported an issue. Attempting with force...{Colors.RESET}")
            run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=repo_dir)
    else:
        print(f"\n{Colors.GRAY}[1/3] Worktree '{worktree_name}' not actively registered in git worktree list.{Colors.RESET}")

    # Remove residual directory from disk if present
    if worktree_path.exists():
        print(f"{Colors.YELLOW}      Cleaning up residual directory at {worktree_path}...{Colors.RESET}")
        shutil.rmtree(worktree_path, ignore_errors=True)

    # 2. Prune metadata
    print(f"\n{Colors.CYAN}[2/3] Pruning git worktree metadata...{Colors.RESET}")
    prune_worktrees(repo_dir)
    print(f"{Colors.GREEN}      Worktree metadata pruned.{Colors.RESET}")

    # 3. Remove branch
    print(f"\n{Colors.CYAN}[3/3] Removing branch '{branch_name}'...{Colors.RESET}")
    if is_branch_existing(branch_name, repo_dir):
        active_branch = get_current_branch(repo_dir)
        if active_branch == branch_name:
            print(f"{Colors.RED}[WARNING] Currently on '{branch_name}' in main worktree. Cannot delete active branch.{Colors.RESET}")
            print(f"{Colors.YELLOW}          Please checkout another branch (e.g. git checkout master) first.{Colors.RESET}")
        else:
            if force:
                run_git(["branch", "-D", branch_name], cwd=repo_dir)
            else:
                del_res = run_git(["branch", "-d", branch_name], cwd=repo_dir)
                if del_res.returncode != 0:
                    print(f"{Colors.YELLOW}      Branch '{branch_name}' not fully merged. Deleting with -D (force)...{Colors.RESET}")
                    run_git(["branch", "-D", branch_name], cwd=repo_dir)
            print(f"{Colors.GREEN}      Branch '{branch_name}' deleted.{Colors.RESET}")
    else:
        print(f"{Colors.GRAY}      Branch '{branch_name}' does not exist.{Colors.RESET}")

    print(f"\n{Colors.GREEN}[SUCCESS] Cleanup complete for '{worktree_name}' and '{branch_name}'!{Colors.RESET}\n")
    print(f"{Colors.CYAN}Current worktrees:{Colors.RESET}")
    run_git(["worktree", "list"], cwd=repo_dir, capture_output=False)
    return True


def main() -> int:
    """Standalone cleanup-worktree CLI entry point."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python -m agy_automation.cleanup_worktree [worktree_name] [branch_name] [--force]")
        return 0

    wt_name = sys.argv[1] if len(sys.argv) > 1 else "agent-worktree1"
    br_name = sys.argv[2] if len(sys.argv) > 2 else "agent-branch1"
    force = "-Force" in sys.argv or "--force" in sys.argv
    success = cleanup_worktree(wt_name, br_name, force=force)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
