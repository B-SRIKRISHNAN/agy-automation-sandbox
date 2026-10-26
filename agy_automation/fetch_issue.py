"""GitHub issue fetching, preview, and context bundling."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Colors


def verify_gh_installed() -> str:
    """Verify that GitHub CLI (gh) is installed and available in PATH."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        raise RuntimeError(
            "GitHub CLI (gh) is not installed or not in PATH.\n"
            "Please install gh to fetch GitHub issues: https://cli.github.com"
        )
    return gh_bin


def fetch_issue_payload(issue_number: int) -> Dict[str, Any]:
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

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            f"Failed to fetch issue #{issue_number} from GitHub. "
            "Please check the issue number and your permissions."
        )

    try:
        data = json.loads(result.stdout)
        return data
    except Exception as exc:
        raise RuntimeError(f"Failed to parse issue #{issue_number} JSON payload: {exc}") from exc


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
) -> Optional[Dict[str, Any]]:
    """Fetch issue, display preview, request confirmation, and optionally write output.

    Returns:
        Dictionary with issue details and formatted context, or None if cancelled by user.
    """
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Fetching GitHub Issue #{issue_number}                    {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")

    issue_data = fetch_issue_payload(issue_number)
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

    # Prompt user confirmation
    try:
        resp = input(f"{Colors.YELLOW}Do you want to proceed with Issue #{issue_number}? (Y/n): {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{Colors.YELLOW}[INFO] Operation cancelled by user.{Colors.RESET}")
        return None

    if resp and resp.lower() not in ("y", "yes"):
        print(f"{Colors.YELLOW}[INFO] Operation cancelled by user.{Colors.RESET}")
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


def main():
    """Standalone fetch-issue CLI entry point."""
    if len(sys.argv) < 2:
        print(f"{Colors.RED}[ERROR] Issue number parameter is required.{Colors.RESET}")
        print("Usage: python -m agy_automation.fetch_issue <issue_number> [output_path]")
        sys.exit(1)

    try:
        issue_num = int(sys.argv[1])
    except ValueError:
        print(f"{Colors.RED}[ERROR] Invalid issue number.{Colors.RESET}")
        sys.exit(1)

    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    try:
        res = fetch_and_confirm_issue(issue_num, output_path=out_file)
        if res is None:
            sys.exit(2)
        sys.exit(0)
    except Exception as exc:
        print(f"{Colors.RED}[ERROR] {exc}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
