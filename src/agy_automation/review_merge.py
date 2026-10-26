"""AI code review generation, merge approval, and safe Git integration."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .cleanup import cleanup_worktree
from .config import Colors, find_agent_instructions, get_target_repo
from .engine import verify_agy_installed
from .git_utils import (
    get_commits_between,
    get_current_branch,
    get_diff_raw,
    get_diff_stat,
    get_dirty_tracked_files,
    run_git,
    worktree_repair,
)


def review_and_merge(
    worktree_name: str,
    branch_name: str,
    base_branch: str = "",
    auto_approve: bool = False,
    interactive: bool = True,
    repo_dir: Optional[Path] = None,
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

    # 1. Inspect commits and diff
    commits = get_commits_between(base_branch, branch_name, repo_dir)
    diff_stat = get_diff_stat(base_branch, branch_name, repo_dir)
    diff_raw = get_diff_raw(base_branch, branch_name, repo_dir)

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

    # Truncate diff to 2000 characters to fit CLI argument buffers
    if len(diff_raw) > 2000:
        diff_snippet = (
            diff_raw[:2000]
            + f"\n\n... [diff truncated to stay within command buffer; full changes visible via git diff {base_branch}..{branch_name}]"
        )
    else:
        diff_snippet = diff_raw

    # 2. Strict Check for agy on host
    agy_bin = verify_agy_installed()

    # 3. Generate detailed summary with agy
    print(f"\n{Colors.CYAN}[3/3] Generating AI Code Review Summary using agy...{Colors.RESET}")
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

    print(f"\n{Colors.CYAN}===================== AI REVIEW SUMMARY ====================={Colors.RESET}")
    agy_res = subprocess.run([agy_bin, "--dangerously-skip-permissions", "-p", review_prompt])
    if agy_res.returncode != 0:
        print(f"{Colors.YELLOW}[WARNING] agy CLI review generation failed.{Colors.RESET}")
        print(f"{Colors.GRAY}Showing raw git diff stat instead:\n{diff_stat}{Colors.RESET}")
    print(f"{Colors.CYAN}============================================================\n{Colors.RESET}")

    # 4. Prompt user for merge approval unless auto_approve
    if auto_approve:
        approval = "y"
    elif interactive:
        try:
            approval = input(
                f"{Colors.YELLOW}Do you approve merging branch '{branch_name}' into '{base_branch}'? (y/N): {Colors.RESET}"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            approval = ""
    else:
        approval = ""

    if approval and approval.lower() in ("y", "yes"):
        dirty_tracked = get_dirty_tracked_files(repo_dir)
        if dirty_tracked:
            print(f"{Colors.RED}[ERROR] Main workspace has uncommitted tracked changes:{Colors.RESET}")
            for d in dirty_tracked:
                print(f"{Colors.YELLOW}  {d}{Colors.RESET}")
            print(f"{Colors.YELLOW}Please stash or commit your local changes on '{base_branch}' before merging.{Colors.RESET}")
            return False

        print(f"\n{Colors.CYAN}[INFO] Checking out base branch '{base_branch}'...{Colors.RESET}")
        run_git(["checkout", base_branch], cwd=repo_dir, capture_output=False)

        print(f"\n{Colors.CYAN}[INFO] Merging branch '{branch_name}' into '{base_branch}' (fast-forward)...{Colors.RESET}")
        ff_res = run_git(["merge", "--ff-only", branch_name], cwd=repo_dir, capture_output=False)
        if ff_res.returncode == 0:
            print(f"{Colors.GREEN}[SUCCESS] Fast-forward merge completed.{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}[INFO] Fast-forward not possible. Attempting standard merge...{Colors.RESET}")
            std_res = run_git(
                ["merge", branch_name, "-m", f"Merge branch '{branch_name}' into {base_branch}"],
                cwd=repo_dir,
                capture_output=False,
            )
            if std_res.returncode != 0:
                print(f"{Colors.RED}[ERROR] Merge hit conflicts. Aborting merge to restore clean state...{Colors.RESET}")
                run_git(["merge", "--abort"], cwd=repo_dir)
                print(f"{Colors.YELLOW}        Base branch restored to clean state. Worktree preserved for manual resolution.{Colors.RESET}")
                return False

        print(f"{Colors.GREEN}[SUCCESS] Successfully merged '{branch_name}' into '{base_branch}'!{Colors.RESET}")

        # Clean up worktree and branch
        print(f"\n{Colors.CYAN}[INFO] Cleaning up worktree and temporary branch...{Colors.RESET}")
        cleanup_worktree(worktree_name, branch_name, force=True, repo_dir=repo_dir)
        return True
    else:
        print(f"\n{Colors.YELLOW}[INFO] Merge declined by user.{Colors.RESET}")
        if interactive and not auto_approve:
            try:
                keep_choice = input(
                    f"{Colors.YELLOW}Keep worktree '{worktree_name}' for manual inspection? (Y/n): {Colors.RESET}"
                ).strip()
            except (EOFError, KeyboardInterrupt):
                keep_choice = "y"

            if keep_choice and keep_choice.lower() in ("n", "no"):
                print(f"{Colors.CYAN}[INFO] Cleaning up worktree and temporary branch upon user request...{Colors.RESET}")
                cleanup_worktree(worktree_name, branch_name, force=True, repo_dir=repo_dir)
            else:
                print(f"{Colors.GREEN}[INFO] Worktree preserved at .worktrees/{worktree_name} on branch '{branch_name}'.{Colors.RESET}")
        return False


def main() -> int:
    """Standalone review-merge CLI entry point."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python -m agy_automation.review_merge <worktree_name> <branch_name> [base_branch]")
        return 0

    if len(sys.argv) < 3:
        print(f"{Colors.RED}[ERROR] WorktreeName and BranchName parameters are required.{Colors.RESET}")
        print("Usage: python -m agy_automation.review_merge <worktree_name> <branch_name> [base_branch]")
        return 1

    wt = sys.argv[1]
    br = sys.argv[2]
    base = sys.argv[3] if len(sys.argv) > 3 else ""
    merged = review_and_merge(wt, br, base)
    return 0 if merged else 1


if __name__ == "__main__":
    sys.exit(main())
