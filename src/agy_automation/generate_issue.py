"""Interactive AI issue exploration and formulation service."""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from .cleanup import cleanup_worktree
from .config import Colors, get_target_repo
from .git_utils import sanitize_session_name
from .sandbox import run_sandbox
from .worktree import create_worktree, inject_issue_context

ISSUE_ANALYST_INSTRUCTIONS = """# Role: Issue Formulation Analyst
You are collaborating interactively with the developer to investigate, verify, and formulate a crisp, unambiguous GitHub issue.

## Your Objectives:
1. Explore the codebase using `read_file`, `search_web`, and `run_command`.
2. Check whether the problem or bug described by the developer is actually present in the code.
3. Discuss potential root causes, trade-offs, and alternative solution directions with the developer.
4. Iterate and converse with the developer until all ambiguity is eliminated.
5. Once aligned, write the finalized issue statement to `NEW_ISSUE.md` in this worktree root.

## Required Format for `NEW_ISSUE.md`:
```markdown
# Title: [Crisp, imperative title under 70 characters]

## Problem Description
[2-3 concise paragraphs explaining what is currently happening, where in the codebase, and why it is a defect or gap]

## Expected Solution
[Clear bullet points describing the expected outcome, behavior, and acceptance criteria]
```

## Strict Rules:
- **DO NOT** write a step-by-step implementation plan. (A separate agent will plan and implement later).
- **DO NOT** modify codebase files, create feature branches, or apply code fixes during this session.
- Keep the entire issue statement crisp, sharp, and under 250 words.
"""


def parse_generated_issue(content: str) -> Tuple[str, str]:
    """Parse title and body from a generated NEW_ISSUE.md file.

    Handles '# Title: ...', '# ...', or plain first line titles.
    """
    lines = content.strip().splitlines()
    if not lines:
        raise ValueError("Generated issue content is empty.")

    first_line = lines[0].strip()
    title = ""
    body_start_idx = 1

    if first_line.startswith("# Title:"):
        title = first_line[8:].strip()
    elif first_line.startswith("# title:"):
        title = first_line[8:].strip()
    elif first_line.startswith("# "):
        title = first_line[2:].strip()
    else:
        title = first_line

    body = "\n".join(lines[body_start_idx:]).strip()
    if not body and not title:
        raise ValueError("Could not parse valid title and body from issue content.")

    return title, body


def generate_issue_statement(
    initial_prompt: str = "",
    target_repo: Optional[Path] = None,
    session_slug: str = "",
    interactive: bool = True,
    session_logger: Optional[Any] = None,
) -> Tuple[str, str]:
    """Launch an interactive sandbox session to investigate code and formulate a crisp issue statement.

    Creates an isolated scratch worktree, starts agy in interactive exploration mode,
    extracts the final NEW_ISSUE.md, and cleans up the scratch worktree upon completion.

    Returns:
        (title, body) tuple.
    """
    if target_repo is None:
        target_repo = get_target_repo()

    if not session_slug:
        slug_seed = initial_prompt[:25] if initial_prompt else "issue-draft"
        clean_seed = sanitize_session_name(slug_seed)
        session_slug = f"draft-{clean_seed}-{int(time.time()) % 10000}"

    worktree_name = f"worktree-{session_slug}"
    branch_name = f"session/{session_slug}"

    print(f"\n{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Interactive AI Issue Formulation Sandbox              {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Target Repo  : {target_repo}{Colors.RESET}")
    print(f"{Colors.GRAY}Draft Session: {session_slug}{Colors.RESET}")
    print(f"{Colors.GRAY}Scratch WT   : {worktree_name}{Colors.RESET}")

    if session_logger:
        session_logger.log_event("coordinator", "formulation", "session_started", {
            "session_slug": session_slug,
            "initial_prompt": initial_prompt[:200],
        })

    # 1. Create temporary scratch worktree
    print(f"\n{Colors.CYAN}[1/4] Preparing scratch exploration worktree...{Colors.RESET}")
    worktree_path = create_worktree(
        worktree_name=worktree_name,
        branch_name=branch_name,
        repo_dir=target_repo,
        force=True,
    )

    # 2. Inject instructions and initial prompt
    print(f"{Colors.CYAN}[2/4] Injecting issue formulation analyst instructions...{Colors.RESET}")
    instr_file = worktree_path / "AGENT_INSTRUCTIONS.md"
    with open(instr_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(ISSUE_ANALYST_INSTRUCTIONS)

    context_content = f"""# Issue Formulation Request
## Initial Developer Concept
{initial_prompt or 'Explore the codebase with the developer to formulate an issue statement.'}
"""
    inject_issue_context(worktree_path, context_content)

    # 3. Launch interactive sandbox
    print(f"{Colors.CYAN}[3/4] Launching interactive Antigravity sandbox session...{Colors.RESET}")
    print(f"{Colors.GRAY}Tip: Chat with agy to investigate the code. Once aligned, agy will create NEW_ISSUE.md.{Colors.RESET}")
    print(f"{Colors.GRAY}Type 'exit' or '/exit' when you are satisfied with the draft.{Colors.RESET}\n")

    sandbox_exit = 0
    try:
        sandbox_exit = run_sandbox(
            worktree_name=worktree_name,
            issue_file=f".worktrees/{worktree_name}/ISSUE_CONTEXT.md",
            target_repo=target_repo,
            instructions_file=f".worktrees/{worktree_name}/AGENT_INSTRUCTIONS.md",
            interactive=interactive,
            session_logger=session_logger,
        )
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[ABORT] Issue formulation session interrupted by user.{Colors.RESET}")
        cleanup_worktree(worktree_name, branch_name, force=True, repo_dir=target_repo)
        raise

    # 4. Extract generated NEW_ISSUE.md
    print(f"\n{Colors.CYAN}[4/4] Extracting generated issue statement...{Colors.RESET}")
    new_issue_file = worktree_path / "NEW_ISSUE.md"
    alt_issue_file = worktree_path / "new_issue.md"

    title = ""
    body = ""

    if new_issue_file.is_file():
        with open(new_issue_file, "r", encoding="utf-8") as f:
            content = f.read()
        title, body = parse_generated_issue(content)
    elif alt_issue_file.is_file():
        with open(alt_issue_file, "r", encoding="utf-8") as f:
            content = f.read()
        title, body = parse_generated_issue(content)
    else:
        # Fallback: check if agent committed something to git log
        print(f"{Colors.YELLOW}[WARNING] NEW_ISSUE.md was not explicitly written by agy.{Colors.RESET}")
        title = initial_prompt.splitlines()[0] if initial_prompt else "Automated issue proposal"
        body = initial_prompt if initial_prompt else "No detailed issue statement generated."

    # Cleanup scratch worktree
    print(f"{Colors.CYAN}[INFO] Cleaning up scratch exploration worktree...{Colors.RESET}")
    cleanup_worktree(worktree_name, branch_name, force=True, repo_dir=target_repo)

    if session_logger:
        session_logger.log_event("coordinator", "formulation", "session_finished", {
            "title": title,
            "body_length": len(body),
        })

    return title, body


def main() -> int:
    """Standalone CLI entry point for generate_issue."""
    parser = argparse.ArgumentParser(description="Interactively explore codebase and formulate a GitHub issue.")
    parser.add_argument("prompt", nargs="?", default="", help="Initial issue description or bug concept")
    args = parser.parse_args()

    prompt = args.prompt
    if not prompt:
        try:
            prompt = input(f"{Colors.YELLOW}Describe the issue or feature concept to investigate: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return 1

    try:
        title, body = generate_issue_statement(initial_prompt=prompt, interactive=True)
        print(f"\n{Colors.GREEN}==================== GENERATED ISSUE ===================={Colors.RESET}")
        print(f"{Colors.YELLOW}Title:{Colors.RESET} {title}\n")
        print(f"{Colors.WHITE}{body}{Colors.RESET}")
        print(f"{Colors.GREEN}========================================================={Colors.RESET}")
        return 0
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] Issue formulation failed: {exc}{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
