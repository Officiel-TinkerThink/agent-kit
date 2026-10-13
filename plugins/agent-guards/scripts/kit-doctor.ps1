# Operator tool behind /kit-doctor (agent-guards). Read-only apart from one probe file per folder it test-writes (removed again).
# Checks: where KIT_DATA resolves and whether every candidate agrees, writability, policy files, policy drift (SHA-256 vs policy-changes.jsonl),
# recent hook errors, pending blocked requests, installed plugin versions. Prints [OK]/[WARN]/[FAIL] lines. Exit 1 if any FAIL.
param([string]$KitData)
$ErrorActionPreference = 'Continue'
$script:fail = 0; $script:warn = 0
function Say([string]$Level, [string]$Check, [string]$Detail) {
    Write-Output ("[{0}] {1}: {2}" -f $Level, $Check, $Detail)
    if ($Level -eq 'FAIL') { $script:fail++ } elseif ($Level -eq 'WARN') { $script:warn++ }
}
function Norm([string]$p) { return ($p -replace '\\', '/').TrimEnd('/') }
function Get-Sha([string]$Path) { if (Test-Path -LiteralPath $Path) { return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower() } return $null }

# --- 1. KIT_DATA resolution: the same order every hook uses, plus the candidates that would be used if an env var were missing
$cacheCfg = $null
if ($PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $cacheCfg = $Matches[1] }
$cands = [ordered]@{}
if ($env:AGENT_KIT_DATA) { $cands['AGENT_KIT_DATA'] = Norm $env:AGENT_KIT_DATA }
if ($env:CLAUDE_CONFIG_DIR) { $cands['CLAUDE_CONFIG_DIR'] = Norm (Join-Path $env:CLAUDE_CONFIG_DIR 'agent-kit') }
if ($cacheCfg) { $cands['plugin cache path'] = Norm (Join-Path $cacheCfg 'agent-kit') }
$cands['USERPROFILE default'] = Norm (Join-Path $(if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) '.claude/agent-kit')
$chosen = if ($KitData) { Norm $KitData } else { @($cands.Values)[0] }
Say 'OK' 'KIT_DATA' "$chosen (first candidate in the hooks' resolution order)"
$distinct = @($cands.Values | Select-Object -Unique)
if ($distinct.Count -gt 1) {
    $withData = @($distinct | Where-Object { (Test-Path -LiteralPath $_) -and (Get-ChildItem -LiteralPath $_ -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1) })
    if ($withData.Count -gt 1) { Say 'WARN' 'KIT_DATA split' ("more than one candidate folder holds data: {0}. Hooks and CLIs would disagree if their environment differs; consolidate or set AGENT_KIT_DATA." -f ($withData -join ' | ')) }
    elseif (-not $env:AGENT_KIT_DATA -and -not $env:CLAUDE_CONFIG_DIR) { Say 'WARN' 'environment' ("neither AGENT_KIT_DATA nor CLAUDE_CONFIG_DIR is set in this shell; candidates differ: {0}. Hooks inside Claude Code derive it from the plugin path; terminal tools would use the last one." -f (($cands.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join '; ')) }
}
if ($env:CLAUDE_CODE_SUBPROCESS_ENV_SCRUB -eq '1') { Say 'WARN' 'environment' 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 removes CLAUDE_CONFIG_DIR from hooks; the plugin-path derivation covers this, but set AGENT_KIT_DATA to be explicit.' }

# --- 2. writable
foreach ($sub in '', 'audit', 'usage', 'verification-logs', 'eval/inbox') {
    $dir = if ($sub) { "$chosen/$sub" } else { $chosen }
    try {
        [void](New-Item -ItemType Directory -Force -Path $dir -ErrorAction Stop)
        $probe = "$dir/.doctor-probe-$PID"
        Set-Content -LiteralPath $probe -Value 'x' -ErrorAction Stop; Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
        Say 'OK' 'writable' $dir
    } catch { Say 'FAIL' 'writable' "$dir is not writable ($($_.Exception.Message)); audit and usage records would be lost" }
}

# --- 3. policy files (parse and shape) and 4. drift against policy-changes.jsonl
$changes = @()
$cl = "$chosen/audit/policy-changes.jsonl"
if (Test-Path -LiteralPath $cl) { $changes = @(Get-Content -LiteralPath $cl -Encoding UTF8 | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } } | Where-Object { $_ }) }
$tok = '[A-Za-z0-9_./:=,\\\[\]@%+-]+'
if (Test-Path -LiteralPath "$chosen/verification-policy.json") { Say 'WARN' 'verification-policy.json' 'obsolete: the runner no longer has a command allowlist of its own (Claude Code permissions decide). The file is ignored; delete it when you no longer need it as a record.' }
foreach ($f in 'browser-policy.json', 'safe-rm-policy.json') {
    $p = "$chosen/$f"
    if (-not (Test-Path -LiteralPath $p)) { Say 'OK' $f 'absent (built-in defaults apply)'; continue }
    try { $j = Get-Content -Raw -LiteralPath $p | ConvertFrom-Json } catch { Say 'FAIL' $f "not valid JSON: $($_.Exception.Message)"; continue }
    switch ($f) {
        'browser-policy.json' {
            $h = @($j.allowedHosts)
            if ($h.Count -eq 0 -or ($h.Count -eq 1 -and $null -eq $h[0])) { Say 'OK' $f 'allowedHosts empty: every http(s) host is allowed' }
            else { Say 'OK' $f ("allowedHosts: {0}" -f (($h | ForEach-Object { [string]$_ }) -join ', ')) }
        }
        'safe-rm-policy.json' { if (-not $j.allowedRoots) { Say 'WARN' $f 'no allowedRoots: rm would be refused everywhere' } else { Say 'OK' $f ("{0} allowed root(s)" -f @($j.allowedRoots).Count) } }
    }
    $sha = Get-Sha $p
    $last = @($changes | Where-Object { $_.file -eq $f }) | Select-Object -Last 1
    if ($last) {
        if ($last.after_sha256 -eq $sha) { Say 'OK' "$f integrity" 'matches the last recorded change (policy-changes.jsonl)' }
        else { Say 'WARN' "$f integrity" "file differs from the last recorded change (recorded $($last.after_sha256.Substring(0, 12)), now $($sha.Substring(0, 12))): edited outside /agent-guards:kit-allow. Review it, then record it with a reason if intended." }
    } elseif ($f -ne 'safe-rm-policy.json') { Say 'WARN' "$f integrity" "no change record: the file was never changed via /agent-guards:kit-allow (sha256 $($sha.Substring(0, 12)))" }
}

# --- 5. hook errors (last 24 h)
$he = "$chosen/hook-errors.log"
if (Test-Path -LiteralPath $he) {
    $cut = (Get-Date).AddHours(-24)
    $recent = @(Get-Content -LiteralPath $he -Encoding UTF8 -Tail 200 | Where-Object { $_ -match '^(\d{4}-\d{2}-\d{2}T[0-9:.+-]+)' -and ([datetimeoffset]::Parse($Matches[1]).LocalDateTime -gt $cut) })
    if ($recent.Count -gt 0) { Say 'WARN' 'hook-errors.log' ("{0} error(s) in the last 24 h; latest: {1}" -f $recent.Count, ($recent | Select-Object -Last 1)) } else { Say 'OK' 'hook-errors.log' 'no errors in the last 24 h' }
} else { Say 'OK' 'hook-errors.log' 'absent (no hook errors recorded)' }

# --- 6. pending blocked requests
$bl = "$chosen/audit/blocked-requests.jsonl"
if (Test-Path -LiteralPath $bl) {
    $cut = (Get-Date).ToUniversalTime().AddDays(-7)
    $n = @(Get-Content -LiteralPath $bl -Encoding UTF8 -Tail 500 | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } } | Where-Object { $_ -and $_.kind -eq 'host' -and ([datetimeoffset]::Parse([string]$_.ts).UtcDateTime -gt $cut) }).Count
    if ($n -gt 0) { Say 'WARN' 'blocked requests' "$n blocked host request(s) in the last 7 days; run /agent-guards:kit-allow to review" } else { Say 'OK' 'blocked requests' 'none in the last 7 days' }
}

# --- 7. installed plugin versions (stale session = restart needed)
if ($cacheCfg) {
    $root = Join-Path $cacheCfg 'plugins/cache/agent-kit'
    $running = $null
    if ($PSScriptRoot -match 'agent-kit[\\/]([^\\/]+)[\\/]([^\\/]+)[\\/]scripts') { $running = @{ Plugin = $Matches[1]; Version = $Matches[2] } }
    foreach ($pl in 'haiku-delegation', 'agent-guards', 'agent-eval', 'verification-runner') {
        $vd = Join-Path $root $pl
        if (-not (Test-Path -LiteralPath $vd)) { Say 'WARN' "plugin $pl" 'not installed from agent-kit'; continue }
        $newest = Get-ChildItem -LiteralPath $vd -Directory | Sort-Object { try { [version]$_.Name } catch { [version]'0.0.0' } } | Select-Object -Last 1
        if ($running -and $running.Plugin -eq $pl -and $running.Version -ne $newest.Name) { Say 'WARN' "plugin $pl" "this session runs $($running.Version) but $($newest.Name) is installed: restart Claude Code" }
        else { Say 'OK' "plugin $pl" "newest installed $($newest.Name)" }
    }
}

Write-Output ("Summary: {0} FAIL, {1} WARN" -f $script:fail, $script:warn)
exit $(if ($script:fail -gt 0) { 1 } else { 0 })
