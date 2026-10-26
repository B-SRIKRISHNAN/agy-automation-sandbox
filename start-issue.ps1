<#
.SYNOPSIS
    Master coordinator script to automate GitHub issue resolution with Antigravity and Git worktrees.

.DESCRIPTION
    Orchestrates the complete lifecycle:
      1. Pre-flight verification of scripts and environment.
      2. Fetches GitHub issue details and confirms with user (scripts/fetch-issue.ps1).
      3. Creates an isolated git worktree and branch named after the issue (scripts/create-worktree.ps1).
      4. Launches the Docker sandbox with issue context, runs agy automated workflow, commits changes (scripts/run-sandbox.ps1).
      5. Compares changes against the base branch, generates an AI review with agy, asks for merge approval, merges, and cleans up the worktree (scripts/review-merge.ps1).
      6. Confirms and pushes the merged changes to the remote branch (scripts/push-changes.ps1).

.PARAMETER IssueNumber
    GitHub issue number to work on. If omitted, prompts interactively.

.PARAMETER BuildSandbox
    Force a rebuild of the Docker sandbox image before launching.

.PARAMETER InteractiveSandbox
    Launch sandbox in interactive mode instead of fully automated mode.

.PARAMETER ContainerEngine
    Specify container engine to use: 'podman', 'docker', or 'auto' (default: auto).

.PARAMETER DryRun
    Simulate pre-flight checks and issue resolution planning without modifying repository, worktrees, or launching containers.

.EXAMPLE
    .\start-issue.ps1 -IssueNumber 15
    .\start-issue.ps1 15 -BuildSandbox
    .\start-issue.ps1 15 -ContainerEngine docker -DryRun
#>

param (
    [Parameter(Position = 0)]
    [int]$IssueNumber = 0,
    [ValidateSet("auto", "podman", "docker")]
    [string]$ContainerEngine = "auto",
    [switch]$BuildSandbox,
    [switch]$InteractiveSandbox,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Determine Toolkit Root (where scripts/ and docker-compose.sandbox.yml live)
if (Test-Path (Join-Path $PSScriptRoot "scripts")) {
    $ToolkitRoot = $PSScriptRoot
} elseif (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) "scripts")) {
    $ToolkitRoot = Split-Path $PSScriptRoot -Parent
} else {
    $ToolkitRoot = $PSScriptRoot
}
$ScriptsDir = Join-Path $ToolkitRoot "scripts"

# Determine Target Project Repository (where user's project code lives)
try {
    $targetGit = (git rev-parse --show-toplevel 2>$null)
    $TargetRepo = if ($targetGit) { $targetGit.Trim() } else { "" }
} catch {
    $TargetRepo = ""
}

if (-not $TargetRepo) {
    Write-Host "[ERROR] Current working directory is not inside a Git repository." -ForegroundColor Red
    exit 1
}

Set-Location $TargetRepo

# Pre-flight check: Ensure target repo locally ignores .worktrees/ without polluting tracked .gitignore
$gitExclude = Join-Path (Join-Path $TargetRepo ".git") "info\exclude"
if (Test-Path $gitExclude) {
    $excludeContent = [System.IO.File]::ReadAllText($gitExclude)
    if ($excludeContent -notmatch "(?m)^\.worktrees/?$") {
        [System.IO.File]::AppendAllText($gitExclude, "`n.worktrees/`nISSUE_CONTEXT.md`n")
    }
}

# Pre-flight check: Verify agy CLI exists on host (strictly required)
if (-not (Get-Command agy -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Antigravity CLI (agy) is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install agy to proceed: https://antigravity.google/cli" -ForegroundColor Yellow
    exit 1
}

# Set container engine environment override if specified
if ($ContainerEngine -ne "auto") {
    $env:CONTAINER_ENGINE = $ContainerEngine
}

# Pre-flight check: Verify container engine (podman or docker)
if ($ContainerEngine -eq "docker") {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] Docker engine requested, but 'docker' was not found in PATH." -ForegroundColor Red
        exit 1
    }
} elseif ($ContainerEngine -eq "podman") {
    if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] Podman engine requested, but 'podman' was not found in PATH." -ForegroundColor Red
        exit 1
    }
} else {
    $hasPodman = [bool](Get-Command podman -ErrorAction SilentlyContinue)
    $hasDocker = [bool](Get-Command docker -ErrorAction SilentlyContinue)
    if (-not $hasPodman -and -not $hasDocker) {
        Write-Host "[ERROR] Neither Podman nor Docker was found in your PATH." -ForegroundColor Red
        Write-Host "Please install Podman or Docker Desktop to run the sandbox." -ForegroundColor Yellow
        exit 1
    }
}

# Pre-flight check: Verify all required child scripts exist
$RequiredScripts = @(
    "fetch-issue.ps1",
    "create-worktree.ps1",
    "run-sandbox.ps1",
    "review-merge.ps1",
    "cleanup-worktree.ps1",
    "push-changes.ps1"
)
foreach ($scriptName in $RequiredScripts) {
    $scriptPath = Join-Path $ScriptsDir $scriptName
    if (-not (Test-Path $scriptPath)) {
        Write-Host "[ERROR] Missing required script in toolkit: $scriptPath" -ForegroundColor Red
        exit 1
    }
}

# Verify Git repo
try {
    $showCurrent = (git branch --show-current 2>$null)
    $CurrentBranch = if ($showCurrent) { $showCurrent.Trim() } else { "" }
} catch {
    Write-Host "[ERROR] Not inside a Git repository." -ForegroundColor Red
    exit 1
}

if (-not $CurrentBranch) {
    Write-Host "[ERROR] Could not determine active Git branch. Please checkout a valid branch first." -ForegroundColor Red
    exit 1
}

# 1. Prompt for Issue Number if not provided
if ($IssueNumber -le 0) {
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "   Antigravity GitHub Issue Automation Coordinator        " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "Base Branch: $CurrentBranch" -ForegroundColor Gray
    Write-Host "`nEnter GitHub Issue Number to work on: " -NoNewline -ForegroundColor Yellow
    $inputNum = Read-Host
    if (-not [int]::TryParse($inputNum, [ref]$IssueNumber) -or $IssueNumber -le 0) {
        Write-Host "[ERROR] Invalid issue number entered." -ForegroundColor Red
        exit 1
    }
}

$WorktreeName = "worktree-issue-$IssueNumber"
$BranchName = "issue-$IssueNumber"
$WorktreesContainer = Join-Path $TargetRepo ".worktrees"
$WorktreePath = Join-Path $WorktreesContainer $WorktreeName

# Check for repository agent instructions (AGENT_INSTRUCTIONS.md, case-insensitive)
$agentInstructionsCandidate = Get-ChildItem -Path $TargetRepo -Depth 0 -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like "agent_instructions.md" -or $_.Name -like "AGENT_INSTRUCTIONS.MD" -or $_.Name -like "AGENT_INSTRUCTIONS.md"
} | Select-Object -First 1
$agentInstructionsName = if ($agentInstructionsCandidate) { $agentInstructionsCandidate.Name } else { "" }

Write-Host "`n[START] Starting issue lifecycle for Issue #$IssueNumber..." -ForegroundColor Cyan
Write-Host "Target Project: $TargetRepo" -ForegroundColor Gray
Write-Host "Base Branch   : $CurrentBranch" -ForegroundColor Gray
Write-Host "Worktree Name : $WorktreeName" -ForegroundColor Gray
Write-Host "Branch Name   : $BranchName" -ForegroundColor Gray
Write-Host "Agent Instr.  : $(if ($agentInstructionsName) { $agentInstructionsName } else { 'None (standard workflow)' })" -ForegroundColor Gray

# ==========================================================
# STEP 1: Fetch issue details & confirm with user
# ==========================================================
Write-Host "`n>>> [STEP 1/5] Fetching issue details from GitHub..." -ForegroundColor Cyan
$fetchScript = Join-Path $ScriptsDir "fetch-issue.ps1"
$issueData = & $fetchScript -IssueNumber $IssueNumber
if ($LASTEXITCODE -ne 0 -or -not $issueData) {
    Write-Host "[INFO] Process aborted or issue fetch failed." -ForegroundColor Yellow
    exit 0
}

# Dry Run intercept
if ($DryRun) {
    Write-Host "`n[DRY RUN] Issue #$IssueNumber fetched successfully. Planned execution:" -ForegroundColor Magenta
    Write-Host "  - Target Repo     : $TargetRepo"
    Write-Host "  - Base Branch     : $CurrentBranch"
    Write-Host "  - Worktree Branch : $BranchName"
    Write-Host "  - Worktree Path   : $WorktreePath"
    Write-Host "  - Container Engine: $(if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { 'auto-detect (podman/docker)' })"
    Write-Host "  - Sandbox Mode    : $(if ($InteractiveSandbox) { 'Interactive bash shell' } else { 'Automated Antigravity agent runner' })"
    Write-Host "  - Build Sandbox   : $BuildSandbox"
    Write-Host "[DRY RUN] Simulation complete. No worktree created, no container started, no commits made." -ForegroundColor Magenta
    exit 0
}

# ==========================================================
# STEP 2: Create isolated Git Worktree and branch
# ==========================================================
Write-Host "`n>>> [STEP 2/5] Creating isolated Git Worktree..." -ForegroundColor Cyan
$createWorktreeScript = Join-Path $ScriptsDir "create-worktree.ps1"
& $createWorktreeScript -WorktreeName $WorktreeName -BranchName $BranchName -BaseBranch $CurrentBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create git worktree." -ForegroundColor Red
    exit 1
}

# Write bundled issue context into worktree (UTF-8 No-BOM)
$issueContextPath = Join-Path $WorktreePath "ISSUE_CONTEXT.md"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($issueContextPath, $issueData.Context, $utf8NoBom)
Write-Host "[OK] Injected issue context into worktree: $issueContextPath" -ForegroundColor Green
if ($agentInstructionsName) {
    Write-Host "[OK] Active repository agent instructions: $agentInstructionsName" -ForegroundColor Green
}

# ==========================================================
# STEP 3: Run Docker Sandbox with automated agy
# ==========================================================
Write-Host "`n>>> [STEP 3/5] Launching Sandbox & running Antigravity (agy)..." -ForegroundColor Cyan
$sandboxScript = Join-Path $ScriptsDir "run-sandbox.ps1"
$issueRelFile = ".worktrees/$WorktreeName/ISSUE_CONTEXT.md"

$sandboxParams = @{
    WorktreeName = $WorktreeName
    IssueFile    = $issueRelFile
    TargetRepo   = $TargetRepo
}
if ($agentInstructionsName) {
    $sandboxParams["InstructionsFile"] = $agentInstructionsName
}
if ($BuildSandbox) { $sandboxParams["Build"] = [switch]$true }
if ($InteractiveSandbox) { $sandboxParams["Interactive"] = [switch]$true }

& $sandboxScript @sandboxParams
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Sandbox run failed with exit code $LASTEXITCODE." -ForegroundColor Red
    exit $LASTEXITCODE
}

# Explicit worktree repair on Windows host (suppress informational stderr to prevent NativeCommandError)
Set-Location $TargetRepo
if (Test-Path $WorktreePath) {
    & {
        $ErrorActionPreference = "SilentlyContinue"
        git worktree repair $WorktreePath 2>&1 | Out-Null
    }
}

# ==========================================================
# STEP 4: Review changes with agy, confirm, merge & cleanup
# ==========================================================
Write-Host "`n>>> [STEP 4/5] Reviewing changes and merging..." -ForegroundColor Cyan
$reviewScript = Join-Path $ScriptsDir "review-merge.ps1"

# Capture output safely, isolating boolean return value
$reviewOutput = @(& $reviewScript -WorktreeName $WorktreeName -BranchName $BranchName -BaseBranch $CurrentBranch)
$merged = ($reviewOutput | Where-Object { $_ -is [bool] } | Select-Object -Last 1) -eq $true

# ==========================================================
# STEP 5: Confirm and push to remote
# ==========================================================
if ($merged -eq $true) {
    Write-Host "`n>>> [STEP 5/5] Push changes to remote..." -ForegroundColor Cyan
    $pushScript = Join-Path $ScriptsDir "push-changes.ps1"
    & $pushScript -BranchName $CurrentBranch -Remote "origin"
} else {
    Write-Host "`n[INFO] Skipping push since changes were not merged into '$CurrentBranch'." -ForegroundColor Yellow
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   Issue #$IssueNumber Workflow Completed!               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
