#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME="${1:-agent-worktree1}"
BRANCH_NAME="${2:-agent-branch1}"
BASE_BRANCH="${3:-}"
FORCE_FLAG="${4:-}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "[ERROR] Not inside a Git repository."
    exit 1
fi

cd "$REPO_ROOT"

# Prune stale worktrees upfront
git worktree prune --expire now 2>/dev/null || true

# Enable relative paths for cross-OS portability
git config worktree.useRelativePaths true 2>/dev/null || true

if [ -z "$BASE_BRANCH" ]; then
    BASE_BRANCH="$(git branch --show-current 2>/dev/null)"
    [ -z "$BASE_BRANCH" ] && BASE_BRANCH="HEAD"
fi

echo "=========================================================="
echo "   Creating Git Worktree: $WORKTREE_NAME"
echo "=========================================================="
echo "Repository Root : $REPO_ROOT"
echo "Base Branch     : $BASE_BRANCH"
echo "New Branch      : $BRANCH_NAME"
echo "Worktree Name   : $WORKTREE_NAME"

mkdir -p "$REPO_ROOT/.worktrees"
WORKTREE_PATH="$REPO_ROOT/.worktrees/$WORKTREE_NAME"

# Check if worktree directory exists or is registered in git worktree list
if [ -d "$WORKTREE_PATH" ] || git worktree list | grep -q -F "$WORKTREE_PATH"; then
    SHOULD_REMOVE=false
    if [ "$FORCE_FLAG" = "-Force" ] || [ "$FORCE_FLAG" = "--force" ]; then
        SHOULD_REMOVE=true
    else
        echo ""
        read -r -p "[WARNING] Worktree '$WORKTREE_NAME' already exists. Remove and recreate? (y/N): " RESP
        if [[ "$RESP" =~ ^[Yy]$ ]]; then
            SHOULD_REMOVE=true
        else
            echo "[INFO] Worktree removal declined. Creation cancelled."
            exit 1
        fi
    fi

    if [ "$SHOULD_REMOVE" = true ]; then
        echo "[INFO] Removing existing worktree at $WORKTREE_PATH..."
        git worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
        rm -rf "$WORKTREE_PATH"
        git worktree prune --expire now 2>/dev/null || true
    fi
fi

# Check if branch exists
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    SHOULD_DELETE_BRANCH=false
    if [ "$FORCE_FLAG" = "-Force" ] || [ "$FORCE_FLAG" = "--force" ]; then
        SHOULD_DELETE_BRANCH=true
    else
        echo ""
        read -r -p "[WARNING] Branch '$BRANCH_NAME' already exists. Delete and recreate fresh from '$BASE_BRANCH'? (y/N): " RESP_B
        if [[ "$RESP_B" =~ ^[Yy]$ ]]; then
            SHOULD_DELETE_BRANCH=true
        else
            echo "[INFO] Preserving existing branch '$BRANCH_NAME'. Attaching worktree..."
        fi
    fi

    if [ "$SHOULD_DELETE_BRANCH" = true ]; then
        echo "[INFO] Deleting existing branch '$BRANCH_NAME'..."
        git branch -D "$BRANCH_NAME" 2>/dev/null || true
        git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "$BASE_BRANCH"
    else
        git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
    fi
else
    echo "[INFO] Creating worktree with new branch '$BRANCH_NAME' from '$BASE_BRANCH'..."
    git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "$BASE_BRANCH"
fi

echo ""
echo "[SUCCESS] Worktree ready!"
echo "Location: $WORKTREE_PATH"
echo "Branch  : $BRANCH_NAME"
