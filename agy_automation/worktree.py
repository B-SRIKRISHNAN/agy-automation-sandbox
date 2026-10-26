"""Git worktree and isolated branch management."""

import shutil
import sys
from pathlib import Path
from typing import Optional

from .config import Colors, get_target_repo
from .git_utils import (
    configure_relative_paths,
    get_current_branch,
    is_branch_existing,
    list_worktrees,
    prune_worktrees,
    run_git,
)


def create_worktree(
    worktree_name: str = "agent-worktree1",
    branch_name: str = "agent-branch1",
    base_branch: str = "",
    force: bool = False,
    repo_dir: Optional[Path] = None,
) -> Path:
    """Create an isolated Git worktree and branch off base_branch."""
    if repo_dir is None:
        repo_dir = get_target_repo()

    prune_worktrees(repo_dir)
    configure_relative_paths(repo_dir)

    active_branch = get_current_branch(repo_dir)
    if not base_branch:
        base_branch = active_branch or "HEAD"

    if active_branch and active_branch == branch_name:
        raise RuntimeError(
            f"Cannot create worktree for branch '{branch_name}': "
            "It is already checked out in your main workspace.\n"
            "Please checkout another branch first (e.g. git checkout master)."
        )

    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Creating Git Worktree: {worktree_name}                  {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Repository Root : {repo_dir}{Colors.RESET}")
    print(f"{Colors.GRAY}Base Branch     : {base_branch}{Colors.RESET}")
    print(f"{Colors.GRAY}New Branch      : {branch_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Worktree Name   : {worktree_name}{Colors.RESET}")

    worktrees_container = repo_dir / ".worktrees"
    worktrees_container.mkdir(parents=True, exist_ok=True)
    worktree_path = worktrees_container / worktree_name

    # Check if worktree directory exists or is registered in git worktree list
    registered_worktrees = list_worktrees(repo_dir)
    normalized_wt_path = str(worktree_path.resolve()).replace("\\", "/").rstrip("/")
    is_registered = any(
        str(Path(w[0]).resolve()).replace("\\", "/").rstrip("/") == normalized_wt_path
        for w in registered_worktrees
    )

    if worktree_path.exists() or is_registered:
        should_remove = force
        if not force:
            print(f"\n{Colors.YELLOW}[WARNING] Worktree '{worktree_name}' already exists at: {worktree_path}{Colors.RESET}")
            try:
                resp = input(f"{Colors.YELLOW}Do you want to remove the existing worktree and recreate it? (y/N): {Colors.RESET}").strip()
                should_remove = resp.lower() in ("y", "yes")
            except (EOFError, KeyboardInterrupt):
                should_remove = False

            if not should_remove:
                raise RuntimeError("Worktree removal declined. Creation cancelled.")

        if should_remove:
            print(f"{Colors.CYAN}[INFO] Removing existing worktree at {worktree_path}...{Colors.RESET}")
            run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=repo_dir)
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)
            prune_worktrees(repo_dir)
            print(f"{Colors.GREEN}[OK] Existing worktree removed.{Colors.RESET}")

    # Check if branch already exists
    branch_exists = is_branch_existing(branch_name, repo_dir)
    if branch_exists:
        should_delete_branch = force
        if not force:
            print(f"\n{Colors.YELLOW}[WARNING] Branch '{branch_name}' already exists in local Git repository.{Colors.RESET}")
            try:
                resp = input(
                    f"{Colors.YELLOW}Do you want to delete branch '{branch_name}' and recreate it fresh from '{base_branch}'? (y/N): {Colors.RESET}"
                ).strip()
                should_delete_branch = resp.lower() in ("y", "yes")
            except (EOFError, KeyboardInterrupt):
                should_delete_branch = False

            if not should_delete_branch:
                print(f"{Colors.CYAN}[INFO] Preserving existing branch '{branch_name}'. Will attach worktree to it.{Colors.RESET}")

        if should_delete_branch:
            print(f"{Colors.CYAN}[INFO] Deleting existing branch '{branch_name}'...{Colors.RESET}")
            run_git(["branch", "-D", branch_name], cwd=repo_dir)
            branch_exists = False
            print(f"{Colors.GREEN}[OK] Existing branch deleted.{Colors.RESET}")

    # Create or attach worktree
    if branch_exists:
        print(f"\n{Colors.CYAN}[INFO] Attaching worktree to existing branch '{branch_name}'...{Colors.RESET}")
        res = run_git(["worktree", "add", str(worktree_path), branch_name], cwd=repo_dir, capture_output=False)
    else:
        print(f"\n{Colors.CYAN}[INFO] Creating worktree with new branch '{branch_name}' from '{base_branch}'...{Colors.RESET}")
        res = run_git(["worktree", "add", "-b", branch_name, str(worktree_path), base_branch], cwd=repo_dir, capture_output=False)

    if res.returncode != 0:
        raise RuntimeError(f"Failed to create git worktree (exit code {res.returncode}).")

    print(f"\n{Colors.GREEN}[SUCCESS] Worktree ready!{Colors.RESET}")
    print(f"{Colors.GREEN}Location: {worktree_path}{Colors.RESET}")
    print(f"{Colors.GREEN}Branch  : {branch_name}{Colors.RESET}")
    return worktree_path


def inject_issue_context(worktree_path: Path, context_content: str) -> Path:
    """Inject bundled ISSUE_CONTEXT.md into worktree root using UTF-8 and LF line endings."""
    dest = worktree_path / "ISSUE_CONTEXT.md"
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(context_content)
    return dest


def main():
    """Standalone create-worktree CLI entry point."""
    wt_name = sys.argv[1] if len(sys.argv) > 1 else "agent-worktree1"
    br_name = sys.argv[2] if len(sys.argv) > 2 else "agent-branch1"
    base_br = sys.argv[3] if len(sys.argv) > 3 else ""
    force = "-Force" in sys.argv or "--force" in sys.argv

    try:
        create_worktree(wt_name, br_name, base_br, force=force)
        sys.exit(0)
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
