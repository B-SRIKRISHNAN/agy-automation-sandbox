$BinDir = $PSScriptRoot
$ToolkitRoot = (Resolve-Path (Join-Path $BinDir "..")).Path
$MasterScript = Join-Path $ToolkitRoot "start-issue.ps1"
& $MasterScript @args
exit $LASTEXITCODE
