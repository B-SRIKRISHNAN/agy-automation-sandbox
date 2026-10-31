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
    [string]$TargetRepo = "",
    [string]$InstructionsFile = "",
    [switch]$Build,
    [switch]$Interactive
)

$ErrorActionPreference = "Stop"

# 1. Determine Toolkit Root (where scripts/ and docker-compose.sandbox.yml live)
$ToolkitRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:TOOLKIT_DIR = $ToolkitRoot

# 2. Determine Target Project Repository (where user's project code lives)
if (-not $TargetRepo) {
    try {
        $targetGit = (git rev-parse --show-toplevel 2>$null)
        $TargetRepo = if ($targetGit) { $targetGit.Trim() } else { (Get-Location).Path }
    } catch {
        $TargetRepo = (Get-Location).Path
    }
}
$env:TARGET_REPO = $TargetRepo

# Dynamically derive repository, container, and image names from target project
$RepoName = (Split-Path $TargetRepo -Leaf).ToLower() -replace '[^a-z0-9_-]', '-'
$env:SANDBOX_CONTAINER = "$RepoName-sandbox"
$env:SANDBOX_IMAGE = "$RepoName-sandbox:latest"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Container Sandbox Runner                               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Toolkit Root      : $ToolkitRoot" -ForegroundColor Gray
Write-Host "Target Repository : $TargetRepo" -ForegroundColor Gray
Write-Host "Container Name    : $env:SANDBOX_CONTAINER" -ForegroundColor Gray
Write-Host "Image Name        : $env:SANDBOX_IMAGE" -ForegroundColor Gray

# 3. Detect Container Engine (honoring CONTAINER_ENGINE environment variable if set)
$ContainerEngine = ""
$IsPodmanCompose = $false
$forcedEngine = $env:CONTAINER_ENGINE

if ($forcedEngine -eq "docker" -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    $ContainerEngine = "docker"
    Write-Host "[INFO] Using requested container engine: Docker" -ForegroundColor Green
} elseif ($forcedEngine -eq "podman" -and (Get-Command podman -ErrorAction SilentlyContinue)) {
    $ContainerEngine = "podman"
    if (Get-Command podman-compose -ErrorAction SilentlyContinue) {
        $IsPodmanCompose = $true
    }
    Write-Host "[INFO] Using requested container engine: Podman" -ForegroundColor Green
} elseif (Get-Command podman -ErrorAction SilentlyContinue) {
    $ContainerEngine = "podman"
    if (Get-Command podman-compose -ErrorAction SilentlyContinue) {
        $IsPodmanCompose = $true
    }
    Write-Host "[INFO] Detected container engine: Podman" -ForegroundColor Green
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $ContainerEngine = "docker"
    Write-Host "[INFO] Detected container engine: Docker" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Neither Podman nor Docker is installed or in your PATH." -ForegroundColor Red
    Write-Host "Please install Podman or Docker to run the sandbox." -ForegroundColor Yellow
    exit 1
}

# 4. Check and pre-create host Gemini credentials folder
$GeminiPath = Join-Path $env:USERPROFILE ".gemini"
if (-not (Test-Path $GeminiPath)) {
    Write-Host "[INFO] Creating host credentials directory at: $GeminiPath" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $GeminiPath -Force | Out-Null
} else {
    Write-Host "[OK] Found host Antigravity credentials: $GeminiPath" -ForegroundColor Green
}
$env:GEMINI_PATH = ($GeminiPath -replace '\\', '/')

# 5. Check .gitconfig.sandbox in Toolkit Root (centralized so target repo stays clean)
$GitConfigSandbox = Join-Path $ToolkitRoot ".gitconfig.sandbox"
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

[worktree]
    useRelativePaths = true
"@ | Out-File -FilePath $GitConfigSandbox -Encoding utf8
}
Write-Host "[OK] Using Git sandbox configuration: $GitConfigSandbox" -ForegroundColor Green

# 6. Optional Rebuild
$ErrorActionPreference = "Continue"
$DockerComposeFile = Join-Path $ToolkitRoot "docker-compose.sandbox.yml"

function Invoke-SandboxCompose {
    param([string[]]$ComposeArgs)
    if ($IsPodmanCompose) {
        & podman-compose -f $DockerComposeFile $ComposeArgs
    } elseif ($ContainerEngine -eq "podman") {
        & podman compose -f $DockerComposeFile $ComposeArgs
    } else {
        & docker compose -f $DockerComposeFile --project-directory $ToolkitRoot $ComposeArgs
    }
}

$imageExists = (& $ContainerEngine images -q $env:SANDBOX_IMAGE 2>$null)
if ($Build -or -not $imageExists) {
    if (-not $imageExists -and -not $Build) {
        Write-Host "`n[INFO] Sandbox image ($env:SANDBOX_IMAGE) not found. Building for first-time use..." -ForegroundColor Cyan
    } else {
        Write-Host "`n[INFO] Building sandbox image ($env:SANDBOX_IMAGE)..." -ForegroundColor Cyan
    }
    Invoke-SandboxCompose @("build", "sandbox")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Container build failed with exit code $LASTEXITCODE." -ForegroundColor Red
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

# 7. Clean up any existing container with same dynamic name if present
$existingContainer = (& $ContainerEngine ps -a -q --filter "name=^/${env:SANDBOX_CONTAINER}$")
if ($existingContainer) {
    & $ContainerEngine rm -f $env:SANDBOX_CONTAINER | Out-Null
}

# 8. Run container in automated or interactive mode
$ErrorActionPreference = "Continue"

if ($WorktreeName) {
    $worktreeContainerPath = "/workspace/.worktrees/$WorktreeName"
    if ($Interactive) {
        Write-Host "`n[INFO] Starting interactive permissionless sandbox session in: $worktreeContainerPath" -ForegroundColor Cyan
    } else {
        Write-Host "`n[INFO] Starting automated agent scoped to: $worktreeContainerPath" -ForegroundColor Cyan
    }
    $issueArg = if ($IssueFile) { $IssueFile.Replace("\", "/") } else { "" }
    
    # Auto-detect instructions file if not explicitly supplied
    if (-not $InstructionsFile -and $TargetRepo) {
        $foundInstr = Get-ChildItem -Path $TargetRepo -Depth 0 -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -like "agent_instructions.md" -or $_.Name -like "AGENT_INSTRUCTIONS.MD" -or $_.Name -like "AGENT_INSTRUCTIONS.md"
        } | Select-Object -First 1
        if ($foundInstr) {
            $InstructionsFile = $foundInstr.Name
        }
    }

    $runnerArgs = @("run", "--rm", "-w", $worktreeContainerPath, "sandbox", "bash", "/runner/container-agent-runner.sh", "$WorktreeName", "$issueArg")
    if ($InstructionsFile) {
        $instructionsArg = $InstructionsFile.Replace("\", "/")
        $runnerArgs += "$instructionsArg"
    }
    if ($Interactive) {
        $runnerArgs += "--interactive"
    }

    # Run container executing runner from mounted /runner/
    Invoke-SandboxCompose $runnerArgs
    $exitCode = $LASTEXITCODE

    # Post-run: repair worktree on host
    $worktreeHostDir = Join-Path (Join-Path $TargetRepo ".worktrees") $WorktreeName
    if (Test-Path $worktreeHostDir) {
        & {
            $ErrorActionPreference = "SilentlyContinue"
            git -C $TargetRepo worktree repair $worktreeHostDir 2>&1 | Out-Null
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
    Invoke-SandboxCompose @("run", "--rm", "sandbox", "bash")
    exit $LASTEXITCODE
}
