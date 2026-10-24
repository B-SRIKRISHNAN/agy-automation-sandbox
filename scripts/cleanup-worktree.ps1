<#
.SYNOPSIS
    Cleans up a Git worktree, prunes worktrees, and deletes the associated branch.

.DESCRIPTION
    Removes the specified worktree under .worktrees/<worktree-name>, prunes git
    worktree metadata, and deletes the specified branch. Defaults to 'agent-worktree1'
    and 'agent-branch1'.

.PARAMETER WorktreeName
    The name of the worktree directory (default: "agent-worktree1").

.PARAMETER BranchName
    The name of the branch to delete (default: "agent-branch1").

.PARAMETER Force
    Force removal of worktree and deletion of branch even if there are uncommitted or unmerged changes.

.EXAMPLE
    .\scripts\cleanup-worktree.ps1
    .\scripts\cleanup-worktree.ps1 -Force
    .\scripts\cleanup-worktree.ps1 -WorktreeName "agent-worktree2" -BranchName "agent-branch2" -Force
#>

param (
    [string]$WorktreeName = "agent-worktree1",
    [string]$BranchName = "agent-branch1",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Determine Git repository root
try {
    $RepoRoot = (git rev-parse --show-toplevel 2>$null).Trim()
} catch {
    Write-Host "[ERROR] Not inside a Git repository." -ForegroundColor Red
    exit 1
}

if (-not $RepoRoot) {
    Write-Host "[ERROR] Could not determine Git repository root." -ForegroundColor Red
    exit 1
}

$CurrentDir = (Get-Location).Path
$WorktreePath = Join-Path (Join-Path $RepoRoot ".worktrees") $WorktreeName

# Ensure we are not currently inside the worktree directory being deleted
if ($CurrentDir.StartsWith($WorktreePath, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "[INFO] Current directory is inside the worktree to be removed. Switching to repo root..." -ForegroundColor Yellow
    Set-Location $RepoRoot
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Cleaning up Git Worktree: $WorktreeName                " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Worktree Path : $WorktreePath" -ForegroundColor Gray
Write-Host "Branch Name   : $BranchName" -ForegroundColor Gray
Write-Host "Force Mode    : $(if ($Force) { 'Enabled' } else { 'Disabled' })" -ForegroundColor Gray

# 1. Check if worktree is registered in git worktree list
$WorktreeList = git worktree list --porcelain
$IsRegistered = $false
if ($WorktreeList) {
    $NormalizedWorktreePath = $WorktreePath.Replace("\", "/").TrimEnd("/")
    foreach ($line in ($WorktreeList -split "`r?`n")) {
        if ($line.StartsWith("worktree ")) {
            $registeredPath = $line.Substring(9).Trim().Replace("\", "/").TrimEnd("/")
            if ($registeredPath -eq $NormalizedWorktreePath) {
                $IsRegistered = $true
                break
            }
        }
    }
}

# 2. Remove git worktree
if ($IsRegistered) {
    Write-Host "`n[1/3] Removing git worktree entry..." -ForegroundColor Cyan
    if ($Force) {
        git worktree remove --force $WorktreePath
    } else {
        git worktree remove $WorktreePath
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARNING] 'git worktree remove' reported an issue. Attempting with force..." -ForegroundColor Yellow
        git worktree remove --force $WorktreePath 2>$null
    }
} else {
    Write-Host "`n[1/3] Worktree '$WorktreeName' not actively registered in git worktree list." -ForegroundColor Gray
}

# Ensure filesystem folder is cleaned up if it still remains
if (Test-Path $WorktreePath) {
    Write-Host "      Cleaning up residual directory at $WorktreePath..." -ForegroundColor Yellow
    Remove-Item -Path $WorktreePath -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Prune worktrees
Write-Host "`n[2/3] Pruning git worktree metadata..." -ForegroundColor Cyan
git worktree prune --expire now
Write-Host "      Worktree metadata pruned." -ForegroundColor Green

# 4. Remove the branch
Write-Host "`n[3/3] Removing branch '$BranchName'..." -ForegroundColor Cyan
$branchList = (git branch --list $BranchName 2>$null)
$BranchExists = if ($branchList) { $branchList.Trim() } else { $null }
if ($BranchExists) {
    # Check if we are currently checked out on that branch in main repo
    $showCurrent = (git branch --show-current 2>$null)
    $CurrentBranch = if ($showCurrent) { $showCurrent.Trim() } else { "" }
    if ($CurrentBranch -eq $BranchName) {
        Write-Host "[WARNING] Currently on '$BranchName' in main worktree. Cannot delete active branch." -ForegroundColor Red
        Write-Host "          Please checkout another branch (e.g. git checkout master) first." -ForegroundColor Yellow
    } else {
        if ($Force) {
            git branch -D $BranchName
        } else {
            git branch -d $BranchName 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "      Branch '$BranchName' not fully merged. Deleting with -D (force)..." -ForegroundColor Yellow
                git branch -D $BranchName
            }
        }
        Write-Host "      Branch '$BranchName' deleted." -ForegroundColor Green
    }
} else {
    Write-Host "      Branch '$BranchName' does not exist." -ForegroundColor Gray
}

Write-Host "`n[SUCCESS] Cleanup complete for '$WorktreeName' and '$BranchName'!" -ForegroundColor Green
Write-Host "`nCurrent worktrees:" -ForegroundColor DarkCyan
git worktree list | Out-Host
