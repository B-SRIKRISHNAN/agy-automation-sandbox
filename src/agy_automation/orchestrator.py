"""Master coordinator orchestrating the 5-step autonomous issue lifecycle."""

import os
import sys
from pathlib import Path
from typing import List, Optional

from .cli import parse_cli_args, prompt_issue_number
from .config import (
    Colors,
    ensure_repo_exclude,
    find_agent_instructions,
    get_target_repo,
    get_toolkit_root,
)
from .engine import detect_container_engine, verify_agy_installed
from .fetch_issue import fetch_and_confirm_issue
from .git_utils import get_current_branch
from .push import push_changes
from .review_merge import review_and_merge
from .sandbox import run_sandbox
from .worktree import create_worktree, inject_issue_context


def run_pipeline(
    issue_number: int = 0,
    build: bool = False,
    interactive: bool = False,
    dry_run: bool = False,
    engine: str = "auto",
    auto_approve: bool = False,
    target_repo: Optional[Path] = None,
) -> int:
    """Execute the end-to-end autonomous issue-resolution lifecycle."""
    toolkit_root = get_toolkit_root()

    # 1. Determine Target Project Repository
    if target_repo is None:
        try:
            target_repo = get_target_repo()
        except RuntimeError as exc:
            print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
            return 1

    os.chdir(str(target_repo))
    ensure_repo_exclude(target_repo)

    # Pre-flight: verify active git branch
    current_branch = get_current_branch(target_repo)
    if not current_branch:
        print(f"{Colors.RED}[ERROR] Could not determine active Git branch. Please checkout a valid branch first.{Colors.RESET}")
        return 1

    # Pre-flight: verify agy CLI
    try:
        verify_agy_installed()
    except RuntimeError as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        return 1

    # Pre-flight: verify container engine
    try:
        engine_type, engine_desc = detect_container_engine(engine)
    except RuntimeError as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        return 1

    if engine != "auto":
        os.environ["CONTAINER_ENGINE"] = engine

    # Prompt for Issue Number if not provided
    if issue_number <= 0:
        try:
            issue_number = prompt_issue_number(current_branch, engine_desc)
        except Exception:
            return 1

    worktree_name = f"worktree-issue-{issue_number}"
    branch_name = f"issue-{issue_number}"
    worktree_path = target_repo / ".worktrees" / worktree_name

    # Check for repository agent instructions
    _, instr_name = find_agent_instructions(target_repo)

    print(f"\n{Colors.CYAN}[START] Starting issue lifecycle for Issue #{issue_number}...{Colors.RESET}")
    print(f"{Colors.GRAY}Target Project   : {target_repo}{Colors.RESET}")
    print(f"{Colors.GRAY}Base Branch      : {current_branch}{Colors.RESET}")
    print(f"{Colors.GRAY}Worktree Name    : {worktree_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Branch Name      : {branch_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Agent Instr.     : {instr_name if instr_name else 'None (standard workflow)'}{Colors.RESET}")
    print(f"{Colors.GRAY}Container Engine : {engine_desc}{Colors.RESET}")

    # ==========================================================
    # STEP 1: Fetch issue details & confirm with user
    # ==========================================================
    print(f"\n{Colors.CYAN}>>> [STEP 1/5] Fetching issue details from GitHub...{Colors.RESET}")
    try:
        issue_data = fetch_and_confirm_issue(
            issue_number,
            auto_approve=auto_approve,
            interactive=not auto_approve,
        )
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        return 1

    if not issue_data:
        print(f"{Colors.YELLOW}[INFO] Process aborted or issue fetch failed.{Colors.RESET}")
        return 0

    # Dry-Run Simulation Intercept
    if dry_run:
        print(f"\n{Colors.MAGENTA}[DRY RUN] Issue #{issue_number} fetched successfully. Planned execution:{Colors.RESET}")
        print(f"{Colors.WHITE}  - Target Repo     : {target_repo}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Base Branch     : {current_branch}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Worktree Branch : {branch_name}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Worktree Path   : {worktree_path}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Agent Instr.    : {instr_name if instr_name else 'None (standard agent workflow)'}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Container Engine: {engine if engine != 'auto' else f'auto-detect ({engine_desc})'}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Sandbox Mode    : {'Interactive bash shell' if interactive else 'Automated Antigravity agent runner'}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Build Sandbox   : {build}{Colors.RESET}")
        print(f"{Colors.MAGENTA}[DRY RUN] Simulation complete. No worktree created, no container started, no commits made.{Colors.RESET}")
        return 0

    # ==========================================================
    # STEP 2: Create isolated Git Worktree and branch
    # ==========================================================
    print(f"\n{Colors.CYAN}>>> [STEP 2/5] Creating isolated Git Worktree...{Colors.RESET}")
    try:
        create_worktree(
            worktree_name=worktree_name,
            branch_name=branch_name,
            base_branch=current_branch,
            auto_approve=auto_approve,
            interactive=not auto_approve,
            repo_dir=target_repo,
        )
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] Failed to create git worktree: {exc}{Colors.RESET}")
        return 1

    # Inject issue context
    context_dest = inject_issue_context(worktree_path, issue_data["context"])
    print(f"{Colors.GREEN}[OK] Injected issue context into worktree: {context_dest}{Colors.RESET}")
    if instr_name:
        print(f"{Colors.GREEN}[OK] Active repository agent instructions: {instr_name}{Colors.RESET}")

    # ==========================================================
    # STEP 3: Run Sandbox with automated agy
    # ==========================================================
    print(f"\n{Colors.CYAN}>>> [STEP 3/5] Launching Sandbox & running Antigravity (agy)...{Colors.RESET}")
    issue_rel_path = f".worktrees/{worktree_name}/ISSUE_CONTEXT.md"
    sandbox_exit = run_sandbox(
        worktree_name=worktree_name,
        issue_file=issue_rel_path,
        target_repo=target_repo,
        instructions_file=instr_name,
        build=build,
        interactive=interactive,
        container_engine=engine,
    )
    if sandbox_exit != 0:
        print(f"{Colors.RED}[ERROR] Sandbox run failed with exit code {sandbox_exit}.{Colors.RESET}")
        return sandbox_exit

    # ==========================================================
    # STEP 4: Review changes with agy, confirm, merge & cleanup
    # ==========================================================
    print(f"\n{Colors.CYAN}>>> [STEP 4/5] Reviewing changes and merging...{Colors.RESET}")
    merged = False
    try:
        merged = review_and_merge(
            worktree_name=worktree_name,
            branch_name=branch_name,
            base_branch=current_branch,
            auto_approve=auto_approve,
            interactive=not auto_approve,
            repo_dir=target_repo,
        )
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] Review and merge failed: {exc}{Colors.RESET}")
        return 1

    # ==========================================================
    # STEP 5: Confirm and push to remote
    # ==========================================================
    if merged:
        print(f"\n{Colors.CYAN}>>> [STEP 5/5] Push changes to remote...{Colors.RESET}")
        push_changes(
            branch_name=current_branch,
            remote="origin",
            auto_approve=auto_approve,
            interactive=not auto_approve,
            repo_dir=target_repo,
        )
    else:
        print(f"\n{Colors.YELLOW}[INFO] Skipping push since changes were not merged into '{current_branch}'.{Colors.RESET}")

    print(f"\n{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Issue #{issue_number} Workflow Completed!               {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Primary CLI entry point for the coordinator."""
    args = parse_cli_args(argv)
    return run_pipeline(
        issue_number=args.issue,
        build=args.build,
        interactive=args.interactive,
        dry_run=args.dry_run,
        engine=args.engine,
    )


if __name__ == "__main__":
    sys.exit(main())
