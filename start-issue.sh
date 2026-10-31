#!/usr/bin/env bash
set -eo pipefail

ISSUE_NUMBER=""
SESSION_NAME=""
BUILD_FLAG=false
INTERACTIVE_FLAG=false
DRY_RUN_FLAG=false
CONTAINER_ENGINE="auto"

# Parse arguments & flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build|-Build|-b)
            BUILD_FLAG=true
            shift
            ;;
        --interactive|-Interactive|-i)
            INTERACTIVE_FLAG=true
            shift
            ;;
        --dry-run|-DryRun|-n)
            DRY_RUN_FLAG=true
            shift
            ;;
        --engine|-ContainerEngine|-e)
            CONTAINER_ENGINE="$2"
            shift 2
            ;;
        --engine=*|-ContainerEngine=*)
            CONTAINER_ENGINE="${1#*=}"
            shift
            ;;
        --session=*|-Session=*)
            SESSION_NAME="${1#*=}"
            shift
            ;;
        --session|-Session|-s)
            SESSION_NAME="$2"
            shift 2
            ;;
        *)
            if [ -z "$ISSUE_NUMBER" ] && [ -z "$SESSION_NAME" ]; then
                if [[ "$1" =~ ^[0-9]+$ ]]; then
                    ISSUE_NUMBER="$1"
                elif [[ "$1" =~ ^#[0-9]+$ ]]; then
                    ISSUE_NUMBER="${1#\#}"
                else
                    SESSION_NAME="$1"
                fi
            fi
            shift
            ;;
    esac
done


if [ "$CONTAINER_ENGINE" != "auto" ]; then
    export CONTAINER_ENGINE
fi

# 1. Determine Toolkit Root (where scripts/ and docker-compose.sandbox.yml live)
SCRIPT_PARENT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_PARENT/scripts" ]; then
    TOOLKIT_DIR="$SCRIPT_PARENT"
elif [ -d "$SCRIPT_PARENT/../scripts" ]; then
    TOOLKIT_DIR="$(cd "$SCRIPT_PARENT/.." && pwd)"
else
    TOOLKIT_DIR="$SCRIPT_PARENT"
fi
SCRIPTS_DIR="$TOOLKIT_DIR/scripts"

# 2. Determine Target Project Repository (where user's project code lives)
TARGET_REPO="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$TARGET_REPO" ]; then
    echo "[ERROR] Current working directory is not inside a Git repository."
    exit 1
fi
cd "$TARGET_REPO"

# Ensure target repo locally ignores .worktrees/ without polluting tracked .gitignore
GIT_EXCLUDE="$TARGET_REPO/.git/info/exclude"
if [ -f "$GIT_EXCLUDE" ]; then
    if ! grep -q "^\.worktrees" "$GIT_EXCLUDE"; then
        echo -e "\n.worktrees/\nISSUE_CONTEXT.md" >> "$GIT_EXCLUDE"
    fi
fi

# ==========================================================
# PRE-FLIGHT CHECKS
# ==========================================================

CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [ -z "$CURRENT_BRANCH" ]; then
    echo "[ERROR] Could not determine active Git branch. Please checkout a valid branch first."
    exit 1
fi

# Strict Check for Antigravity CLI (Option B)
if ! command -v agy >/dev/null 2>&1; then
    echo "[ERROR] Antigravity CLI (agy) is not installed or not in your PATH."
    echo "Please install agy to proceed: curl -fsSL https://antigravity.google/cli/install.sh | bash"
    exit 1
fi

# Check for Container Engine (Podman preferred, Docker fallback, or explicit override)
if [ "$CONTAINER_ENGINE" = "docker" ]; then
    if ! command -v docker >/dev/null 2>&1; then
        echo "[ERROR] Docker engine requested, but 'docker' was not found in PATH."
        exit 1
    fi
    ENGINE="Docker ($($(command -v docker) --version))"
elif [ "$CONTAINER_ENGINE" = "podman" ]; then
    if ! command -v podman >/dev/null 2>&1; then
        echo "[ERROR] Podman engine requested, but 'podman' was not found in PATH."
        exit 1
    fi
    ENGINE="Podman ($($(command -v podman) --version))"
elif command -v podman >/dev/null 2>&1; then
    ENGINE="Podman ($($(command -v podman) --version))"
elif command -v docker >/dev/null 2>&1; then
    ENGINE="Docker ($($(command -v docker) --version))"
else
    echo "[ERROR] Neither Podman nor Docker was found in your PATH."
    echo "Please install Podman (e.g. sudo apt install podman podman-compose) or Docker to run the sandbox."
    exit 1
fi

# Verify all required child bash scripts
REQUIRED_SCRIPTS=(
    "fetch-issue.sh"
    "create-worktree.sh"
    "run-sandbox.sh"
    "review-merge.sh"
    "cleanup-worktree.sh"
    "push-changes.sh"
)
for script in "${REQUIRED_SCRIPTS[@]}"; do
    script_path="$SCRIPTS_DIR/$script"
    if [ ! -f "$script_path" ]; then
        echo "[ERROR] Missing required script in toolkit: $script_path"
        exit 1
    fi
    chmod +x "$script_path"
done

# Prompt for Session Name or Issue Number if not provided
if [ -z "$ISSUE_NUMBER" ] && [ -z "$SESSION_NAME" ]; then
    echo "=========================================================="
    echo "   Antigravity Autonomous Sandbox Coordinator            "
    echo "=========================================================="
    echo "Base Branch      : $CURRENT_BRANCH"
    echo "Container Engine : $ENGINE"
    echo ""
    read -r -p "Enter Session Name or GitHub Issue # (e.g. 'refactor-auth' or '42'): " TARGET_INPUT
    TARGET_INPUT="$(echo "$TARGET_INPUT" | xargs)"
    if [ -z "$TARGET_INPUT" ]; then
        echo "[ERROR] No session name or issue number entered."
        exit 1
    fi
    CLEANED_TARGET="${TARGET_INPUT#\#}"
    if [[ "$CLEANED_TARGET" =~ ^[0-9]+$ ]] && [ "$CLEANED_TARGET" -gt 0 ]; then
        ISSUE_NUMBER="$CLEANED_TARGET"
    else
        SESSION_NAME="$TARGET_INPUT"
    fi
fi

if [ -n "$SESSION_NAME" ]; then
    IS_SESSION=true
    SESSION_SLUG="$(echo "$SESSION_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g' | sed 's/^-*//;s/-*$//')"
    [ -z "$SESSION_SLUG" ] && SESSION_SLUG="session"
    WORKTREE_NAME="worktree-$SESSION_SLUG"
    BRANCH_NAME="session/$SESSION_SLUG"
    INTERACTIVE_SANDBOX=true
else
    IS_SESSION=false
    SESSION_SLUG=""
    WORKTREE_NAME="worktree-issue-$ISSUE_NUMBER"
    BRANCH_NAME="issue-$ISSUE_NUMBER"
    INTERACTIVE_SANDBOX="$INTERACTIVE_FLAG"
fi

WORKTREE_PATH="$TARGET_REPO/.worktrees/$WORKTREE_NAME"

# Check for repository agent instructions (AGENT_INSTRUCTIONS.md, case-insensitive)
AGENT_INSTRUCTIONS_FILE=""
AGENT_INSTRUCTIONS_NAME=""
for name in "AGENT_INSTRUCTIONS.md" "AGENT_INSTRUCTIONS.MD" "agent_instructions.md"; do
    if [ -f "$TARGET_REPO/$name" ]; then
        AGENT_INSTRUCTIONS_FILE="$TARGET_REPO/$name"
        AGENT_INSTRUCTIONS_NAME="$name"
        break
    fi
done
if [ -z "$AGENT_INSTRUCTIONS_FILE" ]; then
    FOUND_INSTR="$(find "$TARGET_REPO" -maxdepth 1 -iname "agent_instructions.md" -type f 2>/dev/null | head -n 1)"
    if [ -n "$FOUND_INSTR" ] && [ -f "$FOUND_INSTR" ]; then
        AGENT_INSTRUCTIONS_FILE="$FOUND_INSTR"
        AGENT_INSTRUCTIONS_NAME="$(basename "$FOUND_INSTR")"
    fi
fi

echo ""
if [ "$IS_SESSION" = true ]; then
    echo "[START] Starting permissionless sandbox session '$SESSION_SLUG'..."
else
    echo "[START] Starting issue lifecycle for Issue #$ISSUE_NUMBER..."
fi
echo "Target Project   : $TARGET_REPO"
echo "Base Branch      : $CURRENT_BRANCH"
echo "Worktree Name    : $WORKTREE_NAME"
echo "Branch Name      : $BRANCH_NAME"
echo "Agent Instr.     : ${AGENT_INSTRUCTIONS_NAME:-None (standard workflow)}"
echo "Container Engine : $ENGINE"
echo "Sandbox Mode     : $(if [ "$INTERACTIVE_SANDBOX" = true ]; then echo 'Interactive Antigravity (permissionless)'; else echo 'Automated Antigravity agent runner'; fi)"

# ==========================================================
# STEP 1: Fetch issue details or initialize session context
# ==========================================================
echo ""
if [ "$IS_SESSION" = true ]; then
    echo ">>> [STEP 1/5] Initializing local session context..."
    TMP_CONTEXT_FILE="/tmp/session_${SESSION_SLUG}_context.md"
    cat <<EOF > "$TMP_CONTEXT_FILE"
# Session: $SESSION_SLUG
- **Base Branch**: $CURRENT_BRANCH
- **Branch**: $BRANCH_NAME
- **Mode**: Interactive Permissionless Sandbox

## Session Overview
Autonomous interactive development session scoped to worktree \`$WORKTREE_NAME\`.
Execute tasks, queries, code modifications, and tests inside this protected container sandbox.
EOF
    echo "[OK] Local session '$SESSION_SLUG' initialized (bypassing GitHub issues)."
else
    echo ">>> [STEP 1/5] Fetching issue details from GitHub..."
    TMP_CONTEXT_FILE="/tmp/issue_${ISSUE_NUMBER}_context.md"
    if ! bash "$SCRIPTS_DIR/fetch-issue.sh" "$ISSUE_NUMBER" "$TMP_CONTEXT_FILE"; then
        echo "[INFO] Process aborted or issue fetch failed."
        rm -f "$TMP_CONTEXT_FILE"
        exit 0
    fi
fi

# Dry Run intercept
if [ "$DRY_RUN_FLAG" = true ]; then
    echo ""
    TARGET_LABEL="$(if [ "$IS_SESSION" = true ]; then echo "Session '$SESSION_SLUG'"; else echo "Issue #$ISSUE_NUMBER"; fi)"
    echo "[DRY RUN] $TARGET_LABEL configured successfully. Planned execution:"
    echo "  - Target Repo     : $TARGET_REPO"
    echo "  - Base Branch     : $CURRENT_BRANCH"
    echo "  - Worktree Branch : $BRANCH_NAME"
    echo "  - Worktree Path   : $WORKTREE_PATH"
    echo "  - Agent Instr.    : ${AGENT_INSTRUCTIONS_NAME:-None (standard agent workflow)}"
    echo "  - Container Engine: ${CONTAINER_ENGINE:-auto-detect ($ENGINE)}"
    echo "  - Sandbox Mode    : $(if [ "$INTERACTIVE_SANDBOX" = true ]; then echo 'Interactive permissionless Antigravity session'; else echo 'Automated Antigravity agent runner'; fi)"
    echo "  - Build Sandbox   : $BUILD_FLAG"
    echo "[DRY RUN] Simulation complete. No worktree created, no container started, no commits made."
    rm -f "$TMP_CONTEXT_FILE"
    exit 0
fi

# ==========================================================
# STEP 2: Create isolated Git Worktree and branch
# ==========================================================
echo ""
echo ">>> [STEP 2/5] Creating isolated Git Worktree..."
if ! bash "$SCRIPTS_DIR/create-worktree.sh" "$WORKTREE_NAME" "$BRANCH_NAME" "$CURRENT_BRANCH"; then
    echo "[ERROR] Failed to create git worktree."
    rm -f "$TMP_CONTEXT_FILE"
    exit 1
fi

# Inject issue or session context into worktree
ISSUE_CONTEXT_DEST="$WORKTREE_PATH/ISSUE_CONTEXT.md"
if [ -f "$TMP_CONTEXT_FILE" ]; then
    cp "$TMP_CONTEXT_FILE" "$ISSUE_CONTEXT_DEST"
    rm -f "$TMP_CONTEXT_FILE"
    echo "[OK] Injected context into worktree: $ISSUE_CONTEXT_DEST"
fi

if [ -n "$AGENT_INSTRUCTIONS_NAME" ]; then
    echo "[OK] Active repository agent instructions: $AGENT_INSTRUCTIONS_NAME"
fi

# ==========================================================
# STEP 3: Run Sandbox with agy
# ==========================================================
echo ""
echo ">>> [STEP 3/5] Launching Sandbox & running Antigravity (agy)..."
SANDBOX_ARGS=("-WorktreeName" "$WORKTREE_NAME" "-IssueFile" ".worktrees/$WORKTREE_NAME/ISSUE_CONTEXT.md" "-TargetRepo" "$TARGET_REPO")
if [ -n "$AGENT_INSTRUCTIONS_NAME" ]; then
    SANDBOX_ARGS+=("-InstructionsFile" "$AGENT_INSTRUCTIONS_NAME")
fi
if [ "$BUILD_FLAG" = true ]; then
    SANDBOX_ARGS+=("-Build")
fi
if [ "$INTERACTIVE_SANDBOX" = true ]; then
    SANDBOX_ARGS+=("-Interactive")
fi


if ! bash "$SCRIPTS_DIR/run-sandbox.sh" "${SANDBOX_ARGS[@]}"; then
    echo "[ERROR] Sandbox run failed."
    exit 1
fi

# Explicit worktree repair on host
if [ -d "$WORKTREE_PATH" ]; then
    git -C "$TARGET_REPO" worktree repair "$WORKTREE_PATH" >/dev/null 2>&1 || true
fi

# ==========================================================
# STEP 4: Review changes with agy, confirm, merge & cleanup
# ==========================================================
echo ""
echo ">>> [STEP 4/5] Reviewing changes and merging..."
MERGED=false
if bash "$SCRIPTS_DIR/review-merge.sh" "$WORKTREE_NAME" "$BRANCH_NAME" "$CURRENT_BRANCH"; then
    MERGED=true
fi

# ==========================================================
# STEP 5: Confirm and push to remote
# ==========================================================
if [ "$MERGED" = true ]; then
    echo ""
    echo ">>> [STEP 5/5] Push changes to remote..."
    bash "$SCRIPTS_DIR/push-changes.sh" "$CURRENT_BRANCH" "origin"
else
    echo ""
    echo "[INFO] Skipping push since changes were not merged into '$CURRENT_BRANCH'."
fi

echo ""
echo "=========================================================="
if [ "$IS_SESSION" = true ]; then
    echo "   Session '$SESSION_SLUG' Workflow Completed!            "
else
    echo "   Issue #$ISSUE_NUMBER Workflow Completed!               "
fi
echo "=========================================================="

