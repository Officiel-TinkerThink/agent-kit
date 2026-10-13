# safe-rm.ps1 - the executor behind `rm` for guarded agents. It NEVER deletes: it validates against safe-rm-policy.json,
# records the operation (path, size, SHA-256) in the audit file and a manifest FIRST, then MOVES the items into the quarantine folder.
# Restore with safe-rm-restore.ps1. Exit codes: 0 ok / nothing to do, 2 refused, 3 partial or failed move (see output).
[CmdletBinding(PositionalBinding = $false)]
param(
    [switch]$Recurse,
    [string]$Agent = '',
    [string]$Session = '',
    [string]$PolicyFile = '',
    [switch]$DryRun,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Paths
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'safe-rm-lib.ps1')

function Write-Utf8NoBom([string]$Path, [string]$Text) { [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false))) }
function Add-Jsonl([string]$File, $Obj) {
    $dir = Split-Path -Parent $File
    if (-not (Test-Path -LiteralPath $dir)) { [void](New-Item -ItemType Directory -Force -Path $dir) }
    [System.IO.File]::AppendAllText($File, (($Obj | ConvertTo-Json -Depth 8 -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
}
function Get-TextSha256([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    return (($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text)) | ForEach-Object { $_.ToString('X2') }) -join '')
}

try {
    $policy = Get-SafeRmPolicy -PolicyFile $PolicyFile
    if (-not $Paths -or $Paths.Count -eq 0) { [Console]::Error.WriteLine('REFUSED: no path given'); exit 2 }
    $res = Resolve-SafeRmPaths -Policy $policy -Tokens $Paths -Recurse $Recurse.IsPresent
    if (-not $res.Ok) { [Console]::Error.WriteLine("REFUSED: $($res.Reason)"); exit 2 }
    if ($res.Items.Count -eq 0) {
        Write-Output ('NOTHING TO DELETE. Skipped: ' + (($res.Skipped) -join '; '))
        exit 0
    }
    if ($DryRun) {
        foreach ($i in $res.Items) { Write-Output ("WOULD QUARANTINE {0} ({1} files, {2} bytes)" -f $i.Full, $i.Files, $i.Bytes) }
        exit 0
    }

    $id = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfff') + '-' + ('{0:x4}' -f (Get-Random -Maximum 65536))
    $qroot = [System.IO.Path]::GetFullPath([string]$policy.quarantineRoot)
    $qdir = Join-Path $qroot $id
    $auditFile = [System.IO.Path]::GetFullPath([string]$policy.auditFile)

    # --- hash everything first (files <= caps, so this is bounded) ---
    $manifestItems = New-Object System.Collections.ArrayList
    foreach ($i in $res.Items) {
        $drive = $i.Full.Substring(0, 1).ToUpper()
        $relNoDrive = $i.Full.Substring(3)
        $dest = Join-Path $qdir (Join-Path ('data\' + $drive) $relNoDrive)
        if ($i.IsDir) {
            $lines = New-Object System.Collections.ArrayList
            foreach ($f in (Get-ChildItem -LiteralPath $i.Full -Recurse -Force -File)) {
                $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
                [void]$lines.Add(($f.FullName.Substring($i.Full.Length + 1) + '|' + $f.Length + '|' + $h))
            }
            $digest = Get-TextSha256 ((@($lines) | Sort-Object) -join "`n")
            $kind = 'dir'
        } else {
            $digest = (Get-FileHash -LiteralPath $i.Full -Algorithm SHA256).Hash
            $kind = 'file'
        }
        [void]$manifestItems.Add([ordered]@{ path = $i.Full; kind = $kind; files = $i.Files; bytes = $i.Bytes; sha256 = $digest; quarantinePath = $dest; status = 'pending' })
    }

    # --- record BEFORE moving; if the record cannot be written nothing is moved ---
    $ts = (Get-Date).ToUniversalTime().ToString('o')
    $manifest = [ordered]@{ schema = 'safe-rm/1'; id = $id; ts = $ts; user = $env:USERNAME; agent = $Agent; session = $Session; recurse = $Recurse.IsPresent; status = 'pending'; items = @($manifestItems) }
    try {
        [void](New-Item -ItemType Directory -Force -Path $qdir)
        Write-Utf8NoBom (Join-Path $qdir 'manifest.json') ($manifest | ConvertTo-Json -Depth 8)
        Add-Jsonl $auditFile ([ordered]@{ schema = 'safe-rm/1'; op = 'delete'; phase = 'planned'; id = $id; ts = $ts; user = $env:USERNAME; agent = $Agent; session = $Session; items = @($manifestItems | ForEach-Object { [ordered]@{ path = $_.path; kind = $_.kind; files = $_.files; bytes = $_.bytes; sha256 = $_.sha256 } }) })
    } catch {
        [Console]::Error.WriteLine("REFUSED: could not write the audit record or manifest, so nothing was moved. ($($_.Exception.Message))")
        exit 2
    }

    # --- move ---
    $failed = 0
    foreach ($m in $manifestItems) {
        try {
            $parent = Split-Path -Parent $m.quarantinePath
            if (-not (Test-Path -LiteralPath $parent)) { [void](New-Item -ItemType Directory -Force -Path $parent) }
            Move-Item -LiteralPath $m.path -Destination $m.quarantinePath -ErrorAction Stop
            $m.status = 'moved'
        } catch {
            $m.status = 'failed'; $m.error = $_.Exception.Message; $failed++
        }
    }
    $manifest.status = if ($failed -eq 0) { 'done' } else { 'partial' }
    $manifest.items = @($manifestItems)
    Write-Utf8NoBom (Join-Path $qdir 'manifest.json') ($manifest | ConvertTo-Json -Depth 8)
    Add-Jsonl $auditFile ([ordered]@{ schema = 'safe-rm/1'; op = 'delete'; phase = 'completed'; id = $id; ts = (Get-Date).ToUniversalTime().ToString('o'); status = $manifest.status; moved = @($manifestItems | Where-Object { $_.status -eq 'moved' } | ForEach-Object { $_.path }); failed = @($manifestItems | Where-Object { $_.status -eq 'failed' } | ForEach-Object { $_.path }) })

    $movedCount = @($manifestItems | Where-Object { $_.status -eq 'moved' }).Count
    Write-Output ("QUARANTINED id={0} items={1} (restorable, not permanently deleted)" -f $id, $movedCount)
    foreach ($m in $manifestItems) { Write-Output ("  {0}  {1} ({2} files, {3} bytes)" -f $m.status.ToUpper(), $m.path, $m.files, $m.bytes) }
    if ($res.Skipped.Count -gt 0) { Write-Output ('Skipped: ' + (($res.Skipped) -join '; ')) }
    if ($failed -gt 0) { [Console]::Error.WriteLine("PARTIAL: $failed item(s) could not be moved; see the manifest in $qdir"); exit 3 }
    exit 0
} catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 3
}
