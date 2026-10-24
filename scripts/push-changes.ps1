<#
.SYNOPSIS
    Prompts user for final permission and pushes commits to the remote branch.

.DESCRIPTION
    Fetches latest remote state, checks for unpushed commits on the target branch
    (including brand-new branches), displays the commit log, requests explicit approval,
    and pushes with upstream tracking (-u).

.PARAMETER BranchName
    The local branch to push (default: current active branch).

.PARAMETER Remote
    The remote repository name (default: "origin").

.EXAMPLE
    .\scripts\push-changes.ps1
    .\scripts\push-changes.ps1 -BranchName "main" -Remote "origin"
#>

param (
    [string]$BranchName = "",
    [string]$Remote = "origin"
)

$ErrorActionPreference = "Stop"

# Determine Git repository root
try {
    $RepoRoot = (git rev-parse --show-toplevel 2>$null).Trim()
} catch {
    Write-Host "[ERROR] Not inside a Git repository." -ForegroundColor Red
    exit 1
}

Set-Location $RepoRoot

if (-not $BranchName) {
    $showCurrent = (git branch --show-current 2>$null)
    if ($showCurrent) {
        $BranchName = $showCurrent.Trim()
    } else {
        Write-Host "[ERROR] Could not determine active branch to push. Please specify -BranchName." -ForegroundColor Red
        exit 1
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Push Changes to Remote: $Remote/$BranchName            " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Fetch remote branch state before comparing
Write-Host "[INFO] Fetching latest state from $Remote/$BranchName..." -ForegroundColor Cyan
git fetch $Remote $BranchName 2>$null | Out-Null

# 2. Check if branch exists on remote
$lsRemote = (git ls-remote --heads $Remote $BranchName 2>$null)
$remoteBranchExists = if ($lsRemote) { $lsRemote.Trim() } else { $null }

if (-not $remoteBranchExists) {
    Write-Host "[INFO] Branch '$BranchName' does not exist yet on '$Remote' (brand new remote branch)." -ForegroundColor Yellow
    $unpushedCommits = git log $BranchName -n 5 --oneline 2>$null
} else {
    $unpushedCommits = git log "$Remote/$BranchName..$BranchName" --oneline 2>$null
}

if (-not $unpushedCommits) {
    Write-Host "[INFO] Local branch '$BranchName' is already in sync with '$Remote/$BranchName'." -ForegroundColor Yellow
    Write-Host "       No unpushed commits found." -ForegroundColor Gray
    exit 0
}

Write-Host "`nCommits to be pushed to $Remote/$BranchName :" -ForegroundColor Cyan
$unpushedCommits | ForEach-Object { Write-Host "  * $_" -ForegroundColor White }

# 3. Request confirmation
Write-Host "`nDo you approve pushing these changes to '$Remote/$BranchName'? (y/N): " -NoNewline -ForegroundColor Yellow
$response = Read-Host

if ($response -and $response.Trim().ToLower() -in @("y", "yes")) {
    Write-Host "`n[INFO] Pushing changes with upstream tracking (-u)..." -ForegroundColor Cyan
    git push -u $Remote $BranchName

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[SUCCESS] Successfully pushed changes to $Remote/$BranchName!" -ForegroundColor Green
    } else {
        Write-Host "`n[ERROR] Git push failed. Please check network/credentials." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "`n[INFO] Push aborted by user. Your local branch '$BranchName' was NOT pushed." -ForegroundColor Yellow
}
