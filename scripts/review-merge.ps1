<#
.SYNOPSIS
    Reviews worktree changes against base branch using agy, requests merge approval, and cleans up.

.DESCRIPTION
    Compares the worktree branch with the base branch (git log & git diff), invokes Antigravity
    CLI (agy) to generate a detailed code review summary, verifies workspace cleanliness,
    executes linear merge into the base branch with rollback safety, and cleans up.

.PARAMETER WorktreeName
    The name of the worktree directory under .worktrees/.

.PARAMETER BranchName
    The name of the feature branch created for the worktree.

.PARAMETER BaseBranch
    The base branch to compare against and merge into (default: current active branch).

.EXAMPLE
    .\scripts\review-merge.ps1 -WorktreeName "worktree-issue-15" -BranchName "issue-15" -BaseBranch "main"
#>

param (
    [Parameter(Mandatory = $true)]
    [string]$WorktreeName,
    [Parameter(Mandatory = $true)]
    [string]$BranchName,
    [string]$BaseBranch = ""
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
$worktreeHostDir = Join-Path (Join-Path $RepoRoot ".worktrees") $WorktreeName
if (Test-Path $worktreeHostDir) {
    & {
        $ErrorActionPreference = "SilentlyContinue"
        git worktree repair $worktreeHostDir 2>&1 | Out-Null
    }
}

if (-not $BaseBranch) {
    $showCurrent = (git branch --show-current 2>$null)
    if ($showCurrent) {
        $BaseBranch = $showCurrent.Trim()
    } else {
        Write-Host "[ERROR] Could not determine base branch to merge into. Please specify -BaseBranch." -ForegroundColor Red
        exit 1
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Code Review & Merge: $BranchName -> $BaseBranch        " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Worktree Name : $WorktreeName" -ForegroundColor Gray
Write-Host "Feature Branch: $BranchName" -ForegroundColor Gray
Write-Host "Target Branch : $BaseBranch" -ForegroundColor Gray

# 1. Inspect commits and diff
$commits = (git log "$BaseBranch..$BranchName" --oneline 2>$null)
$diffStat = (git diff "$BaseBranch..$BranchName" --stat 2>$null)
$diff = (git diff "$BaseBranch..$BranchName" 2>$null)

if (-not $commits -and -not $diff) {
    Write-Host "`n[WARNING] No differences found between '$BranchName' and '$BaseBranch'." -ForegroundColor Yellow
    Write-Host "No changes to review or merge." -ForegroundColor Yellow
    return $false
}

Write-Host "`n[1/3] Commits on '$BranchName':" -ForegroundColor Cyan
$commits | ForEach-Object { Write-Host "  * $_" -ForegroundColor White }

Write-Host "`n[2/3] Changed Files:" -ForegroundColor Cyan
$diffStat | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

# Convert diff array to string and truncate to 2000 characters to stay well within Windows CLI argument limits
$diffString = if ($diff) { ($diff -join "`n") } else { "" }
if ($diffString.Length -gt 2000) {
    $diffSnippet = $diffString.Substring(0, 2000) + "`n`n... [diff truncated to stay within command buffer; full changes visible via git diff $BaseBranch..$BranchName]"
} else {
    $diffSnippet = $diffString
}

# 2. Verify agy CLI is installed on host (Option B: strictly required)
if (-not (Get-Command agy -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Antigravity CLI (agy) is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install agy to proceed: https://antigravity.google/cli" -ForegroundColor Yellow
    exit 1
}

# 3. Generate detailed summary with agy
Write-Host "`n[3/3] Generating AI Code Review Summary using agy..." -ForegroundColor Cyan

# Check for repository agent instructions (AGENT_INSTRUCTIONS.md, case-insensitive)
$reviewInstrCandidate = Get-ChildItem -Path $RepoRoot -Depth 0 -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like "agent_instructions.md" -or $_.Name -like "AGENT_INSTRUCTIONS.MD" -or $_.Name -like "AGENT_INSTRUCTIONS.md"
} | Select-Object -First 1
$complianceSection = if ($reviewInstrCandidate) {
    "`n`n### 5. Repository Standards & Agent Instructions Compliance`n(Assess whether the code, documentation, and tests comply with the sequence and standards in $($reviewInstrCandidate.Name))"
} else { "" }

$reviewPrompt = @"
You are a senior principal engineer performing a code review. Analyze the following commits and diff for feature branch '$BranchName' targeting '$BaseBranch'.
Generate a comprehensive, crystal-clear review formatted with markdown headings:

### 1. Summary of Changes
(What problem was solved, core architectural changes, and rationale)

### 2. Detailed File-by-File Breakdown
(Grouped by module or component, describing specific modifications)

### 3. Impact & Risk Assessment
(Dependencies, database migrations, configuration updates, potential regressions)

### 4. Verification & Testing Checklist
(Recommended steps to test and verify these changes)$complianceSection

---
Commits:
$($commits -join "`n")

Diff Stat:
$($diffStat -join "`n")

Diff Details:
$diffSnippet
"@

try {
    $reviewSummary = (& {
        $ErrorActionPreference = "Continue"
        agy --dangerously-skip-permissions -p "$reviewPrompt" 2>&1
    })
    if ($LASTEXITCODE -eq 0 -and $reviewSummary) {
        Write-Host "`n===================== AI REVIEW SUMMARY =====================" -ForegroundColor DarkCyan
        $reviewSummary | Out-Host
        Write-Host "============================================================`n" -ForegroundColor DarkCyan
    } else {
        Write-Host "`n[INFO] AI review generation completed with notes:`n$reviewSummary" -ForegroundColor Gray
    }
} catch {
    Write-Host "[WARNING] agy CLI review generation failed: $_" -ForegroundColor Yellow
    Write-Host "Showing raw git diff stat instead:`n$diffStat" -ForegroundColor Gray
}

# 3. Prompt user for merge approval
Write-Host "Do you approve merging branch '$BranchName' into '$BaseBranch'? (y/N): " -NoNewline -ForegroundColor Yellow
$approval = Read-Host

if ($approval -and $approval.Trim().ToLower() -in @("y", "yes")) {
    # Guard: verify working tree cleanliness before checkout/merge
    $dirtyHost = (git status --porcelain 2>$null)
    # Filter out untracked files if needed, but if tracked files are dirty, prevent merge
    $dirtyTracked = $dirtyHost | Where-Object { $_ -notmatch '^\?\?' }
    if ($dirtyTracked) {
        Write-Host "[ERROR] Main workspace has uncommitted tracked changes:" -ForegroundColor Red
        $dirtyTracked | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
        Write-Host "Please stash or commit your local changes on '$BaseBranch' before merging." -ForegroundColor Yellow
        return $false
    }

    Write-Host "`n[INFO] Checking out base branch '$BaseBranch'..." -ForegroundColor Cyan
    git checkout $BaseBranch 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to checkout '$BaseBranch'. Merge aborted." -ForegroundColor Red
        return $false
    }

    # Attempt fast-forward merge first
    Write-Host "[INFO] Merging branch '$BranchName' into '$BaseBranch' (fast-forward)..." -ForegroundColor Cyan
    $ffOutput = (git merge --ff-only $BranchName 2>&1)
    if ($LASTEXITCODE -eq 0) {
        $ffOutput | Out-Host
    } else {
        Write-Host "[INFO] Fast-forward not possible. Attempting standard merge..." -ForegroundColor Yellow
        $mergeOutput = (git merge $BranchName -m "Merge branch '$BranchName' into $BaseBranch" 2>&1)
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Merge hit conflicts. Aborting merge to restore clean state..." -ForegroundColor Red
            git merge --abort 2>$null | Out-Null
            Write-Host "        Base branch restored to clean state. Worktree preserved for manual resolution." -ForegroundColor Yellow
            return $false
        } else {
            $mergeOutput | Out-Host
        }
    }

    Write-Host "[SUCCESS] Successfully merged '$BranchName' into '$BaseBranch'!" -ForegroundColor Green

    # 4. Clean up worktree and branch
    Write-Host "`n[INFO] Cleaning up worktree and temporary branch..." -ForegroundColor Cyan
    $cleanupScript = Join-Path $PSScriptRoot "cleanup-worktree.ps1"
    & $cleanupScript -WorktreeName $WorktreeName -BranchName $BranchName -Force

    return $true
} else {
    Write-Host "`n[INFO] Merge declined by user." -ForegroundColor Yellow
    # Safe default: pressing Enter (or anything other than 'n'/'no') keeps the worktree
    Write-Host "Keep worktree '$WorktreeName' for manual inspection? (Y/n): " -NoNewline -ForegroundColor Yellow
    $keepChoice = Read-Host
    if ($keepChoice -and $keepChoice.Trim().ToLower() -in @("n", "no")) {
        Write-Host "[INFO] Cleaning up worktree and temporary branch upon user request..." -ForegroundColor Cyan
        $cleanupScript = Join-Path $PSScriptRoot "cleanup-worktree.ps1"
        & $cleanupScript -WorktreeName $WorktreeName -BranchName $BranchName -Force
    } else {
        Write-Host "[INFO] Worktree preserved at .worktrees/$WorktreeName on branch '$BranchName'." -ForegroundColor Green
    }
    return $false
}
