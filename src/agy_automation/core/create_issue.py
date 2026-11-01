"""GitHub issue creation service and interactive confirmation."""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import Colors, get_target_repo
from .exceptions import GitHubCliNotFoundError, IssueCreationError
from .fetch_issue import verify_gh_installed


def extract_issue_number_from_url(url: str) -> Optional[int]:
    """Extract issue number from a GitHub issue URL (e.g., https://github.com/org/repo/issues/46)."""
    match = re.search(r"/issues/(\d+)", url)
    if match:
        return int(match.group(1))
    return None


def create_github_issue(
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    repo_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute gh issue create to publish a new issue to GitHub.

    Pure functional service with zero interactive prompts: suitable for CLI and API/FastAPI use.

    Returns:
        Dict with keys: number, url, title, body, labels.
    """
    if not title or not title.strip():
        raise ValueError("Issue title cannot be empty.")
    if not body or not body.strip():
        raise ValueError("Issue body cannot be empty.")

    gh_bin = verify_gh_installed()
    cmd = [
        gh_bin,
        "issue",
        "create",
        "--title",
        title.strip(),
        "--body",
        body.strip(),
    ]

    if labels:
        for lbl in labels:
            if lbl.strip():
                cmd.extend(["--label", lbl.strip()])

    if assignees:
        for asn in assignees:
            if asn.strip():
                cmd.extend(["--assignee", asn.strip()])

    kwargs: Dict[str, Any] = {
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if repo_dir:
        kwargs["cwd"] = str(repo_dir)

    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        err_msg = result.stderr.strip() or result.stdout.strip()
        raise IssueCreationError(f"GitHub CLI issue creation failed: {err_msg}")

    url = result.stdout.strip()
    issue_number = extract_issue_number_from_url(url)
    if not issue_number:
        match = re.search(r"#(\d+)", url)
        if match:
            issue_number = int(match.group(1))

    return {
        "number": issue_number,
        "url": url,
        "title": title.strip(),
        "body": body.strip(),
        "labels": labels or [],
    }


def edit_text_in_editor(initial_text: str) -> str:
    """Open initial_text in user's $EDITOR or system fallback and return modified text."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        editor = "nano" if sys.platform != "win32" else "notepad"

    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(initial_text)
        temp_path = tf.name

    try:
        subprocess.run([editor, temp_path], check=True)
        with open(temp_path, "r", encoding="utf-8") as f:
            edited_text = f.read()
        return edited_text
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def confirm_and_create_issue(
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
    repo_dir: Optional[Path] = None,
    interactive: bool = True,
    prompt_callback: Optional[Callable[[str, str], Optional[Dict[str, str]]]] = None,
) -> Optional[Dict[str, Any]]:
    """Display terminal preview of generated issue, prompt user confirmation, and publish.

    Returns:
        Dict returned by create_github_issue(), or None if cancelled.
    """
    current_title = title.strip()
    current_body = body.strip()

    while True:
        print(f"\n{Colors.CYAN}======================== GENERATED ISSUE PREVIEW ========================{Colors.RESET}")
        print(f"{Colors.YELLOW}Title:{Colors.RESET} {current_title}")
        if labels:
            print(f"{Colors.GRAY}Labels:{Colors.RESET} {', '.join(labels)}")
        print(f"{Colors.GRAY}------------------------------------------------------------------------{Colors.RESET}")
        print(current_body)
        print(f"{Colors.CYAN}========================================================================{Colors.RESET}")

        if not interactive:
            print(f"{Colors.GREEN}[INFO] Non-interactive mode: auto-publishing issue...{Colors.RESET}")
            return create_github_issue(current_title, current_body, labels=labels, repo_dir=repo_dir)

        if prompt_callback is not None:
            updated = prompt_callback(current_title, current_body)
            if updated is None:
                return None
            current_title = updated.get("title", current_title)
            current_body = updated.get("body", current_body)
            return create_github_issue(current_title, current_body, labels=labels, repo_dir=repo_dir)

        try:
            choice = input(
                f"\n{Colors.GREEN}Create this issue on GitHub? ({Colors.WHITE}Y{Colors.GREEN}/n/{Colors.CYAN}edit{Colors.GREEN}): {Colors.RESET}"
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}[ABORT] Issue creation cancelled by user.{Colors.RESET}")
            return None

        if choice in ("", "y", "yes"):
            print(f"\n{Colors.CYAN}[INFO] Submitting issue to GitHub via gh CLI...{Colors.RESET}")
            try:
                res = create_github_issue(current_title, current_body, labels=labels, repo_dir=repo_dir)
                num_str = f" #{res['number']}" if res.get("number") else ""
                print(f"{Colors.GREEN}[SUCCESS] Created GitHub Issue{num_str}!{Colors.RESET}")
                print(f"{Colors.CYAN}URL: {res['url']}{Colors.RESET}")
                return res
            except Exception as exc:
                print(f"{Colors.RED}[ERROR] Failed to create GitHub issue: {exc}{Colors.RESET}")
                return None

        elif choice in ("e", "edit"):
            combined = f"# {current_title}\n\n{current_body}"
            print(f"{Colors.CYAN}[INFO] Opening issue draft in editor...{Colors.RESET}")
            edited = edit_text_in_editor(combined)
            lines = [line.rstrip() for line in edited.splitlines()]
            if lines and lines[0].startswith("# "):
                current_title = lines[0][2:].strip()
                current_body = "\n".join(lines[1:]).strip()
            elif lines:
                current_title = lines[0].strip()
                current_body = "\n".join(lines[1:]).strip()
            continue

        else:
            print(f"{Colors.YELLOW}[INFO] Issue creation cancelled by user.{Colors.RESET}")
            return None


def main() -> int:
    """Standalone CLI entry point for create_issue."""
    parser = argparse.ArgumentParser(description="Create a GitHub issue using the GitHub CLI (gh).")
    parser.add_argument("-t", "--title", help="Issue title")
    parser.add_argument("-b", "--body", help="Issue description / body markdown")
    parser.add_argument("-F", "--body-file", help="Path to markdown file containing issue body")
    parser.add_argument("-l", "--label", action="append", help="Issue labels (repeatable)")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-approve creation without confirmation prompt")

    args = parser.parse_args()

    title = args.title or ""
    body = args.body or ""

    if args.body_file:
        bf_path = Path(args.body_file)
        if not bf_path.is_file():
            print(f"{Colors.RED}[ERROR] Body file not found: {bf_path}{Colors.RESET}")
            return 1
        with open(bf_path, "r", encoding="utf-8") as f:
            content = f.read()
        if not title:
            lines = content.splitlines()
            if lines and lines[0].startswith("# "):
                title = lines[0][2:].strip()
                body = "\n".join(lines[1:]).strip()
            else:
                body = content
        else:
            body = content

    if not title:
        try:
            title = input(f"{Colors.YELLOW}Enter issue title: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return 1

    if not body:
        try:
            body = input(f"{Colors.YELLOW}Enter issue body (or hit Ctrl+D to finish): {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return 1

    res = confirm_and_create_issue(
        title=title,
        body=body,
        labels=args.label,
        interactive=not args.yes,
    )
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
