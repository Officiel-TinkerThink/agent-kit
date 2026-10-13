# Operator tool behind /kit-allow (agent-guards). Records a USER-APPROVED change to the browser host allowlist, never an agent's own decision.
#   kit-policy.ps1 -Action list-blocked [-Max 20]
#   kit-policy.ps1 -Action add-host -HostName docs.example.com -Reason "..."
#   kit-policy.ps1 -Action show
# Commands for the verification-runner are NOT managed here: Claude Code's own permissions (settings allow / ask / deny rules) decide those.
# Every change appends one line to <KIT_DATA>/audit/policy-changes.jsonl (who, when, why, SHA-256 of the file before and after).
# Policy file: <KIT_DATA>/browser-policy.json (allowedHosts).
# Exit codes: 0 ok, 1 refused (bad input), 2 internal error.
param(
    [Parameter(Mandatory)][ValidateSet('list-blocked', 'add-host', 'show')][string]$Action,
    [string]$HostName, [string]$Reason, [int]$Max = 20
)
$ErrorActionPreference = 'Stop'
function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $env:USERPROFILE '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
function Get-Sha([string]$Path) { if (Test-Path -LiteralPath $Path) { return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower() } return $null }
function Refuse([string]$Msg) { [Console]::Error.WriteLine("REFUSED: $Msg"); exit 1 }
function Write-Json([string]$Path, $Obj) {
    $tmp = $Path + '.tmp'
    [System.IO.File]::WriteAllText($tmp, ($Obj | ConvertTo-Json -Depth 8), (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}
function Add-Change([string]$File, $Before, $After, $Entry) {
    $dir = (Get-KitData) + '/audit'
    [void](New-Item -ItemType Directory -Force -Path $dir)
    $rec = [ordered]@{ ts = (Get-Date).ToUniversalTime().ToString('o'); actor = $env:USERNAME; action = $Action; file = $File
                       before_sha256 = $Before; after_sha256 = $After; entry = $Entry; reason = $Reason; approved = 'user confirmed in chat' }
    Add-Content -LiteralPath ($dir + '/policy-changes.jsonl') -Value ($rec | ConvertTo-Json -Compress -Depth 6) -Encoding UTF8 -ErrorAction Stop
}
function Read-Policy([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return [pscustomobject]@{} }
    try { return (Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json) } catch { Refuse "$Path is not valid JSON; fix or remove it first ($($_.Exception.Message))" }
}

try {
    $kit = Get-KitData
    switch ($Action) {
        'show' {
            $p = "$kit/browser-policy.json"
            Write-Output "== $p  sha256=$(Get-Sha $p)"
            if (Test-Path -LiteralPath $p) { Get-Content -Raw -LiteralPath $p } else { Write-Output '(absent)' }
        }
        'list-blocked' {
            $log = "$kit/audit/blocked-requests.jsonl"
            if (-not (Test-Path -LiteralPath $log)) { Write-Output 'No blocked requests recorded.'; break }
            $bp = Read-Policy "$kit/browser-policy.json"
            $allowedHost = @($bp.allowedHosts | Where-Object { $_ } | ForEach-Object { ([string]$_).ToLower() })
            $rows = Get-Content -LiteralPath $log -Tail 500 -Encoding UTF8 | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } } |
                Where-Object { $_ -and $_.kind -eq 'host' -and -not ($allowedHost -contains ([string]$_.value).ToLower()) } |
                Group-Object value | Sort-Object { ($_.Group | Select-Object -Last 1).ts } -Descending | Select-Object -First $Max
            if (-not $rows) { Write-Output 'No pending blocked hosts (all recorded ones are already allowed).'; break }
            $i = 0
            foreach ($g in $rows) {
                $i++; $last = $g.Group | Select-Object -Last 1
                Write-Output ("{0}. [host] {1}   (x{2}, last {3}, agent {4})" -f $i, $last.value, $g.Count, $last.ts, $last.agent)
            }
        }
        'add-host' {
            $h = ([string]$HostName).Trim().ToLower()
            if (-not $Reason) { Refuse '-Reason is required: say why this host is needed.' }
            if ($h -notmatch '^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$' -or $h -match '\.\.') { Refuse "host '$h' is not a plain host name (no scheme, port, path or wildcard)." }
            $path = "$kit/browser-policy.json"
            $j = Read-Policy $path
            $hosts = @($j.allowedHosts | Where-Object { $_ } | ForEach-Object { ([string]$_).ToLower() })
            if ($hosts.Count -eq 0) { Refuse 'browser-policy.json has no allowedHosts, which means every host is already allowed; adding one would RESTRICT the browser agents to it. Create the list deliberately by hand if you want a restriction.' }
            if ($hosts -contains $h) { Write-Output "Already allowed: $h"; break }
            $before = Get-Sha $path
            $j.allowedHosts = @($hosts) + $h
            Write-Json $path $j
            Add-Change 'browser-policy.json' $before (Get-Sha $path) ([ordered]@{ host = $h })
            Write-Output "Allowed host (browser agents): $h"
        }
    }
    exit 0
} catch {
    [Console]::Error.WriteLine("kit-policy failed: $($_.Exception.Message)")
    exit 2
}
