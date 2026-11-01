"""Primary entry point and command router for agy-automation CLI."""

import sys
from pathlib import Path
from typing import List, Optional

from ..core.config import Colors, get_target_repo
from ..core.configuration import load_merged_config
from ..core.context import PipelineContext
from ..core.exceptions import AutomationError
from .formatters import print_stream_line
from .parser import parse_cli_args


def main(argv: Optional[List[str]] = None) -> int:
    """Parse CLI input, merge YAML configuration, assemble PipelineContext, and dispatch."""
    args = parse_cli_args(argv)

    # 1. Handle specialized subcommands
    cmd = getattr(args, "command", "")

    if cmd == "create-issue" or getattr(args, "new_issue", False):
        from ..core.issue_workflow import run_issue_creation_workflow
        try:
            return run_issue_creation_workflow(
                initial_prompt=getattr(args, "prompt", ""),
                dry_run=args.dry_run,
                engine=args.engine,
                interactive=True,
            )
        except AutomationError as exc:
            print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
            return 1

    if cmd == "cleanup":
        from ..core.cleanup import cleanup_worktree
        wt = args.target or getattr(args, "session", "") or "agent-worktree1"
        extra = getattr(args, "extra_args", [])
        br = extra[0] if extra else (getattr(args, "session", "") or "agent-branch1")
        force = getattr(args, "force", False)
        success = cleanup_worktree(worktree_name=wt, branch_name=br, force=force)
        return 0 if success else 1

    if cmd == "review":
        from ..core.review_merge import review_and_merge
        wt = args.target or getattr(args, "session", "") or "agent-worktree1"
        extra = getattr(args, "extra_args", [])
        br = extra[0] if extra else (getattr(args, "session", "") or "agent-branch1")
        success = review_and_merge(worktree_name=wt, branch_name=br)
        return 0 if success else 1

    # 2. Pipeline Execution (start, session, or default target)
    try:
        repo = get_target_repo()
    except Exception:
        repo = Path.cwd()

    cfg = load_merged_config(repo)

    # Resolve engine with CLI flag precedence over YAML
    engine = args.engine if args.engine != "auto" else cfg.get("default_engine", "auto")

    # Determine target type and ID
    if getattr(args, "session", ""):
        target_type = "session"
        target_id = args.session
    elif getattr(args, "issue", 0) > 0:
        target_type = "issue"
        target_id = str(args.issue)
    else:
        target_type = "prompt"
        target_id = ""

    from ..core.orchestrator import run_pipeline

    if target_type == "prompt":
        return run_pipeline(
            issue_number=0,
            session_name="",
            build=args.build,
            interactive=args.interactive,
            dry_run=args.dry_run,
            engine=engine,
        )

    ctx = PipelineContext(
        target_repo=repo,
        target_type=target_type,
        target_id=target_id,
        base_branch=cfg.get("base_branch", "master"),
        engine=engine,
        interactive=args.interactive or cfg.get("interactive", True),
        auto_approve=cfg.get("auto_approve", False),
        dry_run=args.dry_run,
        build=args.build,
    )

    try:
        return run_pipeline(context=ctx)
    except AutomationError as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        return 1
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[ABORT] Operation cancelled by user.{Colors.RESET}")
        return 130


if __name__ == "__main__":
    sys.exit(main())
