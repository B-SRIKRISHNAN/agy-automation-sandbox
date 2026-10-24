#!/usr/bin/env bash
set -eo pipefail

BRANCH_NAME="${1:-}"
REMOTE="${2:-origin}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "[ERROR] Not inside a Git repository."
    exit 1
fi

cd "$REPO_ROOT"

if [ -z "$BRANCH_NAME" ]; then
    BRANCH_NAME="$(git branch --show-current 2>/dev/null || true)"
    if [ -z "$BRANCH_NAME" ]; then
        echo "[ERROR] Could not determine active branch to push. Please specify branch name as first argument."
        exit 1
    fi
fi

echo "=========================================================="
echo "   Push Changes to Remote: $REMOTE/$BRANCH_NAME"
echo "=========================================================="

# 1. Fetch remote branch state before comparing
echo "[INFO] Fetching latest state from $REMOTE/$BRANCH_NAME..."
git fetch "$REMOTE" "$BRANCH_NAME" >/dev/null 2>&1 || true

# 2. Check if branch exists on remote
REMOTE_EXISTS="$(git ls-remote --heads "$REMOTE" "$BRANCH_NAME" 2>/dev/null || true)"
if [ -z "$REMOTE_EXISTS" ]; then
    echo "[INFO] Branch '$BRANCH_NAME' does not exist yet on '$REMOTE' (brand new remote branch)."
    UNPUSHED_COMMITS="$(git log "$BRANCH_NAME" -n 5 --oneline 2>/dev/null || true)"
else
    UNPUSHED_COMMITS="$(git log "$REMOTE/$BRANCH_NAME..$BRANCH_NAME" --oneline 2>/dev/null || true)"
fi

if [ -z "$UNPUSHED_COMMITS" ]; then
    echo "[INFO] Local branch '$BRANCH_NAME' is already in sync with '$REMOTE/$BRANCH_NAME'."
    echo "       No unpushed commits found."
    exit 0
fi

echo ""
echo "Commits to be pushed to $REMOTE/$BRANCH_NAME:"
echo "$UNPUSHED_COMMITS" | sed 's/^/  * /'

# 3. Request confirmation
echo ""
read -r -p "Do you approve pushing these changes to '$REMOTE/$BRANCH_NAME'? (y/N): " RESP
if [[ "$RESP" =~ ^[Yy]$ ]]; then
    echo ""
    echo "[INFO] Pushing changes with upstream tracking (-u)..."
    git push -u "$REMOTE" "$BRANCH_NAME"
    echo ""
    echo "[SUCCESS] Successfully pushed changes to $REMOTE/$BRANCH_NAME!"
else
    echo ""
    echo "[INFO] Push aborted by user. Your local branch '$BRANCH_NAME' was NOT pushed."
fi
