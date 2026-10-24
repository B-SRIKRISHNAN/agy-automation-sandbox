#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME="${1:-agent-worktree1}"
BRANCH_NAME="${2:-agent-branch1}"
FORCE_FLAG="${3:-}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "[ERROR] Not inside a Git repository."
    exit 1
fi

cd "$REPO_ROOT"

WORKTREE_PATH="$REPO_ROOT/.worktrees/$WORKTREE_NAME"

echo "=========================================================="
echo "   Cleaning up Git Worktree: $WORKTREE_NAME"
echo "=========================================================="
echo "Worktree Path : $WORKTREE_PATH"
echo "Branch Name   : $BRANCH_NAME"

# 1. Remove git worktree
if git worktree list | grep -q -F "$WORKTREE_PATH"; then
    echo ""
    echo "[1/3] Removing git worktree entry..."
    git worktree remove --force "$WORKTREE_PATH" || true
else
    echo ""
    echo "[1/3] Worktree '$WORKTREE_NAME' not actively registered in git worktree list."
fi

if [ -d "$WORKTREE_PATH" ]; then
    echo "      Cleaning up residual directory at $WORKTREE_PATH..."
    rm -rf "$WORKTREE_PATH"
fi

# 2. Prune worktrees
echo ""
echo "[2/3] Pruning git worktree metadata..."
git worktree prune --expire now
echo "      Worktree metadata pruned."

# 3. Remove the branch
echo ""
echo "[3/3] Removing branch '$BRANCH_NAME'..."
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    CURRENT_BRANCH="$(git branch --show-current 2>/dev/null)"
    if [ "$CURRENT_BRANCH" = "$BRANCH_NAME" ]; then
        echo "[WARNING] Currently on '$BRANCH_NAME' in main worktree. Cannot delete active branch."
    else
        git branch -D "$BRANCH_NAME"
        echo "      Branch '$BRANCH_NAME' deleted."
    fi
else
    echo "      Branch '$BRANCH_NAME' does not exist."
fi

echo ""
echo "[SUCCESS] Cleanup complete for '$WORKTREE_NAME' and '$BRANCH_NAME'!"
echo ""
echo "Current worktrees:"
git worktree list
