<#
.SYNOPSIS
    Launches the project Docker Sandbox environment or runs an automated agent task.

.DESCRIPTION
    Builds and starts an interactive or automated Docker container with Java 21, Maven, Node.js 22 LTS,
    Git, and the Antigravity CLI (agy) pre-installed. Mounts the repository root, host .gemini credentials,
    and sandbox .gitconfig into the container. Scopes working directory to the worktree during automated runs.

.PARAMETER WorktreeName
    Optional worktree name to automatically switch into and execute the agent task.

.PARAMETER IssueFile
    Optional path to the issue context markdown file relative to /workspace.

.PARAMETER Build
    Force a rebuild of the Docker sandbox image before launching.

.PARAMETER Interactive
    Force an interactive bash shell even if WorktreeName is provided.

.EXAMPLE
    .\scripts\run-sandbox.ps1
    .\scripts\run-sandbox.ps1 -Build
    .\scripts\run-sandbox.ps1 -WorktreeName "worktree-issue-15"
#>

param (
    [string]$WorktreeName = "",
    [string]$IssueFile = "",
    [switch]$Build,
    [switch]$Interactive
)

$ErrorActionPreference = "Stop"

# Calculate repository root (parent of scripts/)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoRootNormalized = $RepoRoot -replace '\\', '/'

# Dynamically derive repository, container, and image names
$RepoName = (Split-Path $RepoRoot -Leaf).ToLower() -replace '[^a-z0-9_-]', '-'
$env:SANDBOX_CONTAINER = "$RepoName-sandbox"
$env:SANDBOX_IMAGE = "$RepoName-sandbox:latest"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Docker Sandbox Runner                                  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Repository Root   : $RepoRoot" -ForegroundColor Gray
Write-Host "Container Name    : $env:SANDBOX_CONTAINER" -ForegroundColor Gray
Write-Host "Image Name        : $env:SANDBOX_IMAGE" -ForegroundColor Gray

# Toolchain reminder for multi-stack repos
Write-Host "`n[TIP] Sandbox includes Node.js 22, Python 3, Java 21, and Git." -ForegroundColor DarkGray
Write-Host "      If your repo requires other compilers (Go, Rust, etc.), update the Dockerfile." -ForegroundColor DarkGray

# 1. Verify Docker CLI
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker is not installed or not in your PATH." -ForegroundColor Red
    exit 1
}

# 2. Check and pre-create host Gemini credentials folder to prevent root-owned folder creation
$GeminiPath = Join-Path $env:USERPROFILE ".gemini"
if (-not (Test-Path $GeminiPath)) {
    Write-Host "[INFO] Creating host credentials directory at: $GeminiPath" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $GeminiPath -Force | Out-Null
} else {
    Write-Host "[OK] Found host Antigravity credentials: $GeminiPath" -ForegroundColor Green
}

# 3. Check .gitconfig.sandbox in repo root (dynamically inherits host Git identity)
$GitConfigSandbox = Join-Path $RepoRoot ".gitconfig.sandbox"
if (-not (Test-Path $GitConfigSandbox)) {
    $hostGitUser = (git config user.name 2>$null)
    if ($hostGitUser) { $hostGitUser = $hostGitUser.Trim() } else { $hostGitUser = $env:USERNAME }

    $hostGitEmail = (git config user.email 2>$null)
    if ($hostGitEmail) { $hostGitEmail = $hostGitEmail.Trim() } else { $hostGitEmail = "$env:USERNAME@localhost" }

    Write-Host "[INFO] Generating default .gitconfig.sandbox from host identity: $hostGitUser <$hostGitEmail>..." -ForegroundColor Cyan
    @"
[user]
    name = $hostGitUser
    email = $hostGitEmail

[safe]
    directory = *

[core]
    autocrlf = input
    fileMode = false
    preloadindex = true
    fscache = true
    untrackedCache = true
"@ | Out-File -FilePath $GitConfigSandbox -Encoding utf8
}
Write-Host "[OK] Using Git sandbox configuration: $GitConfigSandbox" -ForegroundColor Green

# 4. Optional Rebuild
# Allow Docker's normal informational stderr output without triggering NativeCommandError
$ErrorActionPreference = "Continue"

$DockerComposeFile = Join-Path $RepoRoot "docker-compose.sandbox.yml"
if ($Build) {
    Write-Host "`n[INFO] Building Docker sandbox image ($env:SANDBOX_IMAGE)..." -ForegroundColor Cyan
    docker compose -f $DockerComposeFile --project-directory $RepoRoot build sandbox
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Docker build failed with exit code $LASTEXITCODE." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# Ensure LF line endings on container runner script
$RunnerScript = Join-Path $PSScriptRoot "container-agent-runner.sh"
if (Test-Path $RunnerScript) {
    $scriptContent = [System.IO.File]::ReadAllText($RunnerScript)
    $scriptContent = $scriptContent -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($RunnerScript, $scriptContent, (New-Object System.Text.UTF8Encoding($false)))
}

# 5. Clean up any existing container with same dynamic name if present
$existingContainer = (docker ps -a -q --filter "name=^/${env:SANDBOX_CONTAINER}$")
if ($existingContainer) {
    docker rm -f $env:SANDBOX_CONTAINER | Out-Null
}

# 6. Run container in automated or interactive mode
# Allow Docker's normal informational stderr output without triggering NativeCommandError
$ErrorActionPreference = "Continue"

if ($WorktreeName -and -not $Interactive) {
    $worktreeContainerPath = "/workspace/.worktrees/$WorktreeName"
    Write-Host "`n[INFO] Starting automated agent scoped to: $worktreeContainerPath" -ForegroundColor Cyan
    $issueArg = if ($IssueFile) { $IssueFile.Replace("\", "/") } else { "" }
    
    # Scope working directory explicitly to the worktree via -w
    docker compose -f $DockerComposeFile --project-directory $RepoRoot run --rm -w $worktreeContainerPath sandbox bash /workspace/scripts/container-agent-runner.sh "$WorktreeName" "$issueArg"
    $exitCode = $LASTEXITCODE

    # Post-run: repair worktree on host explicitly
    Set-Location $RepoRoot
    $worktreeHostDir = Join-Path (Join-Path $RepoRoot ".worktrees") $WorktreeName
    if (Test-Path $worktreeHostDir) {
        & {
            $ErrorActionPreference = "SilentlyContinue"
            git worktree repair $worktreeHostDir 2>&1 | Out-Null
        }
    }

    if ($exitCode -ne 0) {
        Write-Host "[ERROR] Agent container exited with error code $exitCode." -ForegroundColor Red
        exit $exitCode
    }
    Write-Host "[OK] Sandbox container run finished successfully." -ForegroundColor Green
}
 else {
    Write-Host "`n----------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "Tips inside the container:" -ForegroundColor Yellow
    Write-Host "  1. Test agy CLI:         agy --version" -ForegroundColor Gray
    Write-Host "  2. Start agy agent:      agy" -ForegroundColor Gray
    Write-Host "  3. Fix cross-OS paths:   git worktree repair" -ForegroundColor Gray
    Write-Host "  4. List worktrees:       git worktree list" -ForegroundColor Gray
    Write-Host "----------------------------------------------------------`n" -ForegroundColor DarkGray

    Write-Host "[INFO] Entering sandbox container shell (exit or Ctrl+D to leave)..." -ForegroundColor Cyan
    docker compose -f $DockerComposeFile --project-directory $RepoRoot run --rm sandbox bash
    exit $LASTEXITCODE
}
