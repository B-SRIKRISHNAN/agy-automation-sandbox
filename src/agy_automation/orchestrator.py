"""Master coordinator orchestrating the 5-step autonomous issue lifecycle."""

import os
import sys
from pathlib import Path
from typing import List, Optional

from .cli import parse_cli_args, prompt_issue_number, prompt_session_or_issue
from .config import (
    Colors,
    ensure_repo_exclude,
    find_agent_instructions,
    get_target_repo,
    get_toolkit_root,
)
from .engine import detect_container_engine, verify_agy_installed
from .fetch_issue import fetch_and_confirm_issue
from .git_utils import get_current_branch, sanitize_session_name
from .push import push_changes
from .review_merge import review_and_merge
from .run_logger import RunSession
from .sandbox import run_sandbox
from .worktree import create_worktree, inject_issue_context


def run_pipeline(
    issue_number: int = 0,
    session_name: str = "",
    build: bool = False,
    interactive: bool = False,
    dry_run: bool = False,
    engine: str = "auto",
    auto_approve: bool = False,
    target_repo: Optional[Path] = None,
) -> int:
    """Execute the end-to-end autonomous issue-resolution or session lifecycle."""
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

    # Determine Target Mode (Session vs Issue)
    target_mode = "issue" if issue_number > 0 else ("session" if session_name else "")
    if not target_mode:
        try:
            target_mode, target_val = prompt_session_or_issue(current_branch, engine_desc)
            if target_mode == "issue":
                issue_number = int(target_val)
            else:
                session_name = str(target_val)
        except Exception:
            return 1

    is_session = (target_mode == "session")
    if is_session:
        session_slug = sanitize_session_name(session_name)
        worktree_name = f"worktree-{session_slug}"
        branch_name = f"session/{session_slug}"
        interactive_sandbox = True  # Permissionless interactive sandbox by default for sessions
    else:
        session_slug = ""
        worktree_name = f"worktree-issue-{issue_number}"
        branch_name = f"issue-{issue_number}"
        interactive_sandbox = interactive

    worktree_path = target_repo / ".worktrees" / worktree_name

    # Check for repository agent instructions
    _, instr_name = find_agent_instructions(target_repo)

    # Initialize RunSession for isolated, OS-agnostic logging
    session_target = session_slug if is_session else str(issue_number)
    session_logger = RunSession(project_name=target_repo.name, target=session_target)
    session_logger.update_context(
        repo_path=str(target_repo),
        base_branch=current_branch,
        branch_name=branch_name,
        worktree_name=worktree_name,
        worktree_path=str(worktree_path),
        engine=engine_desc,
        container_name=f"{target_repo.name}-sandbox",
    )
    session_logger.log_event("coordinator", "init", "pipeline_initialized", {
        "mode": "session" if is_session else "issue",
        "target": session_target,
        "base_branch": current_branch,
        "branch_name": branch_name,
        "worktree": worktree_name,
        "engine": engine_desc,
    })

    if is_session:
        print(f"\n{Colors.CYAN}[START] Starting permissionless sandbox session '{session_slug}'...{Colors.RESET}")
    else:
        print(f"\n{Colors.CYAN}[START] Starting issue lifecycle for Issue #{issue_number}...{Colors.RESET}")
    print(f"{Colors.GRAY}Target Project   : {target_repo}{Colors.RESET}")
    print(f"{Colors.GRAY}Base Branch      : {current_branch}{Colors.RESET}")
    print(f"{Colors.GRAY}Worktree Name    : {worktree_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Branch Name      : {branch_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Agent Instr.     : {instr_name if instr_name else 'None (standard workflow)'}{Colors.RESET}")
    print(f"{Colors.GRAY}Container Engine : {engine_desc}{Colors.RESET}")
    print(f"{Colors.GRAY}Sandbox Mode     : {'Interactive Antigravity (permissionless)' if interactive_sandbox else 'Automated Antigravity agent runner'}{Colors.RESET}")
    print(f"{Colors.GRAY}Run Log Dir      : {session_logger.run_dir}{Colors.RESET}")

    # ==========================================================
    # STEP 1: Fetch issue details or initialize session context
    # ==========================================================
    if is_session:
        print(f"\n{Colors.CYAN}>>> [STEP 1/5] Initializing local session context...{Colors.RESET}")
        session_context = f"""# Session: {session_slug}
- **Base Branch**: {current_branch}
- **Branch**: {branch_name}
- **Mode**: Interactive Permissionless Sandbox

## Session Overview
Autonomous interactive development session scoped to worktree `{worktree_name}`.
Execute tasks, queries, code modifications, and tests inside this protected container sandbox.
"""
        issue_data = {"number": session_slug, "context": session_context}
        session_logger.log_event("coordinator", "fetch", "session_initialized", {"session_slug": session_slug})
        print(f"{Colors.GREEN}[OK] Local session '{session_slug}' initialized (bypassing GitHub issues).{Colors.RESET}")
    else:
        print(f"\n{Colors.CYAN}>>> [STEP 1/5] Fetching issue details from GitHub...{Colors.RESET}")
        session_logger.log_event("coordinator", "fetch", "issue_fetch_started", {"issue_number": issue_number})
        try:
            issue_data = fetch_and_confirm_issue(
                issue_number,
                auto_approve=auto_approve,
                interactive=not auto_approve,
            )
        except Exception as exc:
            session_logger.finish("FAILED", error=f"Issue fetch failed: {exc}")
            print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
            return 1

        if not issue_data:
            session_logger.finish("ABORTED", error="Process aborted or issue fetch failed")
            print(f"{Colors.YELLOW}[INFO] Process aborted or issue fetch failed.{Colors.RESET}")
            return 0

        session_logger.update_context(
            issue_title=issue_data.get("title", ""),
            issue_url=issue_data.get("url", ""),
        )
        session_logger.log_event("coordinator", "fetch", "issue_fetch_completed", {
            "issue_number": issue_number,
            "title": issue_data.get("title", ""),
            "url": issue_data.get("url", ""),
        })

    # Dry-Run Simulation Intercept
    if dry_run:
        target_desc = f"Session '{session_slug}'" if is_session else f"Issue #{issue_number}"
        print(f"\n{Colors.MAGENTA}[DRY RUN] {target_desc} configured successfully. Planned execution:{Colors.RESET}")
        print(f"{Colors.WHITE}  - Target Repo     : {target_repo}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Base Branch     : {current_branch}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Worktree Branch : {branch_name}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Worktree Path   : {worktree_path}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Agent Instr.    : {instr_name if instr_name else 'None (standard agent workflow)'}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Container Engine: {engine if engine != 'auto' else f'auto-detect ({engine_desc})'}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Sandbox Mode    : {'Interactive permissionless Antigravity session' if interactive_sandbox else 'Automated Antigravity agent runner'}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Build Sandbox   : {build}{Colors.RESET}")
        print(f"{Colors.WHITE}  - Session Logs    : {session_logger.run_dir}{Colors.RESET}")
        print(f"{Colors.MAGENTA}[DRY RUN] Simulation complete. No worktree created, no container started, no commits made.{Colors.RESET}")
        session_logger.log_event("coordinator", "dry_run", "simulation_completed")
        session_logger.finish("COMPLETED")
        return 0

    merged = False
    pushed = False

    try:
        # ==========================================================
        # STEP 2: Create isolated Git Worktree and branch
        # ==========================================================
        print(f"\n{Colors.CYAN}>>> [STEP 2/5] Creating isolated Git Worktree...{Colors.RESET}")
        session_logger.log_event("coordinator", "worktree", "worktree_creation_started", {
            "worktree_name": worktree_name,
            "branch_name": branch_name,
        })
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
            session_logger.finish("FAILED", error=f"Worktree creation failed: {exc}")
            print(f"{Colors.RED}[ERROR] Failed to create git worktree: {exc}{Colors.RESET}")
            return 1

        session_logger.log_event("coordinator", "worktree", "worktree_created", {
            "worktree_path": str(worktree_path),
        })

        # Inject issue or session context
        context_dest = inject_issue_context(worktree_path, issue_data["context"])
        print(f"{Colors.GREEN}[OK] Injected context into worktree: {context_dest}{Colors.RESET}")
        if instr_name:
            print(f"{Colors.GREEN}[OK] Active repository agent instructions: {instr_name}{Colors.RESET}")

        # ==========================================================
        # STEP 3: Run Sandbox with agy
        # ==========================================================
        print(f"\n{Colors.CYAN}>>> [STEP 3/5] Launching Sandbox & running Antigravity (agy)...{Colors.RESET}")
        session_logger.log_event("coordinator", "sandbox", "sandbox_started", {
            "instructions": instr_name,
            "interactive": interactive_sandbox,
        })
        issue_rel_path = f".worktrees/{worktree_name}/ISSUE_CONTEXT.md"
        sandbox_exit = run_sandbox(
            worktree_name=worktree_name,
            issue_file=issue_rel_path,
            target_repo=target_repo,
            instructions_file=instr_name,
            build=build,
            interactive=interactive_sandbox,
            container_engine=engine,
            session_logger=session_logger,
        )
        if sandbox_exit != 0:
            session_logger.finish("FAILED", error=f"Sandbox run failed with exit code {sandbox_exit}")
            print(f"{Colors.RED}[ERROR] Sandbox run failed with exit code {sandbox_exit}.{Colors.RESET}")
            return sandbox_exit

        # ==========================================================
        # STEP 4: Review changes with agy, confirm, merge & cleanup
        # ==========================================================
        print(f"\n{Colors.CYAN}>>> [STEP 4/5] Reviewing changes and merging...{Colors.RESET}")
        session_logger.log_event("coordinator", "review", "review_started")
        try:
            merged = review_and_merge(
                worktree_name=worktree_name,
                branch_name=branch_name,
                base_branch=current_branch,
                auto_approve=auto_approve,
                interactive=not auto_approve,
                repo_dir=target_repo,
                session_logger=session_logger,
            )
        except Exception as exc:
            session_logger.finish("FAILED", error=f"Review and merge failed: {exc}")
            print(f"{Colors.RED}[ERROR] Review and merge failed: {exc}{Colors.RESET}")
            return 1

        session_logger.log_event("coordinator", "review", "merge_decision", {"merged": merged})

        # ==========================================================
        # STEP 5: Confirm and push to remote
        # ==========================================================
        if merged:
            print(f"\n{Colors.CYAN}>>> [STEP 5/5] Push changes to remote...{Colors.RESET}")
            session_logger.log_event("coordinator", "push", "push_started")
            pushed = push_changes(
                branch_name=current_branch,
                remote="origin",
                auto_approve=auto_approve,
                interactive=not auto_approve,
                repo_dir=target_repo,
            )
            session_logger.log_event("coordinator", "push", "push_decision", {"pushed": bool(pushed)})
        else:
            print(f"\n{Colors.YELLOW}[INFO] Skipping push since changes were not merged into '{current_branch}'.{Colors.RESET}")
            session_logger.log_event("coordinator", "push", "push_skipped", {"reason": "changes_not_merged"})

    except KeyboardInterrupt:
        session_logger.finish("ABORTED", error="Execution interrupted by user (Ctrl+C)")
        raise
    except Exception as exc:
        session_logger.finish("FAILED", error=str(exc))
        raise

    session_logger.finish("COMPLETED", merged=merged, pushed=bool(pushed))
    print(f"\n{Colors.CYAN}=========================================================={Colors.RESET}")
    target_msg = f"Session '{session_slug}'" if is_session else f"Issue #{issue_number}"
    print(f"{Colors.GREEN}   {target_msg} Workflow Completed!               {Colors.RESET}")
    print(f"{Colors.GRAY}   Logs: {session_logger.run_dir}{Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Primary CLI entry point for the coordinator."""
    args = parse_cli_args(argv)
    return run_pipeline(
        issue_number=args.issue,
        session_name=getattr(args, "session", ""),
        build=args.build,
        interactive=args.interactive,
        dry_run=args.dry_run,
        engine=args.engine,
    )



if __name__ == "__main__":
    sys.exit(main())
