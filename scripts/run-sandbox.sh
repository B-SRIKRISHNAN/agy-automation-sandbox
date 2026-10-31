#!/usr/bin/env bash
set -eo pipefail

WORKTREE_NAME=""
ISSUE_FILE=""
TARGET_REPO=""
INSTRUCTIONS_FILE=""
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
        -TargetRepo|--target-repo)
            TARGET_REPO="$2"
            shift 2
            ;;
        -InstructionsFile|--instructions-file)
            INSTRUCTIONS_FILE="$2"
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

# 1. Determine Toolkit Root (where scripts/ and docker-compose.sandbox.yml live)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export TOOLKIT_DIR

# 2. Determine Target Project Repository (where user's project code lives)
if [ -z "$TARGET_REPO" ]; then
    TARGET_REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
export TARGET_REPO

# Derive container and image names from target project
REPO_NAME="$(basename "$TARGET_REPO" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/-/g')"
export SANDBOX_CONTAINER="${REPO_NAME}-sandbox"
export SANDBOX_IMAGE="${REPO_NAME}-sandbox:latest"

echo "=========================================================="
echo "   Container Sandbox Runner                               "
echo "=========================================================="
echo "Toolkit Root      : $TOOLKIT_DIR"
echo "Target Repository : $TARGET_REPO"
echo "Container Name    : $SANDBOX_CONTAINER"
echo "Image Name        : $SANDBOX_IMAGE"

# 3. Detect Container Engine (Podman preferred, Docker fallback, or explicit override)
FORCED_ENGINE="${CONTAINER_ENGINE:-auto}"
CONTAINER_ENGINE=""
COMPOSE_CMD=""

if [ "$FORCED_ENGINE" = "docker" ] && command -v docker >/dev/null 2>&1; then
    CONTAINER_ENGINE="docker"
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    echo "[INFO] Using requested container engine: Docker ($($CONTAINER_ENGINE --version))"
elif [ "$FORCED_ENGINE" = "podman" ] && command -v podman >/dev/null 2>&1; then
    CONTAINER_ENGINE="podman"
    if podman compose version >/dev/null 2>&1; then
        COMPOSE_CMD="podman compose"
    elif command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
    else
        COMPOSE_CMD="podman compose"
    fi
    echo "[INFO] Using requested container engine: Podman ($($CONTAINER_ENGINE --version))"
elif command -v podman >/dev/null 2>&1; then
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

# 4. Check and pre-create host Gemini credentials folder
GEMINI_PATH="${HOME}/.gemini"
if [ ! -d "$GEMINI_PATH" ]; then
    echo "[INFO] Creating host credentials directory at: $GEMINI_PATH"
    mkdir -p "$GEMINI_PATH"
else
    echo "[OK] Found host Antigravity credentials: $GEMINI_PATH"
fi
export GEMINI_PATH

# 5. Check .gitconfig.sandbox in Toolkit Root (centralized so target repo stays clean)
GIT_CONFIG_SANDBOX="$TOOLKIT_DIR/.gitconfig.sandbox"
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

# 6. Optional Rebuild
DOCKER_COMPOSE_FILE="$TOOLKIT_DIR/docker-compose.sandbox.yml"

run_compose() {
    if [ "$CONTAINER_ENGINE" = "podman" ]; then
        $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" "$@"
    else
        $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" --project-directory "$TOOLKIT_DIR" "$@"
    fi
}

IMAGE_EXISTS="$($CONTAINER_ENGINE images -q "$SANDBOX_IMAGE" 2>/dev/null || true)"
if [ "$BUILD" = true ] || [ -z "$IMAGE_EXISTS" ]; then
    echo ""
    if [ -z "$IMAGE_EXISTS" ] && [ "$BUILD" = false ]; then
        echo "[INFO] Sandbox image ($SANDBOX_IMAGE) not found. Building for first-time use..."
    else
        echo "[INFO] Building sandbox image ($SANDBOX_IMAGE)..."
    fi
    run_compose build sandbox
fi

# Ensure executable on runner script
RUNNER_SCRIPT="$SCRIPT_DIR/container-agent-runner.sh"
if [ -f "$RUNNER_SCRIPT" ]; then
    chmod +x "$RUNNER_SCRIPT"
fi

# 7. Clean up existing container if present
EXISTING_CONTAINER="$($CONTAINER_ENGINE ps -a -q --filter "name=^/${SANDBOX_CONTAINER}$" 2>/dev/null || true)"
if [ -n "$EXISTING_CONTAINER" ]; then
    $CONTAINER_ENGINE rm -f "$SANDBOX_CONTAINER" >/dev/null 2>&1 || true
fi

# 8. Run container in automated or interactive mode
if [ -n "$WORKTREE_NAME" ]; then
    WORKTREE_CONTAINER_PATH="/workspace/.worktrees/$WORKTREE_NAME"
    echo ""
    if [ "$INTERACTIVE" = true ]; then
        echo "[INFO] Starting interactive permissionless sandbox session in: $WORKTREE_CONTAINER_PATH"
    else
        echo "[INFO] Starting automated agent scoped to: $WORKTREE_CONTAINER_PATH"
    fi
    issue_arg="${ISSUE_FILE//\\//}"

    # Auto-detect instructions file if not explicitly supplied
    if [ -z "$INSTRUCTIONS_FILE" ] && [ -n "$TARGET_REPO" ]; then
        for candidate in "AGENT_INSTRUCTIONS.md" "AGENT_INSTRUCTIONS.MD" "agent_instructions.md"; do
            if [ -f "$TARGET_REPO/$candidate" ]; then
                INSTRUCTIONS_FILE="$candidate"
                break
            fi
        done
        if [ -z "$INSTRUCTIONS_FILE" ]; then
            FOUND_INSTR="$(find "$TARGET_REPO" -maxdepth 1 -iname "agent_instructions.md" -type f 2>/dev/null | head -n 1)"
            if [ -n "$FOUND_INSTR" ] && [ -f "$FOUND_INSTR" ]; then
                INSTRUCTIONS_FILE="$(basename "$FOUND_INSTR")"
            fi
        fi
    fi

    RUNNER_ARGS=("$WORKTREE_NAME" "$issue_arg")
    if [ -n "$INSTRUCTIONS_FILE" ]; then
        RUNNER_ARGS+=("${INSTRUCTIONS_FILE//\\//}")
    fi
    if [ "$INTERACTIVE" = true ]; then
        RUNNER_ARGS+=("--interactive")
    fi

    # Run container executing runner from mounted /runner/
    run_compose run --rm -w "$WORKTREE_CONTAINER_PATH" sandbox bash /runner/container-agent-runner.sh "${RUNNER_ARGS[@]}"
    EXIT_CODE=$?

    # Post-run: repair worktree on host
    WORKTREE_HOST_DIR="$TARGET_REPO/.worktrees/$WORKTREE_NAME"
    if [ -d "$WORKTREE_HOST_DIR" ]; then
        git -C "$TARGET_REPO" worktree repair "$WORKTREE_HOST_DIR" >/dev/null 2>&1 || true
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
    run_compose run --rm sandbox bash
    exit $?
fi
