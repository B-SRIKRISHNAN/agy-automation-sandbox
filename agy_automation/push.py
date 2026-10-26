"""Remote branch verification, unpushed commit inspection, and push approval."""

import sys
from pathlib import Path
from typing import Optional

from .config import Colors, get_target_repo
from .git_utils import get_current_branch, run_git


def push_changes(
    branch_name: str = "",
    remote: str = "origin",
    repo_dir: Optional[Path] = None,
) -> bool:
    """Fetch remote state, inspect unpushed commits, request confirmation, and push with -u."""
    if repo_dir is None:
        repo_dir = get_target_repo()

    if not branch_name:
        branch_name = get_current_branch(repo_dir)
        if not branch_name:
            raise RuntimeError("Could not determine active branch to push. Please specify branch name.")

    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Push Changes to Remote: {remote}/{branch_name}            {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")

    # 1. Fetch remote branch state before comparing
    print(f"{Colors.CYAN}[INFO] Fetching latest state from {remote}/{branch_name}...{Colors.RESET}")
    run_git(["fetch", remote, branch_name], cwd=repo_dir)

    # 2. Check if branch exists on remote
    ls_res = run_git(["ls-remote", "--heads", remote, branch_name], cwd=repo_dir)
    remote_exists = bool(ls_res.returncode == 0 and ls_res.stdout.strip())

    if not remote_exists:
        print(f"{Colors.YELLOW}[INFO] Branch '{branch_name}' does not exist yet on '{remote}' (brand new remote branch).{Colors.RESET}")
        log_res = run_git(["log", branch_name, "-n", "5", "--oneline"], cwd=repo_dir)
    else:
        log_res = run_git(["log", f"{remote}/{branch_name}..{branch_name}", "--oneline"], cwd=repo_dir)

    unpushed_commits = [c.strip() for c in log_res.stdout.splitlines() if c.strip()] if log_res.returncode == 0 else []

    if not unpushed_commits:
        print(f"{Colors.YELLOW}[INFO] Local branch '{branch_name}' is already in sync with '{remote}/{branch_name}'.{Colors.RESET}")
        print(f"{Colors.GRAY}       No unpushed commits found.{Colors.RESET}")
        return True

    print(f"\n{Colors.CYAN}Commits to be pushed to {remote}/{branch_name}:{Colors.RESET}")
    for c in unpushed_commits:
        print(f"{Colors.WHITE}  * {c}{Colors.RESET}")

    # 3. Request confirmation
    try:
        resp = input(f"\n{Colors.YELLOW}Do you approve pushing these changes to '{remote}/{branch_name}'? (y/N): {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        resp = ""

    if resp and resp.lower() in ("y", "yes"):
        print(f"\n{Colors.CYAN}[INFO] Pushing changes with upstream tracking (-u)...{Colors.RESET}")
        push_res = run_git(["push", "-u", remote, branch_name], cwd=repo_dir, capture_output=False)
        if push_res.returncode == 0:
            print(f"\n{Colors.GREEN}[SUCCESS] Successfully pushed changes to {remote}/{branch_name}!{Colors.RESET}")
            return True
        else:
            print(f"\n{Colors.RED}[ERROR] Git push failed. Please check network/credentials.{Colors.RESET}")
            return False
    else:
        print(f"\n{Colors.YELLOW}[INFO] Push aborted by user. Your local branch '{branch_name}' was NOT pushed.{Colors.RESET}")
        return False


def main():
    """Standalone push-changes CLI entry point."""
    br = sys.argv[1] if len(sys.argv) > 1 else ""
    remote = sys.argv[2] if len(sys.argv) > 2 else "origin"
    pushed = push_changes(br, remote)
    sys.exit(0 if pushed else 1)


if __name__ == "__main__":
    main()
