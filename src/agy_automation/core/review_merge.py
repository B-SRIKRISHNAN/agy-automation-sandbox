"""AI code review generation, merge approval, and safe Git integration for agy-automation."""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .cleanup import cleanup_worktree
from .config import Colors, find_agent_instructions, get_target_repo
from .engine import verify_agy_installed
from .exceptions import DirtyWorkspaceError, MergeConflictError
from .git import (
    abort_merge,
    get_commits_between,
    get_current_branch,
    get_diff_raw,
    get_diff_stat,
    get_dirty_tracked_files,
    get_unmerged_files,
    get_workspace_status,
    is_merge_in_progress,
    run_git,
    worktree_repair,
)


def format_merge_message(branch_name: str, base_branch: str) -> str:
    """Format merge commit message, including issue closing tag if branch targets an issue."""
    msg = f"Merge branch '{branch_name}' into {base_branch}"
    match = re.search(r"issue-(\d+)", branch_name)
    if match:
        msg = f"{msg} (Fixes #{match.group(1)})"
    return msg


def prepare_review_data(
    worktree_name: str,
    branch_name: str,
    base_branch: str = "",
    repo_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Inspect commits and generate unified diff / review prompt data headlessly."""
    if repo_dir is None:
        repo_dir = get_target_repo()

    if not base_branch:
        base_branch = get_current_branch(repo_dir) or "master"

    commits = get_commits_between(base_branch, branch_name, repo_dir)
    diff_stat = get_diff_stat(base_branch, branch_name, repo_dir)
    diff_raw = get_diff_raw(base_branch, branch_name, repo_dir)

    # Truncate diff to 2000 characters to fit CLI argument buffers
    if len(diff_raw) > 2000:
        diff_snippet = (
            diff_raw[:2000]
            + f"\n\n... [diff truncated to stay within command buffer; full changes visible via git diff {base_branch}..{branch_name}]"
        )
    else:
        diff_snippet = diff_raw

    _, instr_name = find_agent_instructions(repo_dir)
    compliance_section = ""
    if instr_name:
        compliance_section = f"""

### 5. Repository Standards & Agent Instructions Compliance
(Assess whether the code, documentation, and tests comply with the sequence and standards in {instr_name})"""

    commits_text = "\n".join(commits)
    review_prompt = f"""You are a senior principal engineer performing a code review. Analyze the following commits and diff for feature branch '{branch_name}' targeting '{base_branch}'.
Generate a comprehensive, crystal-clear review formatted with markdown headings:

### 1. Summary of Changes
(What problem was solved, core architectural changes, and rationale)

### 2. Detailed File-by-File Breakdown
(Grouped by module or component, describing specific modifications)

### 3. Impact & Risk Assessment
(Dependencies, database migrations, configuration updates, potential regressions)

### 4. Verification & Testing Checklist
(Recommended steps to test and verify these changes){compliance_section}

---
Commits:
{commits_text}

Diff Stat:
{diff_stat}

Diff Details:
{diff_snippet}
"""
    return {
        "worktree_name": worktree_name,
        "branch_name": branch_name,
        "base_branch": base_branch,
        "commits": commits,
        "diff_stat": diff_stat,
        "diff_raw": diff_raw,
        "diff_snippet": diff_snippet,
        "review_prompt": review_prompt,
    }


def ensure_clean_workspace(
    repo_dir: Path,
    base_branch: str,
    session_logger: Optional[Any] = None,
    interactive: bool = True,
    prompt_callback: Optional[Callable[[List[str]], str]] = None,
) -> bool:
    """Check if repository workspace has uncommitted tracked changes, waiting interactively if needed."""
    attempt = 0
    while True:
        attempt += 1
        dirty_tracked, untracked = get_workspace_status(repo_dir)
        if not dirty_tracked:
            if attempt > 1:
                print(f"{Colors.GREEN}[OK] Main workspace is now clean. Proceeding with merge...{Colors.RESET}")
                if session_logger:
                    session_logger.log_event("coordinator", "merge", "workspace_clean_verified", {"attempts": attempt})
            return True

        if session_logger:
            session_logger.log_event("coordinator", "merge", "workspace_dirty_detected", {
                "attempt": attempt,
                "dirty_tracked": dirty_tracked,
                "untracked_count": len(untracked),
            })

        print(f"\n{Colors.YELLOW}[WARNING] Main workspace has uncommitted local changes on '{base_branch}':{Colors.RESET}")
        for d in dirty_tracked:
            print(f"{Colors.YELLOW}  {d}{Colors.RESET}")
        print(f"{Colors.CYAN}Please stash ('git stash') or commit your local changes before merging.{Colors.RESET}")

        if not interactive:
            print(f"{Colors.RED}[ERROR] Non-interactive mode cannot wait for workspace cleanup. Aborting merge.{Colors.RESET}")
            if session_logger:
                session_logger.log_event("coordinator", "merge", "merge_aborted_dirty_workspace_unattended")
            return False

        if prompt_callback is not None:
            action = prompt_callback(dirty_tracked)
            if action.lower() in ("abort", "cancel"):
                return False
            continue

        try:
            choice = input(
                f"{Colors.GREEN}Press [Enter] to re-check and retry merge (or type 'abort' to cancel): {Colors.RESET}"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}[ABORT] Workspace cleanup cancelled by user.{Colors.RESET}")
            if session_logger:
                session_logger.log_event("coordinator", "merge", "workspace_clean_aborted_by_user")
            return False

        if choice.lower() in ("abort", "cancel", "c"):
            print(f"{Colors.YELLOW}[INFO] Merge cancelled by user due to uncommitted workspace changes.{Colors.RESET}")
            if session_logger:
                session_logger.log_event("coordinator", "merge", "workspace_clean_aborted_by_user")
            return False


def review_and_merge(
    worktree_name: str,
    branch_name: str,
    base_branch: str = "",
    auto_approve: bool = False,
    interactive: bool = True,
    repo_dir: Optional[Path] = None,
    session_logger: Optional[Any] = None,
    approval_callback: Optional[Callable[[], bool]] = None,
) -> bool:
    """Generate an AI code review with agy, request approval, and perform linear/FF merge."""
    if repo_dir is None:
        repo_dir = get_target_repo()

    worktree_host_dir = repo_dir / ".worktrees" / worktree_name
    if worktree_host_dir.is_dir():
        worktree_repair(repo_dir, worktree_host_dir)

    if not base_branch:
        base_branch = get_current_branch(repo_dir)
        if not base_branch:
            raise RuntimeError("Could not determine base branch to merge into. Please specify base branch.")

    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Code Review & Merge: {branch_name} -> {base_branch}        {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Worktree Name : {worktree_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Feature Branch: {branch_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Target Branch : {base_branch}{Colors.RESET}")

    review_data = prepare_review_data(worktree_name, branch_name, base_branch, repo_dir)
    commits = review_data["commits"]
    diff_stat = review_data["diff_stat"]
    diff_raw = review_data["diff_raw"]
    diff_snippet = review_data["diff_snippet"]
    review_prompt = review_data["review_prompt"]

    if not commits and not diff_raw:
        print(f"\n{Colors.YELLOW}[WARNING] No differences found between '{branch_name}' and '{base_branch}'.{Colors.RESET}")
        print(f"{Colors.YELLOW}No changes to review or merge.{Colors.RESET}")
        return False

    print(f"\n{Colors.CYAN}[1/3] Commits on '{branch_name}':{Colors.RESET}")
    for commit in commits:
        print(f"{Colors.WHITE}  * {commit}{Colors.RESET}")

    print(f"\n{Colors.CYAN}[2/3] Changed Files:{Colors.RESET}")
    for line in diff_stat.splitlines():
        print(f"{Colors.GRAY}  {line}{Colors.RESET}")

    # 2. Strict Check for agy on host
    agy_bin = verify_agy_installed()

    # 3. Generate detailed summary with agy
    print(f"\n{Colors.CYAN}[3/3] Generating AI Code Review Summary using agy...{Colors.RESET}")
    print(f"\n{Colors.CYAN}===================== AI REVIEW SUMMARY ====================={Colors.RESET}")
    agy_res = subprocess.run([agy_bin, "--dangerously-skip-permissions", "-p", review_prompt])
    if agy_res.returncode != 0:
        print(f"{Colors.YELLOW}[WARNING] agy CLI review generation failed.{Colors.RESET}")
        print(f"{Colors.GRAY}Showing raw git diff stat instead:\n{diff_stat}{Colors.RESET}")
    print(f"{Colors.CYAN}============================================================\n{Colors.RESET}")

    # 4. Prompt user for merge approval unless auto_approve
    if auto_approve:
        approved = True
    elif approval_callback is not None:
        approved = approval_callback()
    elif interactive:
        try:
            resp = input(
                f"{Colors.YELLOW}Do you approve merging branch '{branch_name}' into '{base_branch}'? (y/N): {Colors.RESET}"
            ).strip()
            approved = resp.lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            approved = False
    else:
        approved = False

    if approved:
        if not ensure_clean_workspace(repo_dir, base_branch, session_logger, interactive):
            return False

        print(f"\n{Colors.CYAN}[INFO] Checking out base branch '{base_branch}'...{Colors.RESET}")
        co_res = run_git(["checkout", base_branch], cwd=repo_dir, capture_output=True)
        if co_res.returncode != 0:
            err_msg = co_res.stderr.strip() or co_res.stdout.strip()
            print(f"{Colors.RED}[ERROR] Failed to checkout base branch '{base_branch}':{Colors.RESET}")
            print(f"{Colors.YELLOW}{err_msg}{Colors.RESET}")
            if session_logger:
                session_logger.log_event("coordinator", "merge", "checkout_failed", {"error": err_msg})
            return False

        print(f"\n{Colors.CYAN}[INFO] Merging branch '{branch_name}' into '{base_branch}' (fast-forward)...{Colors.RESET}")
        if session_logger:
            session_logger.log_event("coordinator", "merge", "fast_forward_attempt", {
                "branch": branch_name,
                "target": base_branch,
            })

        ff_res = run_git(["merge", "--ff-only", branch_name], cwd=repo_dir, capture_output=True)
        if ff_res.returncode == 0:
            print(f"{Colors.GREEN}[SUCCESS] Fast-forward merge completed.{Colors.RESET}")
            if session_logger:
                session_logger.log_event("coordinator", "merge", "fast_forward_success")
        else:
            print(f"{Colors.YELLOW}[INFO] Fast-forward not possible. Attempting standard merge...{Colors.RESET}")
            merge_msg = format_merge_message(branch_name, base_branch)
            if session_logger:
                session_logger.log_event("coordinator", "merge", "standard_merge_attempt", {
                    "message": merge_msg
                })

            while True:
                std_res = run_git(["merge", branch_name, "-m", merge_msg], cwd=repo_dir, capture_output=True)
                if std_res.returncode == 0:
                    print(f"{Colors.GREEN}[SUCCESS] Standard merge completed successfully.{Colors.RESET}")
                    if session_logger:
                        session_logger.log_event("coordinator", "merge", "standard_merge_success")
                    break

                output_combined = (std_res.stderr + "\n" + std_res.stdout).strip()

                if "would be overwritten by merge" in output_combined:
                    print(f"\n{Colors.YELLOW}[WARNING] Untracked or local files would be overwritten by merge:{Colors.RESET}")
                    for err_line in output_combined.splitlines():
                        if "error:" in err_line or "untracked" in err_line.lower() or "\t" in err_line:
                            print(f"{Colors.YELLOW}  {err_line.strip()}{Colors.RESET}")

                    if session_logger:
                        session_logger.log_event("coordinator", "merge", "merge_blocked_by_untracked_files", {
                            "details": output_combined[:500]
                        })

                    if not interactive:
                        print(f"{Colors.RED}[ERROR] Cannot resolve untracked file collisions non-interactively. Aborting merge.{Colors.RESET}")
                        return False

                    print(f"{Colors.CYAN}Please remove, move, or stash the conflicting untracked files.{Colors.RESET}")
                    try:
                        choice = input(f"{Colors.GREEN}Press [Enter] to re-attempt merge (or type 'abort' to cancel): {Colors.RESET}").strip()
                    except (EOFError, KeyboardInterrupt):
                        return False

                    if choice.lower() in ("abort", "cancel", "c"):
                        print(f"{Colors.YELLOW}[INFO] Merge cancelled by user.{Colors.RESET}")
                        if session_logger:
                            session_logger.log_event("coordinator", "merge", "merge_aborted_by_user")
                        return False

                    continue

                unmerged = get_unmerged_files(repo_dir)
                if unmerged or is_merge_in_progress(repo_dir):
                    if session_logger:
                        session_logger.log_event("coordinator", "merge", "merge_conflict_detected", {
                            "conflicts": unmerged
                        })

                    print(f"\n{Colors.YELLOW}==================== MERGE CONFLICT DETECTED ===================={Colors.RESET}")
                    print(f"{Colors.RED}[WARNING] Git merge encountered conflict(s) in {len(unmerged)} file(s):{Colors.RESET}")
                    for u in unmerged:
                        print(f"{Colors.YELLOW}  * {u}{Colors.RESET}")
                    print(f"\n{Colors.CYAN}Instructions:{Colors.RESET}")
                    print(f"{Colors.GRAY}  1. Open the file(s) above and resolve the conflict markers (<<<<<<<, =======, >>>>>>>){Colors.RESET}")
                    print(f"{Colors.GRAY}  2. Stage the resolved file(s): git add <file>{Colors.RESET}")
                    print(f"{Colors.GRAY}  3. Press [Enter] below to finalize the merge commit.{Colors.RESET}")
                    print(f"{Colors.GRAY}  (Or type 'abort' to cancel the merge and restore base branch).{Colors.RESET}")
                    print(f"{Colors.YELLOW}================================================================={Colors.RESET}")

                    if not interactive:
                        print(f"{Colors.RED}[ERROR] Cannot resolve merge conflicts in non-interactive mode. Aborting merge.{Colors.RESET}")
                        abort_merge(repo_dir)
                        if session_logger:
                            session_logger.log_event("coordinator", "merge", "merge_conflict_unattended_abort")
                        return False

                    conflict_resolved = False
                    while not conflict_resolved:
                        try:
                            c_choice = input(f"\n{Colors.GREEN}Press [Enter] after resolving conflicts (or type 'abort' to cancel): {Colors.RESET}").strip()
                        except (EOFError, KeyboardInterrupt):
                            print(f"\n{Colors.YELLOW}[ABORT] Merge resolution cancelled. Aborting merge...{Colors.RESET}")
                            abort_merge(repo_dir)
                            if session_logger:
                                session_logger.log_event("coordinator", "merge", "merge_conflict_aborted_by_user")
                            return False

                        if c_choice.lower() in ("abort", "cancel", "c"):
                            print(f"{Colors.YELLOW}[INFO] Aborting merge to restore clean state...{Colors.RESET}")
                            abort_merge(repo_dir)
                            if session_logger:
                                session_logger.log_event("coordinator", "merge", "merge_conflict_aborted_by_user")
                            print(f"{Colors.GREEN}[OK] Base branch restored to clean state. Worktree preserved.{Colors.RESET}")
                            return False

                        remaining_unmerged = get_unmerged_files(repo_dir)
                        if remaining_unmerged:
                            print(f"\n{Colors.RED}[WARNING] The following file(s) still have unresolved conflict markers:{Colors.RESET}")
                            for ru in remaining_unmerged:
                                print(f"{Colors.YELLOW}  * {ru}{Colors.RESET}")
                            print(f"{Colors.CYAN}Please resolve the conflict markers and stage with 'git add <file>'.{Colors.RESET}")
                            if session_logger:
                                session_logger.log_event("coordinator", "merge", "merge_conflict_still_unresolved", {
                                    "remaining": remaining_unmerged
                                })
                            continue

                        print(f"\n{Colors.CYAN}[INFO] Finalizing merge commit...{Colors.RESET}")
                        commit_res = run_git(["commit", "--no-edit"], cwd=repo_dir, capture_output=True)
                        if commit_res.returncode == 0:
                            print(f"{Colors.GREEN}[SUCCESS] Merge conflicts resolved and merge commit finalized!{Colors.RESET}")
                            if session_logger:
                                session_logger.log_event("coordinator", "merge", "merge_conflicts_resolved_and_committed")
                            conflict_resolved = True
                            break
                        else:
                            commit_err = commit_res.stderr.strip() or commit_res.stdout.strip()
                            print(f"{Colors.RED}[ERROR] Failed to commit merge: {commit_err}{Colors.RESET}")
                            if session_logger:
                                session_logger.log_event("coordinator", "merge", "merge_commit_failed", {"error": commit_err})
                            abort_merge(repo_dir)
                            return False

                    break

                if std_res.returncode != 0 and not unmerged and not is_merge_in_progress(repo_dir):
                    err_msg = std_res.stderr.strip() or std_res.stdout.strip()
                    print(f"{Colors.RED}[ERROR] Merge failed unexpectedly:{Colors.RESET}")
                    print(f"{Colors.YELLOW}{err_msg}{Colors.RESET}")
                    if session_logger:
                        session_logger.log_event("coordinator", "merge", "merge_unexpected_failure", {"error": err_msg})
                    return False

        print(f"\n{Colors.GREEN}[SUCCESS] Successfully merged '{branch_name}' into '{base_branch}'!{Colors.RESET}")
        print(f"\n{Colors.CYAN}[INFO] Cleaning up worktree and temporary branch...{Colors.RESET}")
        cleanup_worktree(worktree_name, branch_name, repo_dir=repo_dir)
        return True
    else:
        print(f"\n{Colors.YELLOW}[INFO] Merge cancelled by user. Worktree preserved at:{Colors.RESET}")
        print(f"{Colors.GRAY}       {worktree_host_dir}{Colors.RESET}")
        print(f"{Colors.GRAY}To merge manually: git checkout {base_branch} && git merge {branch_name}{Colors.RESET}")
        return False


def main() -> int:
    """Standalone review-merge CLI entry point."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python -m agy_automation.review_merge <worktree_name> <branch_name> [base_branch]")
        return 0

    if len(sys.argv) < 3:
        print(f"{Colors.RED}[ERROR] Missing required arguments.{Colors.RESET}")
        print("Usage: python -m agy_automation.review_merge <worktree_name> <branch_name> [base_branch]")
        return 1

    wt_name = sys.argv[1]
    br_name = sys.argv[2]
    base_br = sys.argv[3] if len(sys.argv) > 3 else ""

    success = review_and_merge(wt_name, br_name, base_br)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
