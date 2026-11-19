# Read-only verification of the files listed in SHA256SUMS.txt.
$ErrorActionPreference = 'Stop'
$taskFailed = $false
foreach ($taskLine in Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SHA256SUMS.txt')) {
    if ($taskLine -notmatch '^([a-fA-F0-9]{64})  (.+)$') { throw 'Invalid checksum file.' }
    $taskExpected = $Matches[1]
    $taskPath = Join-Path $PSScriptRoot $Matches[2]
    if (-not (Test-Path -LiteralPath $taskPath)) { Write-Host ('MISSING: ' + $Matches[2]); $taskFailed = $true; continue }
    if ((Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash -ne $taskExpected) { Write-Host ('CHANGED: ' + $taskPath); $taskFailed = $true }
}
if ($taskFailed) { throw 'Some files are missing or changed.' }
Write-Host 'OK: all listed files match their SHA256 checksums.'
