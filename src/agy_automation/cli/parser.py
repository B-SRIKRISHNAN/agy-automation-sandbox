"""Command line interface parsing, subcommands, and GitHub CLI-style help formatting for agy-automation."""

import argparse
import sys
from typing import List, Optional

SUBCOMMANDS = ("start", "session", "create-issue", "new-issue", "review", "cleanup")

FLAG_ALIASES = {
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
    "-newissue": "--new-issue",
    "--newissue": "--new-issue",
    "-new-issue": "--new-issue",
    "-createissue": "--new-issue",
    "--createissue": "--new-issue",
    "-create-issue": "--new-issue",
    "--create-issue": "--new-issue",
    "-force": "--force",
}

MAIN_HELP = """Autonomous issue-resolution & permissionless sandbox pipeline powered by Antigravity CLI.

USAGE
  agy-automation <command> [flags]
  agy-automation <issue-number> [flags]

CORE COMMANDS
  start         Resolve a GitHub issue inside an automated sandbox container
  session       Launch an interactive permissionless sandbox session (bypasses GitHub issues)
  create-issue  Interactively explore code, formulate an issue, and publish to GitHub
  review        Review changes with AI code review and merge worktree into base branch
  cleanup       Safely remove a git worktree, branch, and prune metadata

GLOBAL FLAGS
  -e, --engine <engine>     Container engine: 'auto', 'podman', or 'docker' (default: auto)
  -n, --dry-run             Simulate execution plan without modifying repo or launching container
  -b, --build               Force a rebuild of the Docker/Podman sandbox image before running
  -i, --interactive         Launch sandbox in interactive shell mode instead of automated mode
  -f, --force               Force worktree/branch deletion or recreation without prompting
  -h, --help                Show help for agy-automation or a specific command

EXAMPLES
  $ agy-automation start 42
  $ agy-automation session refactor-auth
  $ agy-automation create-issue "investigate memory leak on login"
  $ agy-automation review worktree-issue-42
  $ agy-automation cleanup worktree-issue-42 --force

LEARN MORE
  Use 'agy-automation <command> --help' for more information about a specific command.
"""

START_HELP = """Resolve a GitHub issue inside an automated sandbox container.

USAGE
  agy-automation start [<issue-number>] [flags]

ARGUMENTS
  <issue-number>            GitHub issue number to resolve (e.g. 42 or #42).
                            If omitted, you will be prompted interactively.

FLAGS
  -b, --build               Force a rebuild of the Docker/Podman sandbox image before running
  -i, --interactive         Launch sandbox in interactive shell mode instead of automated mode
  -n, --dry-run             Simulate execution plan without modifying repo or launching container
  -e, --engine <engine>     Container engine: 'auto', 'podman', or 'docker' (default: auto)
  -h, --help                Show help for this command

EXAMPLES
  $ agy-automation start 42
  $ agy-automation start 42 --build --interactive
  $ agy-automation start --dry-run
"""

SESSION_HELP = """Launch an interactive permissionless sandbox session (bypasses GitHub issues).

USAGE
  agy-automation session <session-name> [flags]

ARGUMENTS
  <session-name>            Custom name for the session (e.g. refactor-auth, spike-prototype)

FLAGS
  -b, --build               Force a rebuild of the Docker/Podman sandbox image before running
  -i, --interactive         Launch sandbox in interactive shell mode instead of automated mode
  -n, --dry-run             Simulate execution plan without modifying repo or launching container
  -e, --engine <engine>     Container engine: 'auto', 'podman', or 'docker' (default: auto)
  -h, --help                Show help for this command

EXAMPLES
  $ agy-automation session refactor-auth
  $ agy-automation session refactor-auth --interactive
  $ agy-automation session spike-proto --build
"""

CREATE_ISSUE_HELP = """Interactively explore code, formulate an issue, and publish to GitHub.

USAGE
  agy-automation create-issue [<prompt>] [flags]

ARGUMENTS
  <prompt>                  Initial problem description or bug concept

FLAGS
  -p, --prompt <text>       Initial problem description or bug concept
  -n, --dry-run             Simulate issue formulation without submitting to GitHub
  -e, --engine <engine>     Container engine: 'auto', 'podman', or 'docker' (default: auto)
  -h, --help                Show help for this command

EXAMPLES
  $ agy-automation create-issue "investigate memory leak on login"
  $ agy-automation create-issue --dry-run
"""

REVIEW_HELP = """Review changes with AI code review and merge worktree into base branch.

USAGE
  agy-automation review <worktree> [<branch>] [flags]

ARGUMENTS
  <worktree>                Name or directory of the git worktree to review
  <branch>                  Target branch to review / merge (optional)

FLAGS
  -h, --help                Show help for this command

EXAMPLES
  $ agy-automation review worktree-issue-42
  $ agy-automation review worktree-dummy session/dummy
"""

CLEANUP_HELP = """Safely remove a git worktree, branch, and prune metadata.

USAGE
  agy-automation cleanup <worktree> [<branch>] [flags]

ARGUMENTS
  <worktree>                Name or directory of the git worktree to clean up
  <branch>                  Name of the git branch to remove (optional)

FLAGS
  -f, --force               Force removal without interactive confirmation
  -h, --help                Show help for this command

EXAMPLES
  $ agy-automation cleanup worktree-issue-42
  $ agy-automation cleanup worktree-issue-42 --force
  $ agy-automation cleanup worktree-dummy session/dummy --force
"""


class AgyParser(argparse.ArgumentParser):
    """Custom ArgumentParser providing clean sectioned GitHub CLI-style help output."""

    def __init__(self, *args, custom_help: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_help = custom_help

    def format_help(self) -> str:
        if self.custom_help:
            return self.custom_help.strip() + "\n"
        return super().format_help()


def normalize_args(raw_args: List[str]) -> List[str]:
    """Pre-normalize PowerShell single-dash flags and aliases to standard flags.

    This prevents argparse from interpreting '-Build' as chained short flags '-B -u -i -l -d'.
    """
    normalized: List[str] = []

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
        elif lower in FLAG_ALIASES:
            normalized.append(FLAG_ALIASES[lower])
        else:
            normalized.append(arg)

    return normalized


def create_parser(prog: str = "agy-automation") -> argparse.ArgumentParser:
    """Create the structured CLI argument parser with subcommands and custom help."""
    parser = AgyParser(
        prog=prog,
        custom_help=MAIN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Root global flags
    parser.add_argument("--engine", "-e", choices=["auto", "podman", "docker"], default="auto")
    parser.add_argument("--dry-run", "-n", action="store_true", dest="dry_run")
    parser.add_argument("--build", "-b", action="store_true", dest="build")
    parser.add_argument("--interactive", "-i", action="store_true", dest="interactive")
    parser.add_argument("--force", "-f", action="store_true", dest="force")
    parser.add_argument("--session", "-s", default="", dest="session")
    parser.add_argument("--new-issue", "-N", action="store_true", dest="new_issue")
    parser.add_argument("--prompt", "-p", default="", dest="prompt")
    subparsers = parser.add_subparsers(dest="subcommand", parser_class=AgyParser)

    # start subcommand
    p_start = subparsers.add_parser(
        "start",
        custom_help=START_HELP,
        help="Resolve a GitHub issue inside an automated sandbox container",
    )
    p_start.add_argument("target", nargs="?", default="")
    p_start.add_argument("--build", "-b", action="store_true", dest="build")
    p_start.add_argument("--interactive", "-i", action="store_true", dest="interactive")
    p_start.add_argument("--dry-run", "-n", action="store_true", dest="dry_run")
    p_start.add_argument("--engine", "-e", choices=["auto", "podman", "docker"], default="auto")

    # session subcommand
    p_session = subparsers.add_parser(
        "session",
        custom_help=SESSION_HELP,
        help="Launch an interactive permissionless sandbox session (bypasses GitHub issues)",
    )
    p_session.add_argument("target", nargs="?", default="")
    p_session.add_argument("--session", "-s", default="", dest="session")
    p_session.add_argument("--build", "-b", action="store_true", dest="build")
    p_session.add_argument("--interactive", "-i", action="store_true", dest="interactive")
    p_session.add_argument("--dry-run", "-n", action="store_true", dest="dry_run")
    p_session.add_argument("--engine", "-e", choices=["auto", "podman", "docker"], default="auto")

    # create-issue subcommand
    p_create = subparsers.add_parser(
        "create-issue",
        aliases=["new-issue"],
        custom_help=CREATE_ISSUE_HELP,
        help="Interactively explore code, formulate an issue, and publish to GitHub",
    )
    p_create.add_argument("prompt", nargs="?", default="")
    p_create.add_argument("--prompt", "-p", default="", dest="prompt_flag")
    p_create.add_argument("--dry-run", "-n", action="store_true", dest="dry_run")
    p_create.add_argument("--engine", "-e", choices=["auto", "podman", "docker"], default="auto")

    # review subcommand
    p_review = subparsers.add_parser(
        "review",
        custom_help=REVIEW_HELP,
        help="Review changes with AI code review and merge worktree into base branch",
    )
    p_review.add_argument("target", nargs="?", default="")
    p_review.add_argument("extra_args", nargs="*", default=[])

    # cleanup subcommand
    p_cleanup = subparsers.add_parser(
        "cleanup",
        custom_help=CLEANUP_HELP,
        help="Safely remove a git worktree, branch, and prune metadata",
    )
    p_cleanup.add_argument("target", nargs="?", default="")
    p_cleanup.add_argument("extra_args", nargs="*", default=[])
    p_cleanup.add_argument("--force", "-f", action="store_true", dest="force")

    return parser


def prepare_subcommand_argv(normalized: List[str]) -> List[str]:
    """Map legacy positional/flag invocations into canonical subcommand form.

    Maintains 100% backward compatibility with syntax such as:
      - 'agy-automation 42' -> 'start 42'
      - 'agy-automation #99' -> 'start 99'
      - 'agy-automation refactor-auth' -> 'session refactor-auth'
      - 'agy-automation --session my-task' -> 'session my-task'
      - 'agy-automation --new-issue' -> 'create-issue'
    """
    has_subcommand = any(arg.lower() in SUBCOMMANDS for arg in normalized)
    is_help = any(arg in ("-h", "--help") for arg in normalized)

    # If already a subcommand or bare --help, leave as-is
    if has_subcommand or (is_help and not any(not arg.startswith("-") for arg in normalized)):
        return list(normalized)

    argv = list(normalized)

    if "--new-issue" in argv:
        argv.remove("--new-issue")
        return ["create-issue"] + argv

    if "--session" in argv:
        idx = argv.index("--session")
        argv.pop(idx)
        val = argv.pop(idx) if idx < len(argv) else ""
        return ["session", val] + argv

    # Locate first non-option argument
    non_option_idx = -1
    for i, arg in enumerate(argv):
        if not arg.startswith("-"):
            non_option_idx = i
            break

    if non_option_idx >= 0:
        target = argv.pop(non_option_idx)
        if target.isdigit() or (target.startswith("#") and target[1:].isdigit()):
            return ["start", target.lstrip("#")] + argv
        else:
            return ["session", target] + argv
    else:
        return ["start"] + argv


def parse_cli_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments with pre-normalization and legacy fallback."""
    if argv is None:
        argv = sys.argv[1:]
    normalized = normalize_args(argv)
    effective_argv = prepare_subcommand_argv(normalized)

    parser = create_parser()
    ns = parser.parse_args(effective_argv)

    # Standardize subcommand name
    cmd = getattr(ns, "subcommand", "") or ""
    if cmd in ("new-issue", "create-issue"):
        cmd = "create-issue"
    ns.command = cmd

    # Initialize all standard attributes with predictable defaults
    ns.target = getattr(ns, "target", "")
    ns.issue = 0
    ns.session = getattr(ns, "session", "")
    ns.prompt = getattr(ns, "prompt_flag", "") or getattr(ns, "prompt", "")
    ns.build = getattr(ns, "build", False)
    ns.interactive = getattr(ns, "interactive", False)
    ns.dry_run = getattr(ns, "dry_run", False)
    ns.engine = getattr(ns, "engine", "auto")
    ns.force = getattr(ns, "force", False)
    ns.new_issue = (cmd == "create-issue")
    ns.extra_args = getattr(ns, "extra_args", [])

    if cmd == "create-issue":
        ns.new_issue = True
        if not ns.prompt and ns.target:
            ns.prompt = ns.target
        ns.session = ""
        ns.issue = 0
    elif cmd == "session":
        ns.session = ns.session or ns.target
        ns.issue = 0
    elif cmd == "start":
        raw = str(ns.target).strip()
        if raw.isdigit() or (raw.startswith("#") and raw[1:].isdigit()):
            ns.issue = int(raw.lstrip("#"))
        else:
            ns.issue = 0
        ns.session = ""

    return ns
