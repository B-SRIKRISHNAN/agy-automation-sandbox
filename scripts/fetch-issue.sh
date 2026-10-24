#!/usr/bin/env bash
set -eo pipefail

ISSUE_NUMBER="${1:-}"
OUTPUT_PATH="${2:-}"

if [ -z "$ISSUE_NUMBER" ]; then
    echo "[ERROR] Issue number parameter is required."
    echo "Usage: ./scripts/fetch-issue.sh <issue_number> [output_path]"
    exit 1
fi

# Verify GitHub CLI (gh)
if ! command -v gh >/dev/null 2>&1; then
    echo "[ERROR] GitHub CLI (gh) is not installed or not found in PATH."
    echo "Please install gh to fetch GitHub issues: https://cli.github.com"
    exit 1
fi

echo "=========================================================="
echo "   Fetching GitHub Issue #$ISSUE_NUMBER                    "
echo "=========================================================="

RAW_JSON="$(gh issue view "$ISSUE_NUMBER" --json number,title,body,url,author,labels,comments 2>/dev/null || true)"
if [ -z "$RAW_JSON" ]; then
    echo "[ERROR] Failed to fetch issue #$ISSUE_NUMBER from GitHub. Please check the issue number and your permissions."
    exit 1
fi

# Use python3 to parse JSON and output structured fields safely
PARSE_SCRIPT='
import sys, json

try:
    data = json.loads(sys.stdin.read())
except Exception as e:
    sys.exit(1)

num = data.get("number", "")
title = data.get("title", "")
url = data.get("url", "")
author = data.get("author", {}).get("login", "Unknown") if data.get("author") else "Unknown"
labels = ", ".join([l.get("name", "") for l in data.get("labels", [])]) if data.get("labels") else "None"
body = data.get("body", "") or ""

# Print preview to stderr for display
sys.stderr.write(f"\nIssue #{num}: {title}\n")
sys.stderr.write(f"Author : {author}\n")
sys.stderr.write(f"URL    : {url}\n")
sys.stderr.write(f"Labels : {labels}\n")
sys.stderr.write("\n--- Description Preview ---\n")
preview = body[:500] + ("\n... [truncated]" if len(body) > 500 else "") if body else "(No description provided)"
sys.stderr.write(f"{preview}\n")
sys.stderr.write("---------------------------\n\n")

# Build Markdown Context
comments_block = ""
comments = data.get("comments", [])
if comments:
    for c in comments:
        c_author = c.get("author", {}).get("login", "Unknown") if c.get("author") else "Unknown"
        c_body = c.get("body", "")
        comments_block += f"\n\n### Comment by @{c_author}\n{c_body}"
else:
    comments_block = "\n*(No comments)*"

context = f"""# Issue #{num}: {title}
- **URL**: {url}
- **Author**: {author}
- **Labels**: {labels}

## Description
{body}

## Comments{comments_block}
"""

sys.stdout.write(context)
'

CONTEXT_CONTENT="$(echo "$RAW_JSON" | python3 -c "$PARSE_SCRIPT" 2>&1 1>/tmp/issue_context_out.md)"
RET_CODE=$?

# Show preview from stderr
cat /tmp/issue_context_out.md >/dev/null 2>&1 || true

if [ $RET_CODE -ne 0 ] || [ ! -f /tmp/issue_context_out.md ]; then
    echo "[ERROR] Failed to parse issue payload."
    exit 1
fi

# Prompt confirmation
read -r -p "Do you want to proceed with Issue #$ISSUE_NUMBER? (Y/n): " RESP
if [[ "$RESP" =~ ^[Nn] ]]; then
    echo "[INFO] Operation cancelled by user."
    rm -f /tmp/issue_context_out.md
    exit 2
fi

if [ -n "$OUTPUT_PATH" ]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    cp /tmp/issue_context_out.md "$OUTPUT_PATH"
    echo "[OK] Bundled issue context written to: $OUTPUT_PATH"
fi

rm -f /tmp/issue_context_out.md
exit 0
