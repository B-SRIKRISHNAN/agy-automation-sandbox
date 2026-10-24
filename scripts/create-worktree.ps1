<#
.SYNOPSIS
    Creates a new Git worktree and branch for agent workflows.

.DESCRIPTION
    Creates a git worktree under .worktrees/<worktree-name> and branches from
    the current branch with <branch-name>. Enables relative worktree links for cross-OS
    compatibility with Docker containers. If the worktree or branch already exists,
    prompts the user for permission to remove and recreate them.

.PARAMETER WorktreeName
    The name of the worktree directory (default: "agent-worktree1").

.PARAMETER BranchName
    The name of the new branch (default: "agent-branch1").

.PARAMETER BaseBranch
    The base branch to branch from (default: current active branch).

.PARAMETER Force
    Force removal of existing worktree and branch without prompting.

.EXAMPLE
    .\scripts\create-worktree.ps1
    .\scripts\create-worktree.ps1 -WorktreeName "worktree-issue-35" -BranchName "issue-35"
#>

param (
    [string]$WorktreeName = "agent-worktree1",
    [string]$BranchName = "agent-branch1",
    [string]$BaseBranch = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Determine Git repository root
try {
    $RepoRoot = (git rev-parse --show-toplevel 2>$null)
    $RepoRoot = if ($RepoRoot) { $RepoRoot.Trim() } else { "" }
} catch {
    Write-Host "[ERROR] Not inside a Git repository." -ForegroundColor Red
    exit 1
}

if (-not $RepoRoot) {
    Write-Host "[ERROR] Could not determine Git repository root." -ForegroundColor Red
    exit 1
}

Set-Location $RepoRoot

# 1. Prune stale worktree metadata upfront
git worktree prune --expire now 2>$null | Out-Null

# 2. Configure Git to use relative paths for worktrees (critical for Docker Linux / Windows sharing)
git config worktree.useRelativePaths true 2>$null | Out-Null

# Determine base branch if not provided
if (-not $BaseBranch) {
    $showCurrent = (git branch --show-current 2>$null)
    $BaseBranch = if ($showCurrent) { $showCurrent.Trim() } else { "HEAD" }
}

# Guard: Ensure we are not trying to create a worktree on the active main branch
$activeBranch = (git branch --show-current 2>$null)
if ($activeBranch -and $activeBranch.Trim() -eq $BranchName) {
    Write-Host "[ERROR] Cannot create worktree for branch '$BranchName': It is already checked out in your main workspace." -ForegroundColor Red
    Write-Host "Please checkout another branch first (e.g. git checkout master)." -ForegroundColor Yellow
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Creating Git Worktree: $WorktreeName                  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Repository Root : $RepoRoot" -ForegroundColor Gray
Write-Host "Base Branch     : $BaseBranch" -ForegroundColor Gray
Write-Host "New Branch      : $BranchName" -ForegroundColor Gray
Write-Host "Worktree Name   : $WorktreeName" -ForegroundColor Gray

# Ensure .worktrees container folder exists
$WorktreesContainer = Join-Path $RepoRoot ".worktrees"
if (-not (Test-Path $WorktreesContainer)) {
    New-Item -ItemType Directory -Path $WorktreesContainer -Force | Out-Null
}

$WorktreePath = Join-Path $WorktreesContainer $WorktreeName

# Check if worktree directory exists or is registered in git worktree list
$worktreeListRaw = (git worktree list --porcelain 2>$null)
$isRegistered = $false
if ($worktreeListRaw) {
    $normalizedPath = $WorktreePath.Replace("\", "/").TrimEnd("/")
    foreach ($line in ($worktreeListRaw -split "`r?`n")) {
        if ($line.StartsWith("worktree ")) {
            $regPath = $line.Substring(9).Trim().Replace("\", "/").TrimEnd("/")
            if ($regPath -eq $normalizedPath) {
                $isRegistered = $true
                break
            }
        }
    }
}

if ((Test-Path $WorktreePath) -or $isRegistered) {
    $shouldRemoveWorktree = $false
    if ($Force) {
        $shouldRemoveWorktree = $true
    } else {
        Write-Host "`n[WARNING] Worktree '$WorktreeName' already exists at: $WorktreePath" -ForegroundColor Yellow
        Write-Host "Do you want to remove the existing worktree and recreate it? (y/N): " -NoNewline -ForegroundColor Yellow
        $resp = Read-Host
        if ($resp -and $resp.Trim().ToLower() -in @("y", "yes")) {
            $shouldRemoveWorktree = $true
        } else {
            Write-Host "[INFO] Worktree removal declined. Creation cancelled." -ForegroundColor Yellow
            exit 1
        }
    }

    if ($shouldRemoveWorktree) {
        Write-Host "[INFO] Properly removing existing worktree '$WorktreeName'..." -ForegroundColor Cyan
        git worktree remove --force $WorktreePath 2>$null | Out-Null
        if (Test-Path $WorktreePath) {
            Remove-Item -Path $WorktreePath -Recurse -Force -ErrorAction SilentlyContinue
        }
        git worktree prune --expire now 2>$null | Out-Null
        Write-Host "[OK] Existing worktree removed." -ForegroundColor Green
    }
}

# Check if branch already exists
$branchList = (git branch --list $BranchName 2>$null)
$branchExists = if ($branchList) { $branchList.Trim() } else { $null }

if ($branchExists) {
    $shouldDeleteBranch = $false
    if ($Force) {
        $shouldDeleteBranch = $true
    } else {
        Write-Host "`n[WARNING] Branch '$BranchName' already exists in local Git repository." -ForegroundColor Yellow
        Write-Host "Do you want to delete branch '$BranchName' and recreate it fresh from '$BaseBranch'? (y/N): " -NoNewline -ForegroundColor Yellow
        $resp = Read-Host
        if ($resp -and $resp.Trim().ToLower() -in @("y", "yes")) {
            $shouldDeleteBranch = $true
        } else {
            Write-Host "[INFO] Preserving existing branch '$BranchName'. Will attach worktree to it." -ForegroundColor Cyan
        }
    }

    if ($shouldDeleteBranch) {
        Write-Host "[INFO] Deleting existing branch '$BranchName'..." -ForegroundColor Cyan
        git branch -D $BranchName 2>$null | Out-Null
        $branchExists = $null
        Write-Host "[OK] Existing branch deleted." -ForegroundColor Green
    }
}

# Create or attach worktree
if ($branchExists) {
    Write-Host "`n[INFO] Attaching worktree to existing branch '$BranchName'..." -ForegroundColor Cyan
    git worktree add $WorktreePath $BranchName
} else {
    Write-Host "`n[INFO] Creating worktree with new branch '$BranchName' from '$BaseBranch'..." -ForegroundColor Cyan
    git worktree add -b $BranchName $WorktreePath $BaseBranch
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create git worktree." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[SUCCESS] Worktree ready!" -ForegroundColor Green
Write-Host "Location: $WorktreePath" -ForegroundColor Green
Write-Host "Branch  : $BranchName" -ForegroundColor Green
