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
        elif lower in flag_aliases:
            normalized.append(flag_aliases[lower])
        else:
            normalized.append(arg)

    return normalized


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="start-issue",
        description="Autonomous issue-resolution pipeline powered by Antigravity CLI and container sandboxing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "issue",
        nargs="?",
        type=int,
        default=0,
        help="GitHub issue number to work on (prompts interactively if omitted).",
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
    """Parse command line arguments with pre-normalization."""
    if argv is None:
        argv = sys.argv[1:]
    normalized = normalize_args(argv)
    parser = create_parser()
    return parser.parse_args(normalized)


def prompt_issue_number(current_branch: str, engine_desc: str) -> int:
    """Prompt user interactively for a valid positive GitHub issue number."""
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Antigravity GitHub Issue Automation Coordinator        {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Base Branch      : {current_branch}{Colors.RESET}")
    print(f"{Colors.GRAY}Container Engine : {engine_desc}{Colors.RESET}")
    print("")

    try:
        user_input = input(f"{Colors.YELLOW}Enter GitHub Issue Number to work on: {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{Colors.YELLOW}[INFO] Operation cancelled by user.{Colors.RESET}")
        raise KeyboardInterrupt("Operation cancelled by user.")

    try:
        issue_num = int(user_input)
        if issue_num <= 0:
            raise ValueError()
        return issue_num
    except ValueError:
        print(f"{Colors.RED}[ERROR] Invalid issue number entered.{Colors.RESET}")
        raise ValueError("Invalid issue number entered.")
