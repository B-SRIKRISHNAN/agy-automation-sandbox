"""Command line interface parsing and flag normalization for agy-automation."""

import argparse
import sys
from typing import List, Optional

from .config import Colors


def normalize_args(raw_args: List[str]) -> List[str]:
    """Pre-normalize PowerShell single-dash flags to standard double-dash GNU/POSIX flags.

    This prevents argparse from interpreting '-Build' as chained short flags '-B -u -i -l -d'.
    """
    normalized: List[str] = []
    flag_aliases = {
        "-build": "--build",
        "-buildsandbox": "--build",
        "--buildsandbox": "--build",
        "-interactive": "--interactive",
        "-interactivesandbox": "--interactive",
        "--interactivesandbox": "--interactive",
        "-dryrun": "--dry-run",
        "--dryrun": "--dry-run",
        "-containerengine": "--engine",
        "--containerengine": "--engine",
        "-session": "--session",
        "-sessionname": "--session",
        "--sessionname": "--session",
    }

    for arg in raw_args:
        lower = arg.lower()
        if lower.startswith("-containerengine="):
            val = arg.split("=", 1)[1]
            normalized.append(f"--engine={val}")
        elif lower.startswith("--containerengine="):
            val = arg.split("=", 1)[1]
            normalized.append(f"--engine={val}")
        elif lower.startswith("-engine="):
            val = arg.split("=", 1)[1]
            normalized.append(f"--engine={val}")
        elif lower.startswith("-session="):
            val = arg.split("=", 1)[1]
            normalized.append(f"--session={val}")
        elif lower.startswith("--sessionname="):
            val = arg.split("=", 1)[1]
            normalized.append(f"--session={val}")
        elif lower in flag_aliases:
            normalized.append(flag_aliases[lower])
        else:
            normalized.append(arg)

    return normalized


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="start-issue",
        description="Autonomous issue-resolution & permissionless sandbox pipeline powered by Antigravity CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "target",
        nargs="?",
        default="",
        help="GitHub issue number or custom session name (prompts interactively if omitted).",
    )
    parser.add_argument(
        "--session",
        "-s",
        default="",
        dest="session",
        help="Custom session name for permissionless sandbox execution (bypasses GitHub issues).",
    )
    parser.add_argument(
        "--build",
        "-b",
        action="store_true",
        dest="build",
        help="Force a rebuild of the Docker/Podman sandbox image before launching.",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        dest="interactive",
        help="Launch sandbox in interactive shell mode instead of fully automated mode.",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        dest="dry_run",
        help="Simulate execution plan without modifying repository, worktrees, or launching containers.",
    )
    parser.add_argument(
        "--engine",
        "-e",
        choices=["auto", "podman", "docker"],
        default="auto",
        dest="engine",
        help="Specify container engine to use: 'auto', 'podman', or 'docker' (default: auto).",
    )

    return parser


def parse_cli_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments with pre-normalization and target resolution."""
    if argv is None:
        argv = sys.argv[1:]
    normalized = normalize_args(argv)
    parser = create_parser()
    ns = parser.parse_args(normalized)

    raw_target = str(ns.target).strip()
    session_flag = str(ns.session).strip()

    if session_flag:
        ns.session = session_flag
        ns.issue = 0
    elif raw_target.isdigit() or (raw_target.startswith("#") and raw_target[1:].isdigit()):
        ns.issue = int(raw_target.lstrip("#"))
        ns.session = ""
    elif raw_target:
        ns.issue = 0
        ns.session = raw_target
    else:
        ns.issue = 0
        ns.session = ""

    return ns


def prompt_session_or_issue(current_branch: str, engine_desc: str) -> tuple[str, str | int]:
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

