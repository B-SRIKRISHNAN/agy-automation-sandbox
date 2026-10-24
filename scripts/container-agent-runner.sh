#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME="${1:-agent-worktree1}"
ISSUE_FILE="${2:-}"

REPO_ROOT="/workspace"
cd "$REPO_ROOT"

echo "=========================================================="
echo "   Container Agent Runner: $WORKTREE_NAME"
echo "=========================================================="

# Repair worktree paths for Linux environment
git worktree repair 2>/dev/null || true

WORKTREE_DIR="/workspace/.worktrees/$WORKTREE_NAME"
if [ ! -d "$WORKTREE_DIR" ]; then
    echo "[ERROR] Worktree directory not found at $WORKTREE_DIR"
    exit 1
fi

cd "$WORKTREE_DIR"
git worktree repair 2>/dev/null || true

echo "[INFO] Working directory: $(pwd)"
echo "[INFO] Current Git branch: $(git branch --show-current)"

# Read issue context if file exists
ISSUE_CONTENT=""
if [ -n "$ISSUE_FILE" ] && [ -f "$ISSUE_FILE" ]; then
    ISSUE_CONTENT="$(cat "$ISSUE_FILE")"
elif [ -f "$WORKTREE_DIR/ISSUE_CONTEXT.md" ]; then
    ISSUE_CONTENT="$(cat "$WORKTREE_DIR/ISSUE_CONTEXT.md")"
fi

PROMPT="You are an autonomous AI software engineer working in a dedicated git worktree at $(pwd).
Your mission is to resolve the following issue:

$ISSUE_CONTENT

Instructions:
1. Inspect the codebase, understand the problem thoroughly, and create an implementation plan.
2. Implement all necessary code, configuration, or documentation changes inside this worktree.
3. Test and verify your changes carefully.
4. Once your implementation is complete and verified, review the git diff.
5. Create a comprehensive, conventional commit message detailing:
   - Concise title (e.g. 'feat(scope): ...' or 'fix(scope): ...')
   - A short explanation of the problem and rationale
   - A bulleted list of all specific changes made
6. Stage the relevant files and commit them to the current branch using git commit.
7. Conclude your response with a concise summary of the resolved issue.
"

LOG_FILE="/tmp/agy.log"
touch "$LOG_FILE"

# Background monitor: stream tool call events live to console
(
    tail -n 0 -F "$LOG_FILE" 2>/dev/null | while IFS= read -r line; do
        if echo "$line" | grep -qi "tool_call\|run_command\|view_file\|replace_file_content\|write_to_file"; then
            echo "[AGENT] $line"
        fi
    done
) &
ACTION_MONITOR_PID=$!

# Background heartbeat: print periodic status every 10s
(
    ELAPSED=0
    while true; do
        sleep 10
        ELAPSED=$((ELAPSED + 10))
        echo "[STATUS] Agent is formulating plan / executing next step... (${ELAPSED}s elapsed)"
    done
) &
HEARTBEAT_PID=$!

echo "=========================================================="
echo "   Launching Antigravity (agy) - Live Output Below        "
echo "=========================================================="

# Pre-flight check: verify agy CLI exists in container
if ! command -v agy >/dev/null 2>&1; then
    echo "[ERROR] Antigravity CLI (agy) is not installed or not found in PATH inside the container."
    kill "$HEARTBEAT_PID" 2>/dev/null || true
    kill "$ACTION_MONITOR_PID" 2>/dev/null || true
    exit 1
fi

# Execute agy in automated mode, streaming live output to console
AGY_EXIT_CODE=0
agy --dangerously-skip-permissions --log-file "$LOG_FILE" -p "$PROMPT" || AGY_EXIT_CODE=$?

# Stop background monitors
kill "$HEARTBEAT_PID" 2>/dev/null || true
kill "$ACTION_MONITOR_PID" 2>/dev/null || true

echo "=========================================================="
echo "   Agent Execution Finished                              "
echo "=========================================================="

if [ $AGY_EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Antigravity CLI exited with error code $AGY_EXIT_CODE."
    exit $AGY_EXIT_CODE
fi

# Fallback: Check if there are unstaged or uncommitted changes remaining
DIRTY_STATUS="$(git status --porcelain)"
if [ -n "$DIRTY_STATUS" ]; then
    echo "[INFO] Detected uncommitted changes remaining in worktree. Staging and committing..."
    git add -A
    git commit -m "feat($WORKTREE_NAME): automated resolution of issue" -m "Committed remaining automated workspace changes." || true
fi

echo ""
echo "[INFO] Commits on current worktree branch:"
git log -n 3 --oneline

echo "[SUCCESS] Agent completed all tasks successfully in worktree."
