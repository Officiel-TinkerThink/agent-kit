# safe-rm-restore.ps1 - for YOU (not agents). Lists quarantined deletions and restores one back to its original place.
#   powershell -File safe-rm-restore.ps1 -List
#   powershell -File safe-rm-restore.ps1 -Id <id>
# Restore refuses to overwrite anything that exists at the original path. Purging = deleting a folder under the quarantine root yourself.
param([switch]$List, [string]$Id = '', [string]$PolicyFile = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'safe-rm-lib.ps1')
$policy = Get-SafeRmPolicy -PolicyFile $PolicyFile
$qroot = [System.IO.Path]::GetFullPath([string]$policy.quarantineRoot)
$auditFile = [System.IO.Path]::GetFullPath([string]$policy.auditFile)
function Add-Jsonl([string]$File, $Obj) { [System.IO.File]::AppendAllText($File, (($Obj | ConvertTo-Json -Depth 8 -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false))) }

if ($List -or -not $Id) {
    if (-not (Test-Path -LiteralPath $qroot)) { Write-Output 'Quarantine is empty.'; exit 0 }
    foreach ($d in (Get-ChildItem -LiteralPath $qroot -Directory | Sort-Object Name)) {
        $mf = Join-Path $d.FullName 'manifest.json'
        if (-not (Test-Path -LiteralPath $mf)) { continue }
        $m = Get-Content -LiteralPath $mf -Raw -Encoding UTF8 | ConvertFrom-Json
        $first = @($m.items)[0].path
        Write-Output ("{0}  {1}  agent={2}  items={3}  status={4}  e.g. {5}" -f $m.id, $m.ts, $m.agent, @($m.items).Count, $m.status, $first)
    }
    exit 0
}

if ($Id -notmatch '^[0-9]{8}T[0-9]{9}-[0-9a-f]{4}$') { [Console]::Error.WriteLine('Invalid id.'); exit 2 }
$qdir = Join-Path $qroot $Id
$mf = Join-Path $qdir 'manifest.json'
if (-not (Test-Path -LiteralPath $mf)) { [Console]::Error.WriteLine("No such quarantine entry: $Id"); exit 2 }
$m = Get-Content -LiteralPath $mf -Raw -Encoding UTF8 | ConvertFrom-Json
$restored = @(); $problems = @()
foreach ($it in @($m.items)) {
    if ($it.status -ne 'moved') { continue }
    if (Test-Path -LiteralPath $it.path) { $problems += "exists, not overwritten: $($it.path)"; continue }
    if (-not (Test-Path -LiteralPath $it.quarantinePath)) { $problems += "missing in quarantine: $($it.quarantinePath)"; continue }
    $parent = Split-Path -Parent $it.path
    if (-not (Test-Path -LiteralPath $parent)) { [void](New-Item -ItemType Directory -Force -Path $parent) }
    Move-Item -LiteralPath $it.quarantinePath -Destination $it.path
    $restored += $it.path
}
Add-Jsonl $auditFile ([ordered]@{ schema = 'safe-rm/1'; op = 'restore'; id = $Id; ts = (Get-Date).ToUniversalTime().ToString('o'); user = $env:USERNAME; restored = $restored; problems = $problems })
foreach ($r in $restored) { Write-Output "RESTORED $r" }
foreach ($p in $problems) { [Console]::Error.WriteLine("PROBLEM: $p") }
if ($problems.Count -gt 0) { exit 3 }
exit 0
