#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME="${1:-agent-worktree1}"
ISSUE_FILE="${2:-}"
INSTRUCTIONS_FILE="${3:-}"

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

# Locate repository agent instructions (AGENT_INSTRUCTIONS.md, case-insensitive)
INSTRUCTIONS_PATH=""
INSTRUCTIONS_CONTENT=""
INSTRUCTIONS_FILENAME="AGENT_INSTRUCTIONS.md"

if [ -n "$INSTRUCTIONS_FILE" ]; then
    if [ -f "$INSTRUCTIONS_FILE" ]; then
        INSTRUCTIONS_PATH="$INSTRUCTIONS_FILE"
    elif [ -f "$REPO_ROOT/$INSTRUCTIONS_FILE" ]; then
        INSTRUCTIONS_PATH="$REPO_ROOT/$INSTRUCTIONS_FILE"
    elif [ -f "$WORKTREE_DIR/$INSTRUCTIONS_FILE" ]; then
        INSTRUCTIONS_PATH="$WORKTREE_DIR/$INSTRUCTIONS_FILE"
    fi
fi

if [ -z "$INSTRUCTIONS_PATH" ]; then
    # Check common casing in repo root (/workspace) and worktree
    for candidate in \
        "$REPO_ROOT/AGENT_INSTRUCTIONS.md" \
        "$REPO_ROOT/AGENT_INSTRUCTIONS.MD" \
        "$REPO_ROOT/agent_instructions.md" \
        "$WORKTREE_DIR/AGENT_INSTRUCTIONS.md" \
        "$WORKTREE_DIR/AGENT_INSTRUCTIONS.MD" \
        "$WORKTREE_DIR/agent_instructions.md"; do
        if [ -f "$candidate" ]; then
            INSTRUCTIONS_PATH="$candidate"
            break
        fi
    done
fi

if [ -z "$INSTRUCTIONS_PATH" ]; then
    # Case-insensitive search fallback in repo root and worktree
    FOUND_IN_REPO="$(find "$REPO_ROOT" -maxdepth 1 -iname "agent_instructions.md" -type f 2>/dev/null | head -n 1)"
    if [ -n "$FOUND_IN_REPO" ] && [ -f "$FOUND_IN_REPO" ]; then
        INSTRUCTIONS_PATH="$FOUND_IN_REPO"
    else
        FOUND_IN_WT="$(find "$WORKTREE_DIR" -maxdepth 1 -iname "agent_instructions.md" -type f 2>/dev/null | head -n 1)"
        if [ -n "$FOUND_IN_WT" ] && [ -f "$FOUND_IN_WT" ]; then
            INSTRUCTIONS_PATH="$FOUND_IN_WT"
        fi
    fi
fi

if [ -n "$INSTRUCTIONS_PATH" ] && [ -f "$INSTRUCTIONS_PATH" ]; then
    INSTRUCTIONS_CONTENT="$(cat "$INSTRUCTIONS_PATH")"
    INSTRUCTIONS_FILENAME="$(basename "$INSTRUCTIONS_PATH")"
    echo "[OK] Found repository agent instructions: $INSTRUCTIONS_PATH"
else
    echo "[INFO] No AGENT_INSTRUCTIONS.md found in repository root. Proceeding with standard instructions."
fi

# Formulate prompt for agy
if [ -n "$INSTRUCTIONS_CONTENT" ]; then
    PROMPT="You are an autonomous AI software engineer working in a dedicated git worktree at $(pwd).
Your mission is to resolve the following issue:

$ISSUE_CONTENT

Repository Agent Instructions ($INSTRUCTIONS_FILENAME):
The repository root contains specific project instructions and workflow standards in $INSTRUCTIONS_FILENAME:

--- BEGIN $INSTRUCTIONS_FILENAME ---
$INSTRUCTIONS_CONTENT
--- END $INSTRUCTIONS_FILENAME ---

Workflow Instructions:
1. Understand the Issue: Thoroughly inspect the codebase, understand the problem and requirements from the issue details.
2. Follow Sequence and Standards: Once you understand the issue, you MUST use and strictly follow the instructions in $INSTRUCTIONS_FILENAME to work in proper sequence, so that documentation, tests, and code writing are done according to instructions. This maintains consistent quality and standards across every agent run.
3. Work Inside Worktree: Implement all necessary documentation, tests, and code changes in the proper sequence inside this worktree ($(pwd)).
4. Test and Verify: Execute all tests and validation steps required by the repository instructions to ensure complete verification.
5. Review Git Diff: Review your git diff carefully to confirm all changes conform to repository conventions and standards.
6. Commit Changes: Create a comprehensive, conventional commit message detailing:
   - Concise title (e.g. 'feat(scope): ...' or 'fix(scope): ...')
   - A short explanation of the problem and rationale
   - A bulleted list of all specific changes made
   Stage the relevant files and commit them to the current branch using git commit.
7. Conclude your response with a concise summary of the resolved issue and how the sequence and standards in $INSTRUCTIONS_FILENAME were satisfied.
"
else
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
fi

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
