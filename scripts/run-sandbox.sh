#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME=""
ISSUE_FILE=""
BUILD=false
INTERACTIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -WorktreeName|--worktree-name)
            WORKTREE_NAME="$2"
            shift 2
            ;;
        -IssueFile|--issue-file)
            ISSUE_FILE="$2"
            shift 2
            ;;
        -Build|--build)
            BUILD=true
            shift
            ;;
        -Interactive|--interactive)
            INTERACTIVE=true
            shift
            ;;
        *)
            if [ -z "$WORKTREE_NAME" ]; then
                WORKTREE_NAME="$1"
            elif [ -z "$ISSUE_FILE" ]; then
                ISSUE_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Calculate repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Derive container and image names
REPO_NAME="$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/-/g')"
export SANDBOX_CONTAINER="${REPO_NAME}-sandbox"
export SANDBOX_IMAGE="${REPO_NAME}-sandbox:latest"

echo "=========================================================="
echo "   Container Sandbox Runner                               "
echo "=========================================================="
echo "Repository Root   : $REPO_ROOT"
echo "Container Name    : $SANDBOX_CONTAINER"
echo "Image Name        : $SANDBOX_IMAGE"

# 1. Detect Container Engine (Podman preferred, Docker fallback)
CONTAINER_ENGINE=""
COMPOSE_CMD=""

if command -v podman >/dev/null 2>&1; then
    CONTAINER_ENGINE="podman"
    if podman compose version >/dev/null 2>&1; then
        COMPOSE_CMD="podman compose"
    elif command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
    else
        COMPOSE_CMD="podman compose"
    fi
    echo "[INFO] Detected container engine: Podman ($($CONTAINER_ENGINE --version))"
elif command -v docker >/dev/null 2>&1; then
    CONTAINER_ENGINE="docker"
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    echo "[INFO] Detected container engine: Docker ($($CONTAINER_ENGINE --version))"
else
    echo "[ERROR] Neither Podman nor Docker was found in your PATH."
    echo "Please install Podman (e.g., sudo apt install podman podman-compose) or Docker to proceed."
    exit 1
fi

# 2. Check and pre-create host Gemini credentials folder
GEMINI_PATH="${HOME}/.gemini"
if [ ! -d "$GEMINI_PATH" ]; then
    echo "[INFO] Creating host credentials directory at: $GEMINI_PATH"
    mkdir -p "$GEMINI_PATH"
else
    echo "[OK] Found host Antigravity credentials: $GEMINI_PATH"
fi

# 3. Check .gitconfig.sandbox in repo root
GIT_CONFIG_SANDBOX="$REPO_ROOT/.gitconfig.sandbox"
if [ ! -f "$GIT_CONFIG_SANDBOX" ]; then
    HOST_GIT_USER="$(git config user.name 2>/dev/null || echo "$USER")"
    HOST_GIT_EMAIL="$(git config user.email 2>/dev/null || echo "${USER}@localhost")"

    echo "[INFO] Generating default .gitconfig.sandbox from host identity: $HOST_GIT_USER <$HOST_GIT_EMAIL>..."
    cat <<EOF > "$GIT_CONFIG_SANDBOX"
[user]
    name = $HOST_GIT_USER
    email = $HOST_GIT_EMAIL

[safe]
    directory = *

[core]
    autocrlf = input
    fileMode = false
    preloadindex = true
    fscache = true
    untrackedCache = true

[worktree]
    useRelativePaths = true
EOF
fi
echo "[OK] Using Git sandbox configuration: $GIT_CONFIG_SANDBOX"

# 4. Optional Rebuild
DOCKER_COMPOSE_FILE="$REPO_ROOT/docker-compose.sandbox.yml"
if [ "$BUILD" = true ]; then
    echo ""
    echo "[INFO] Building sandbox image ($SANDBOX_IMAGE)..."
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" --project-directory "$REPO_ROOT" build sandbox
fi

# Ensure executable and LF line endings on runner script
RUNNER_SCRIPT="$SCRIPT_DIR/container-agent-runner.sh"
if [ -f "$RUNNER_SCRIPT" ]; then
    chmod +x "$RUNNER_SCRIPT"
fi

# 5. Clean up existing container if present
EXISTING_CONTAINER="$($CONTAINER_ENGINE ps -a -q --filter "name=^/${SANDBOX_CONTAINER}$" 2>/dev/null || true)"
if [ -n "$EXISTING_CONTAINER" ]; then
    $CONTAINER_ENGINE rm -f "$SANDBOX_CONTAINER" >/dev/null 2>&1 || true
fi

# 6. Run container in automated or interactive mode
if [ -n "$WORKTREE_NAME" ] && [ "$INTERACTIVE" = false ]; then
    WORKTREE_CONTAINER_PATH="/workspace/.worktrees/$WORKTREE_NAME"
    echo ""
    echo "[INFO] Starting automated agent scoped to: $WORKTREE_CONTAINER_PATH"

    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" --project-directory "$REPO_ROOT" run --rm -w "$WORKTREE_CONTAINER_PATH" sandbox bash /workspace/scripts/container-agent-runner.sh "$WORKTREE_NAME" "$ISSUE_FILE"
    EXIT_CODE=$?

    # Post-run: repair worktree on host
    WORKTREE_HOST_DIR="$REPO_ROOT/.worktrees/$WORKTREE_NAME"
    if [ -d "$WORKTREE_HOST_DIR" ]; then
        git worktree repair "$WORKTREE_HOST_DIR" >/dev/null 2>&1 || true
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        echo "[ERROR] Agent container exited with error code $EXIT_CODE."
        exit $EXIT_CODE
    fi
    echo "[OK] Sandbox container run finished successfully."
else
    echo ""
    echo "----------------------------------------------------------"
    echo "Tips inside the container:"
    echo "  1. Test agy CLI:         agy --version"
    echo "  2. Start agy agent:      agy"
    echo "  3. Fix cross-OS paths:   git worktree repair"
    echo "  4. List worktrees:       git worktree list"
    echo "----------------------------------------------------------"
    echo ""
    echo "[INFO] Entering sandbox container shell (exit or Ctrl+D to leave)..."
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" --project-directory "$REPO_ROOT" run --rm sandbox bash
    exit $?
fi
