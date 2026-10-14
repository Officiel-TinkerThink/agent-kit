# PreToolUse hook (Agent), registered by the haiku-delegation plugin. The merged agents code-explorer and contracts-reader serve several kinds of task;
# the brief must start with `Task kind: <kind>` (several kinds separated by commas). Without it the agent has to guess the section and the usage log cannot
# pick the footer checks. A brief with no valid kind line is blocked once, with the message the main agent needs to fix it.
# PowerShell twin of guard-task-kind.sh. Convenience guard, not a safety guard: any parse problem allows the call (fail-open).
# Set TASK_KIND_GUARD=off in the environment to disable it.
try {
    if ($env:TASK_KIND_GUARD -ceq 'off') { exit 0 }
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $type = [string]$in.tool_input.subagent_type
    $base = $type -replace '^.*:', ''
    # the kinds of each topic agent come from kinds.txt (<agent> <kind> <footers>); an agent with no rows, or a missing table, is not guarded
    $valid = @()
    foreach ($row in (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'kinds.txt') -ErrorAction Stop)) {
        $f = @($row.Trim() -split '\s+')
        if ($f.Count -ge 2 -and -not $f[0].StartsWith('#') -and $f[0] -ceq $base) { $valid += $f[1] }
    }
    if ($valid.Count -eq 0) { exit 0 }
    $prompt = [string]$in.tool_input.prompt
    $first = ($prompt -split "`r?`n" | Where-Object { $_.Trim() -ne '' } | Select-Object -First 1)
    $kinds = @()
    if ($first -cmatch '^\s*Task kind:\s*(.*)$') { $kinds = @($Matches[1] -split '[,\s]+' | Where-Object { $_ }) }   # case-sensitive, like the shell version and the usage log
    $problem = $null
    if ($kinds.Count -eq 0) { $problem = 'No such line was found.' }
    else {
        foreach ($k in $kinds) {
            if ($valid -cnotcontains $k) {
                # the kind words come from the brief (untrusted text): only a short, plain-character copy of a bad word goes back to the model
                $shown = ($k -creplace '[^a-z0-9-]', ''); if ($shown.Length -gt 20) { $shown = $shown.Substring(0, 20) }
                $problem = "'$shown' is not a kind of this agent."; break
            }
        }
    }
    if ($problem) {
        [Console]::Error.WriteLine("BLOCKED: the brief for $base must start with a first line 'Task kind: <kind>'. $problem Valid kinds: $($valid -join ', ') (several kinds separated by commas when the task mixes them). Example first line: 'Task kind: $($valid[0])'. Re-issue the call with that line added; nothing else changes.")
        exit 2
    }
    exit 0
} catch {
    exit 0
}
