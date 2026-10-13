# SubagentStart hook: tells selected subagents where this kit keeps its data (their prompts refer to KIT_DATA).
function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $env:USERPROFILE '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
function Test-AgentIs([string]$Type, [string[]]$Names) {
    # plugin agents report agent_type as "<plugin>:<name>"; user-level agents report "<name>"
    foreach ($n in $Names) { if ($Type -eq $n -or $Type.EndsWith(':' + $n)) { return $true } }
    return $false
}
function Write-HookError([string]$Where, $Err) {
    # A failed start-up hook must leave a trace: the agent only sees a missing KIT_DATA line.
    try {
        $dir = Get-KitData
        [void](New-Item -ItemType Directory -Force -Path $dir)
        Add-Content -LiteralPath (Join-Path $dir 'hook-errors.log') -Value ("{0:o} {1} {2}" -f (Get-Date), $Where, ([string]$Err -replace '\s+', ' '))
    } catch { }
}
try {
    # Bounded stdin read: an unread pipe must not hang the hook until the harness kills it.
    $reader = [Console]::In.ReadToEndAsync()
    if (-not $reader.Wait(10000)) { Write-HookError 'inject-context' 'stdin not closed within 10 s; no context injected'; exit 0 }
    $in = $reader.Result | ConvertFrom-Json
    if (-not (Test-AgentIs ([string]$in.agent_type) @('verification-runner'))) { exit 0 }
    [void](New-Item -ItemType Directory -Force -Path ((Get-KitData) + '/verification-logs'))   # the redirect target must exist
    $cfg = $env:CLAUDE_CONFIG_DIR; if (-not $cfg -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $cfg = $Matches[1] }; if (-not $cfg) { $cfg = Join-Path $env:USERPROFILE '.claude' }
    $ctx = "KIT_DATA=$(Get-KitData)`nCONFIG_DIR=$(($cfg -replace '\\', '/').TrimEnd('/'))"
    [Console]::Out.WriteLine((@{ hookSpecificOutput = @{ hookEventName = 'SubagentStart'; additionalContext = $ctx } } | ConvertTo-Json -Depth 5 -Compress))
} catch { Write-HookError 'inject-context' $_.Exception.Message }
exit 0
