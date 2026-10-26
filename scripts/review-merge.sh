#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME="${1:-}"
BRANCH_NAME="${2:-}"
BASE_BRANCH="${3:-}"

if [ -z "$WORKTREE_NAME" ] || [ -z "$BRANCH_NAME" ]; then
    echo "[ERROR] WorktreeName and BranchName parameters are required."
    echo "Usage: ./scripts/review-merge.sh <worktree_name> <branch_name> [base_branch]"
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "[ERROR] Not inside a Git repository."
    exit 1
fi

cd "$REPO_ROOT"
WORKTREE_HOST_DIR="$REPO_ROOT/.worktrees/$WORKTREE_NAME"
if [ -d "$WORKTREE_HOST_DIR" ]; then
    git worktree repair "$WORKTREE_HOST_DIR" >/dev/null 2>&1 || true
fi

if [ -z "$BASE_BRANCH" ]; then
    BASE_BRANCH="$(git branch --show-current 2>/dev/null || true)"
    if [ -z "$BASE_BRANCH" ]; then
        echo "[ERROR] Could not determine base branch to merge into. Please pass base branch as third argument."
        exit 1
    fi
fi

echo "=========================================================="
echo "   Code Review & Merge: $BRANCH_NAME -> $BASE_BRANCH"
echo "=========================================================="
echo "Worktree Name : $WORKTREE_NAME"
echo "Feature Branch: $BRANCH_NAME"
echo "Target Branch : $BASE_BRANCH"

# 1. Inspect commits and diff
COMMITS="$(git log "$BASE_BRANCH..$BRANCH_NAME" --oneline 2>/dev/null || true)"
DIFF_STAT="$(git diff "$BASE_BRANCH..$BRANCH_NAME" --stat 2>/dev/null || true)"
DIFF_RAW="$(git diff "$BASE_BRANCH..$BRANCH_NAME" 2>/dev/null || true)"

if [ -z "$COMMITS" ] && [ -z "$DIFF_RAW" ]; then
    echo ""
    echo "[WARNING] No differences found between '$BRANCH_NAME' and '$BASE_BRANCH'."
    echo "No changes to review or merge."
    exit 0
fi

echo ""
echo "[1/3] Commits on '$BRANCH_NAME':"
if [ -n "$COMMITS" ]; then
    echo "$COMMITS" | sed 's/^/  * /'
fi

echo ""
echo "[2/3] Changed Files:"
if [ -n "$DIFF_STAT" ]; then
    echo "$DIFF_STAT" | sed 's/^/  /'
fi

# Truncate diff to 2000 characters to fit shell argument buffers
DIFF_SNIPPET="$DIFF_RAW"
if [ "${#DIFF_RAW}" -gt 2000 ]; then
    DIFF_SNIPPET="${DIFF_RAW:0:2000}"$'\n\n... [diff truncated to stay within command buffer; full changes visible via git diff '"$BASE_BRANCH".."$BRANCH_NAME"']'
fi

# 2. Strict Check for agy on host (Option B)
if ! command -v agy >/dev/null 2>&1; then
    echo ""
    echo "[ERROR] Antigravity CLI (agy) is not installed or not in your PATH."
    echo "Please install agy to proceed: https://antigravity.google/cli"
    exit 1
fi

# 3. Generate detailed summary with agy
echo ""
echo "[3/3] Generating AI Code Review Summary using agy..."

# Check for repository agent instructions (AGENT_INSTRUCTIONS.md, case-insensitive)
INSTRUCTIONS_CHECK_SECTION=""
INSTRUCTIONS_FILE_REVIEW=""
for name in "AGENT_INSTRUCTIONS.md" "AGENT_INSTRUCTIONS.MD" "agent_instructions.md"; do
    if [ -f "$REPO_ROOT/$name" ]; then
        INSTRUCTIONS_FILE_REVIEW="$REPO_ROOT/$name"
        break
    fi
done
if [ -z "$INSTRUCTIONS_FILE_REVIEW" ]; then
    FOUND_INSTR="$(find "$REPO_ROOT" -maxdepth 1 -iname "agent_instructions.md" -type f 2>/dev/null | head -n 1)"
    if [ -n "$FOUND_INSTR" ] && [ -f "$FOUND_INSTR" ]; then
        INSTRUCTIONS_FILE_REVIEW="$FOUND_INSTR"
    fi
fi

if [ -n "$INSTRUCTIONS_FILE_REVIEW" ] && [ -f "$INSTRUCTIONS_FILE_REVIEW" ]; then
    INSTR_BASENAME="$(basename "$INSTRUCTIONS_FILE_REVIEW")"
    INSTRUCTIONS_CHECK_SECTION="
### 5. Repository Standards & Agent Instructions Compliance
(Assess whether the code, documentation, and tests comply with the sequence and standards in $INSTR_BASENAME)"
fi

REVIEW_PROMPT="You are a senior principal engineer performing a code review. Analyze the following commits and diff for feature branch '$BRANCH_NAME' targeting '$BASE_BRANCH'.
Generate a comprehensive, crystal-clear review formatted with markdown headings:

### 1. Summary of Changes
(What problem was solved, core architectural changes, and rationale)

### 2. Detailed File-by-File Breakdown
(Grouped by module or component, describing specific modifications)

### 3. Impact & Risk Assessment
(Dependencies, database migrations, configuration updates, potential regressions)

### 4. Verification & Testing Checklist
(Recommended steps to test and verify these changes)$INSTRUCTIONS_CHECK_SECTION

---
Commits:
$COMMITS

Diff Stat:
$DIFF_STAT

Diff Details:
$DIFF_SNIPPET
"

echo ""
echo "===================== AI REVIEW SUMMARY ====================="
agy --dangerously-skip-permissions -p "$REVIEW_PROMPT" || {
    echo "[WARNING] agy CLI review generation failed."
    echo "Showing raw git diff stat instead:"
    echo "$DIFF_STAT"
}
echo "============================================================"
echo ""

# 4. Prompt user for merge approval
read -r -p "Do you approve merging branch '$BRANCH_NAME' into '$BASE_BRANCH'? (y/N): " APPROVAL
if [[ "$APPROVAL" =~ ^[Yy]$ ]]; then
    # Verify working tree cleanliness
    DIRTY_TRACKED="$(git status --porcelain | grep -v '^\?\?' || true)"
    if [ -n "$DIRTY_TRACKED" ]; then
        echo "[ERROR] Main workspace has uncommitted tracked changes:"
        echo "$DIRTY_TRACKED" | sed 's/^/  /'
        echo "Please stash or commit your local changes on '$BASE_BRANCH' before merging."
        exit 1
    fi

    echo ""
    echo "[INFO] Checking out base branch '$BASE_BRANCH'..."
    git checkout "$BASE_BRANCH"

    echo "[INFO] Merging branch '$BRANCH_NAME' into '$BASE_BRANCH' (fast-forward)..."
    if git merge --ff-only "$BRANCH_NAME"; then
        echo "[SUCCESS] Fast-forward merge completed."
    else
        echo "[INFO] Fast-forward not possible. Attempting standard merge..."
        if ! git merge "$BRANCH_NAME" -m "Merge branch '$BRANCH_NAME' into $BASE_BRANCH"; then
            echo "[ERROR] Merge hit conflicts. Aborting merge to restore clean state..."
            git merge --abort 2>/dev/null || true
            echo "        Base branch restored to clean state. Worktree preserved for manual resolution."
            exit 1
        fi
    fi

    echo "[SUCCESS] Successfully merged '$BRANCH_NAME' into '$BASE_BRANCH'!"

    # Clean up worktree and branch
    echo ""
    echo "[INFO] Cleaning up worktree and temporary branch..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    bash "$SCRIPT_DIR/cleanup-worktree.sh" "$WORKTREE_NAME" "$BRANCH_NAME"
    exit 0
else
    echo ""
    echo "[INFO] Merge declined by user."
    read -r -p "Keep worktree '$WORKTREE_NAME' for manual inspection? (Y/n): " KEEP_CHOICE
    if [[ "$KEEP_CHOICE" =~ ^[Nn] ]]; then
        echo "[INFO] Cleaning up worktree and temporary branch upon user request..."
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        bash "$SCRIPT_DIR/cleanup-worktree.sh" "$WORKTREE_NAME" "$BRANCH_NAME"
    else
        echo "[INFO] Worktree preserved at .worktrees/$WORKTREE_NAME on branch '$BRANCH_NAME'."
    fi
    exit 1
fi
