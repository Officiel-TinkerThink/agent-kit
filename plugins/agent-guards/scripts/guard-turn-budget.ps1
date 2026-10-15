# PreToolUse hook (matcher: .*), registered by the agent-guards plugin. Counts the tool calls of each kit subagent (key: agent_id)
# and, when the N-th call arrives (N from turn-budget.txt), blocks that one call with a message telling the agent to stop, write its
# final report and start it with PARTIAL. It never blocks again: the real cap (maxTurns = 3 x N in the agent file) is the safety margin.
# Fails open on any internal error (a cost and reliability aid, not a compliance control). State: <kit data>/turn-budget/<agent_id>.
$ErrorActionPreference = 'Stop'
function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $(if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
function Write-HookError([string]$m) {
    try { Add-Content -LiteralPath ((Get-KitData) + '/hook-errors.log') -Value ("{0} guard-turn-budget: {1}" -f (Get-Date).ToString('o'), $m) -Encoding UTF8 } catch { }
}
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $id = [string]$in.agent_id
    if (-not $id -or $id -eq 'false' -or $id -eq '0') { exit 0 }
    if ($id -notmatch '^[A-Za-z0-9_-]+$') { exit 0 }
    if ([string]$in.tool_name -eq 'SubagentHandback') { exit 0 }

    $type = [string]$in.agent_type
    $base = $type.Substring($type.LastIndexOf(':') + 1)
    if (-not $base) { exit 0 }
    $n = 0
    foreach ($row in (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'turn-budget.txt') -ErrorAction Stop)) {
        $p = $row -split '\s+'
        if ($p.Length -ge 2 -and $p[0] -notmatch '^#' -and $p[0] -ceq $base) { if ($p[1] -match '^\d+$') { $n = [int]$p[1] }; break }
    }
    if ($n -le 0) { exit 0 }

    $dir = (Get-KitData) + '/turn-budget'
    $f = $dir + '/' + $id
    try { [void](New-Item -ItemType Directory -Force -Path $dir) } catch { Write-HookError "cannot create $dir"; exit 0 }
    $c = 0
    if (Test-Path -LiteralPath $f -PathType Leaf) { $raw = (Get-Content -LiteralPath $f -TotalCount 1); if ($raw -match '^\d+$') { $c = [int]$raw } }
    $c++
    try { [IO.File]::WriteAllText($f, "$c`n", (New-Object System.Text.UTF8Encoding($false))) } catch { Write-HookError "cannot write $f"; exit 0 }
    # a new agent: drop count files of finished runs older than a day (only inside the turn-budget folder)
    if ($c -eq 1) {
        $old = (Get-Date).AddDays(-1)
        Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $old } | Remove-Item -Force -ErrorAction SilentlyContinue
    }

    if ($c -eq $n) {
        [Console]::Error.WriteLine("BLOCKED (intentional guard, not a hook failure): turn budget reached ($n tool calls). Stop calling tools and write your final report now. Its first line is PARTIAL, then list what you did not do or did not check. Use another tool only if the report cannot be written without it.")
        exit 2
    }
    exit 0
} catch { exit 0 }
