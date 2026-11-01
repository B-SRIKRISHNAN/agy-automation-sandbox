"""End-to-end workflow for interactive issue formulation, confirmation, and GitHub publishing."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Colors, get_target_repo
from .create_issue import confirm_and_create_issue
from .generate_issue import generate_issue_statement


def run_issue_creation_workflow(
    initial_prompt: str = "",
    target_repo: Optional[Path] = None,
    dry_run: bool = False,
    engine: str = "auto",
    interactive: bool = True,
) -> int:
    """Execute the interactive issue formulation, GitHub publishing, and optional handoff workflow.

    Returns:
        0 on success, non-zero on failure or cancellation.
    """
    if target_repo is None:
        target_repo = get_target_repo()

    prompt = initial_prompt.strip()
    if not prompt and interactive:
        print(f"\n{Colors.CYAN}=========================================================={Colors.RESET}")
        print(f"{Colors.GREEN}   GitHub Issue Formulation & Creation Wizard            {Colors.RESET}")
        print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
        try:
            prompt = input(
                f"{Colors.YELLOW}Describe the bug, gap, or feature concept you want to investigate:\n> {Colors.RESET}"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}[INFO] Issue creation cancelled by user.{Colors.RESET}")
            return 1

    if not prompt:
        print(f"{Colors.RED}[ERROR] An initial description or prompt is required.{Colors.RESET}")
        return 1

    # 1. Interactive issue formulation in sandbox
    try:
        title, body = generate_issue_statement(
            initial_prompt=prompt,
            target_repo=target_repo,
            interactive=interactive,
        )
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[ABORT] Session cancelled by user.{Colors.RESET}")
        return 1
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] Issue formulation failed: {exc}{Colors.RESET}")
        return 1

    # 2. Dry run check
    if dry_run:
        print(f"\n{Colors.YELLOW}[DRY RUN] Issue generated successfully. Skipping GitHub publishing.{Colors.RESET}")
        print(f"{Colors.CYAN}Title: {title}{Colors.RESET}")
        print(f"{Colors.GRAY}{body}{Colors.RESET}")
        return 0

    # 3. Preview, edit, and create on GitHub
    created = confirm_and_create_issue(
        title=title,
        body=body,
        repo_dir=target_repo,
        interactive=interactive,
    )
    if not created:
        return 1

    new_issue_num = created.get("number")
    if not new_issue_num:
        return 0

    # 4. Optional instant handoff to start-issue
    if interactive:
        try:
            handoff = input(
                f"\n{Colors.GREEN}Would you like to start autonomous agent resolution for Issue #{new_issue_num} now? ({Colors.WHITE}y{Colors.GREEN}/{Colors.YELLOW}N{Colors.GREEN}): {Colors.RESET}"
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            handoff = ""

        if handoff in ("y", "yes"):
            print(f"\n{Colors.CYAN}[INFO] Launching autonomous pipeline for Issue #{new_issue_num}...{Colors.RESET}")
            from .orchestrator import run_pipeline
            return run_pipeline(
                issue_number=new_issue_num,
                engine=engine,
            )

    return 0
