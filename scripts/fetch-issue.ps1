<#
.SYNOPSIS
    Fetches a GitHub issue, confirms details with the user, and creates an issue context bundle.

.DESCRIPTION
    Uses GitHub CLI (gh) to fetch the issue title, body, author, labels, and comments.
    Displays a summary and asks the user for confirmation. If confirmed, writes
    the bundled context to ISSUE_CONTEXT.md (UTF-8 without BOM) and returns the issue object.

.PARAMETER IssueNumber
    The GitHub issue number to fetch.

.PARAMETER OutputPath
    Optional path to write the bundled issue context markdown file.

.EXAMPLE
    .\scripts\fetch-issue.ps1 -IssueNumber 15
#>

param (
    [Parameter(Mandatory = $true, Position = 0)]
    [int]$IssueNumber,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

# Verify GitHub CLI
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] GitHub CLI (gh) is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Fetching GitHub Issue #$IssueNumber                    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Fetch issue JSON
try {
    $rawJson = gh issue view $IssueNumber --json number,title,body,url,author,labels,comments 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $rawJson) {
        Write-Host "[ERROR] Failed to fetch issue #$IssueNumber from GitHub. Please check the issue number and your permissions." -ForegroundColor Red
        exit 1
    }
    $issue = $rawJson | ConvertFrom-Json
} catch {
    Write-Host "[ERROR] An error occurred while fetching issue #$($IssueNumber): $_" -ForegroundColor Red
    exit 1
}

# Guard against missing or invalid issue payload
if (-not $issue -or -not $issue.number) {
    Write-Host "[ERROR] Invalid or empty issue data received for issue #$IssueNumber." -ForegroundColor Red
    exit 1
}

$title = $issue.title
$url = $issue.url
$author = if ($issue.author) { $issue.author.login } else { "Unknown" }
$labels = if ($issue.labels) { ($issue.labels | ForEach-Object { $_.name }) -join ", " } else { "None" }
$body = $issue.body

Write-Host "`nIssue #$($issue.number): " -NoNewline -ForegroundColor Cyan
Write-Host "$title" -ForegroundColor Yellow
Write-Host "Author : " -NoNewline -ForegroundColor Gray
Write-Host "$author" -ForegroundColor White
Write-Host "URL    : " -NoNewline -ForegroundColor Gray
Write-Host "$url" -ForegroundColor Blue
Write-Host "Labels : " -NoNewline -ForegroundColor Gray
Write-Host "$labels" -ForegroundColor White
Write-Host "`n--- Description Preview ---" -ForegroundColor DarkGray
if ($body) {
    $preview = if ($body.Length -gt 500) { $body.Substring(0, 500) + "`n... [truncated]" } else { $body }
    Write-Host $preview -ForegroundColor Gray
} else {
    Write-Host "(No description provided)" -ForegroundColor DarkGray
}
Write-Host "---------------------------`n" -ForegroundColor DarkGray

# Prompt confirmation
Write-Host "Do you want to proceed with Issue #$($IssueNumber)? (Y/n): " -NoNewline -ForegroundColor Yellow
$response = Read-Host
if ($response -and $response.Trim().ToLower() -notin @("y", "yes")) {
    Write-Host "[INFO] Operation cancelled by user." -ForegroundColor Yellow
    exit 2
}

# Format bundled markdown context (Zero indentation on here-string)
$contextContent = @"
# Issue #$($issue.number): $title
- **URL**: $url
- **Author**: $author
- **Labels**: $labels

## Description
$body

## Comments
"@

# Array-wrap comments for PS 5.1 single-item compatibility
$commentsList = @($issue.comments)
if ($commentsList -and $commentsList.Count -gt 0) {
    foreach ($comment in $commentsList) {
        $cAuthor = if ($comment.author) { $comment.author.login } else { "Unknown" }
        $contextContent += "`n`n### Comment by @$cAuthor`n$($comment.body)"
    }
} else {
    $contextContent += "`n*(No comments)*"
}

if ($OutputPath) {
    $outDir = Split-Path $OutputPath -Parent
    if ($outDir -and -not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }
    # Enforce raw UTF-8 without BOM for cross-platform/container compatibility
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($OutputPath, $contextContent, $utf8NoBom)
    Write-Host "[OK] Bundled issue context written to: $OutputPath (UTF-8 No-BOM)" -ForegroundColor Green
}

# Return hashtable with issue metadata
return [PSCustomObject]@{
    Number  = $issue.number
    Title   = $title
    Url     = $url
    Author  = $author
    Labels  = $labels
    Body    = $body
    Context = $contextContent
}
