"""GitHub issue fetching, preview, and context bundling for agy-automation."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import Colors
from .exceptions import GitHubCliNotFoundError, IssueNotFoundError


def verify_gh_installed() -> str:
    """Verify that GitHub CLI (gh) is installed and available in PATH."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        raise GitHubCliNotFoundError(
            "GitHub CLI (gh) is not installed or not in PATH.\n"
            "Please install gh to fetch GitHub issues: https://cli.github.com"
        )
    return gh_bin


def fetch_issue_payload(
    issue_number: int,
    repo_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute gh issue view and parse JSON response."""
    gh_bin = verify_gh_installed()
    cmd = [
        gh_bin,
        "issue",
        "view",
        str(issue_number),
        "--json",
        "number,title,body,url,author,labels,comments",
    ]

    kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
    }
    if repo_dir:
        kwargs["cwd"] = str(repo_dir)

    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0 or not result.stdout.strip():
        raise IssueNotFoundError(
            f"Failed to fetch issue #{issue_number} from GitHub. "
            "Please check the issue number and your permissions."
        )

    try:
        data = json.loads(result.stdout)
        return data
    except Exception as exc:
        raise IssueNotFoundError(f"Failed to parse issue #{issue_number} JSON payload: {exc}") from exc


def list_github_issues(
    repo_dir: Optional[Path] = None,
    state: str = "open",
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """List issues for a repository via gh issue list."""
    gh_bin = verify_gh_installed()
    cmd = [
        gh_bin,
        "issue",
        "list",
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,state,author,labels,updatedAt,url,comments",
    ]

    kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
    }
    if repo_dir:
        kwargs["cwd"] = str(repo_dir)

    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def get_issue_provider_status(repo_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Check GitHub CLI installation, authentication, and remote origin availability."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        return {
            "available": False,
            "gh_installed": False,
            "authenticated": False,
            "has_remote": False,
            "remote_url": "",
            "reason": "GitHub CLI (gh) is not installed on PATH",
        }

    # Check authentication status
    auth_proc = subprocess.run(
        [gh_bin, "auth", "status"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    is_authenticated = (auth_proc.returncode == 0)

    # Check git remote origin
    remote_url = ""
    has_remote = False
    if repo_dir and Path(repo_dir).exists():
        rem_proc = subprocess.run(
            ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if rem_proc.returncode == 0 and rem_proc.stdout.strip():
            remote_url = rem_proc.stdout.strip()
            has_remote = True

    is_available = bool(gh_bin and is_authenticated and has_remote)
    reason = None
    if not is_authenticated:
        reason = "GitHub CLI is not authenticated (run 'gh auth login')"
    elif not has_remote:
        reason = "Target repository has no 'origin' remote configured"

    return {
        "available": is_available,
        "gh_installed": True,
        "authenticated": is_authenticated,
        "has_remote": has_remote,
        "remote_url": remote_url,
        "reason": reason,
    }


def build_markdown_context(issue_data: Dict[str, Any]) -> str:
    """Format structured ISSUE_CONTEXT.md content."""
    num = issue_data.get("number", "")
    title = issue_data.get("title", "")
    url = issue_data.get("url", "")

    author_obj = issue_data.get("author") or {}
    author = author_obj.get("login", "Unknown") if isinstance(author_obj, dict) else "Unknown"

    raw_labels = issue_data.get("labels") or []
    if raw_labels and isinstance(raw_labels, list):
        labels_list = [l.get("name", "") for l in raw_labels if isinstance(l, dict) and l.get("name")]
        labels_str = ", ".join(labels_list) if labels_list else "None"
    else:
        labels_str = "None"

    body = issue_data.get("body", "") or ""

    comments = issue_data.get("comments") or []
    if comments and isinstance(comments, list):
        comments_block = ""
        for c in comments:
            c_author_obj = c.get("author") or {}
            c_author = c_author_obj.get("login", "Unknown") if isinstance(c_author_obj, dict) else "Unknown"
            c_body = c.get("body", "")
            comments_block += f"\n\n### Comment by @{c_author}\n{c_body}"
    else:
        comments_block = "\n*(No comments)*"

    context = f"""# Issue #{num}: {title}
- **URL**: {url}
- **Author**: {author}
- **Labels**: {labels_str}

## Description
{body}

## Comments{comments_block}
"""
    return context


def fetch_and_confirm_issue(
    issue_number: int,
    output_path: Optional[Path] = None,
    auto_approve: bool = False,
    interactive: bool = True,
    prompt_handler: Optional[Callable[[str], bool]] = None,
    repo_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch issue, display preview, request confirmation, and optionally write output."""
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Fetching GitHub Issue #{issue_number}                    {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")

    issue_data = fetch_issue_payload(issue_number, repo_dir=repo_dir)
    num = issue_data.get("number", issue_number)
    title = issue_data.get("title", "")
    url = issue_data.get("url", "")
    author_obj = issue_data.get("author") or {}
    author = author_obj.get("login", "Unknown") if isinstance(author_obj, dict) else "Unknown"

    raw_labels = issue_data.get("labels") or []
    labels_list = [l.get("name", "") for l in raw_labels if isinstance(l, dict) and l.get("name")]
    labels_str = ", ".join(labels_list) if labels_list else "None"

    body = issue_data.get("body", "") or ""

    print(f"\n{Colors.CYAN}Issue #{num}: {Colors.YELLOW}{title}{Colors.RESET}")
    print(f"{Colors.GRAY}Author : {Colors.WHITE}{author}{Colors.RESET}")
    print(f"{Colors.GRAY}URL    : {Colors.CYAN}{url}{Colors.RESET}")
    print(f"{Colors.GRAY}Labels : {Colors.WHITE}{labels_str}{Colors.RESET}")
    print(f"\n{Colors.GRAY}--- Description Preview ---{Colors.RESET}")
    if body:
        preview = body[:500] + ("\n... [truncated]" if len(body) > 500 else "")
        print(f"{Colors.WHITE}{preview}{Colors.RESET}")
    else:
        print(f"{Colors.GRAY}(No description provided){Colors.RESET}")
    print(f"{Colors.GRAY}---------------------------{Colors.RESET}\n")

    # Prompt user confirmation unless auto_approve
    if interactive and not auto_approve:
        if prompt_handler is not None:
            approved = prompt_handler(f"Do you want to proceed with Issue #{issue_number}?")
            if not approved:
                return None
        elif sys.stdin.isatty():
            try:
                resp = input(f"{Colors.YELLOW}Do you want to proceed with Issue #{issue_number}? (Y/n): {Colors.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Colors.YELLOW}[INFO] Operation cancelled by user.{Colors.RESET}")
                return None

            if resp and resp.lower() not in ("y", "yes"):
                print(f"\n{Colors.YELLOW}[INFO] Operation cancelled by user.{Colors.RESET}")
                return None

    context_text = build_markdown_context(issue_data)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(context_text)
        print(f"{Colors.GREEN}[OK] Bundled issue context written to: {output_path}{Colors.RESET}")

    return {
        "number": num,
        "title": title,
        "url": url,
        "author": author,
        "labels": labels_str,
        "body": body,
        "context": context_text,
    }


def main() -> int:
    """Standalone fetch-issue CLI entry point."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python -m agy_automation.fetch_issue <issue_number> [output_path]")
        return 0

    if len(sys.argv) < 2:
        print(f"{Colors.RED}[ERROR] Issue number parameter is required.{Colors.RESET}")
        print("Usage: python -m agy_automation.fetch_issue <issue_number> [output_path]")
        return 1

    try:
        issue_num = int(sys.argv[1])
    except ValueError:
        print(f"{Colors.RED}[ERROR] Invalid issue number.{Colors.RESET}")
        return 1

    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    try:
        res = fetch_and_confirm_issue(issue_num, output_path=out_file)
        if res is None:
            return 2
        return 0
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
