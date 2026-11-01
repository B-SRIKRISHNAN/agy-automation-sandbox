"""Interactive terminal user prompts for agy-automation CLI."""

from typing import Tuple, Union

from .formatters import Colors


def prompt_session_or_issue(current_branch: str, engine_desc: str) -> Tuple[str, Union[str, int]]:
    """Prompt user interactively for a session name or GitHub issue number."""
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Antigravity Autonomous Sandbox Coordinator            {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Base Branch      : {current_branch}{Colors.RESET}")
    print(f"{Colors.GRAY}Container Engine : {engine_desc}{Colors.RESET}")
    print("")

    try:
        user_input = input(f"{Colors.YELLOW}Enter Session Name or GitHub Issue # (e.g. 'refactor-auth' or '42'): {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{Colors.YELLOW}[INFO] Operation cancelled by user.{Colors.RESET}")
        raise KeyboardInterrupt("Operation cancelled by user.")

    if not user_input:
        print(f"{Colors.RED}[ERROR] No session name or issue number entered.{Colors.RESET}")
        raise ValueError("No session name or issue number entered.")

    cleaned = user_input.lstrip("#")
    if cleaned.isdigit() and int(cleaned) > 0:
        return ("issue", int(cleaned))

    return ("session", user_input)


def prompt_issue_number(current_branch: str, engine_desc: str) -> int:
    """Prompt user interactively for a valid positive GitHub issue number (legacy helper)."""
    target_type, target_val = prompt_session_or_issue(current_branch, engine_desc)
    if target_type == "issue":
        return int(target_val)
    raise ValueError(f"Expected issue number, got session '{target_val}'")
