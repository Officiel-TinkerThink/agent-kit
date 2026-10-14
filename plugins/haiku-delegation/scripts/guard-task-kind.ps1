# PreToolUse hook (Agent), registered by the haiku-delegation plugin. The merged agents code-explorer and contracts-reader serve several kinds of task;
# the brief must start with `Task kind: <kind>` (several kinds separated by commas). Without it the agent has to guess the section and the usage log cannot
# pick the footer checks. A brief with no valid kind line is blocked once, with the message the main agent needs to fix it.
# PowerShell twin of guard-task-kind.sh. Convenience guard, not a safety guard: any parse problem allows the call (fail-open).
# Set TASK_KIND_GUARD=off in the environment to disable it.
try {
    if ($env:TASK_KIND_GUARD -eq 'off') { exit 0 }
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $type = [string]$in.tool_input.subagent_type
    $base = $type -replace '^.*:', ''
    $valid = switch ($base) {
        'code-explorer'    { @('locate', 'read', 'map', 'inventory', 'tests') }
        'contracts-reader' { @('schema', 'api-spec', 'migrations', 'api-match') }
        default            { exit 0 }
    }
    $prompt = [string]$in.tool_input.prompt
    $first = ($prompt -split "`r?`n" | Where-Object { $_.Trim() -ne '' } | Select-Object -First 1)
    $kinds = @()
    if ($first -match '^\s*Task kind:\s*(.*)$') { $kinds = @($Matches[1] -split '[,\s]+' | Where-Object { $_ }) }
    $problem = $null
    if ($kinds.Count -eq 0) { $problem = 'No such line was found.' }
    else { foreach ($k in $kinds) { if ($valid -notcontains $k) { $problem = "'$k' is not a kind of this agent."; break } } }
    if ($problem) {
        [Console]::Error.WriteLine("BLOCKED: the brief for $base must start with a first line 'Task kind: <kind>'. $problem Valid kinds: $($valid -join ', ') (several kinds separated by commas when the task mixes them). Example first line: 'Task kind: $($valid[0])'. Re-issue the call with that line added; nothing else changes.")
        exit 2
    }
    exit 0
} catch {
    exit 0
}
