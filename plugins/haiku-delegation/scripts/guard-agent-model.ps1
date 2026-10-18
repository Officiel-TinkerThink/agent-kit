# PreToolUse hook (Agent), registered by the haiku-delegation plugin. A subagent that is not one of the kit agents (general-purpose, Explore, Plan, no type at all)
# runs on the main model (Sonnet or Opus) unless the call says `model: "haiku"`: about 20 to 40 times the cost of Haiku. Such a call without a Haiku model is blocked
# with the message that fixes it. The kit agents pin Haiku in their own definition (haiku-pinned.txt) and are never blocked. Only the main agent's calls are checked.
# PowerShell twin of guard-agent-model.sh. Convenience guard, not a safety guard: any parse problem allows the call (fail-open).
# Main-agent calls of the built-in general-purpose type are routed to haiku-delegation:general-purpose instead of being checked (see below).
# Set AGENT_MODEL_GUARD=off in the environment to disable it (for a task that really needs another model); this also turns the routing off.
try {
    if ($env:AGENT_MODEL_GUARD -ceq 'off') { exit 0 }
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if ($null -eq $in -or $null -eq $in.tool_input) { exit 0 }   # empty or unexpected input: allow (fail-open)
    $id = [string]$in.agent_id
    $type = [string]$in.tool_input.subagent_type
    # A bare general-purpose call from the main agent is routed to haiku-delegation:general-purpose (pinned Haiku) by rewriting subagent_type through updatedInput.
    # AGENT_GENERAL_ROUTE=off turns the routing off. The JSON is written as UTF-8 bytes: the console code page would mangle non-ASCII text in the prompt.
    if (-not $id -or $id -eq 'false' -or $id -eq '0') {
        # no subagent_type at all runs as the built-in general-purpose, so it is routed too
        if (($type -ceq 'general-purpose' -or -not $type) -and $env:AGENT_GENERAL_ROUTE -cne 'off') {
            $in.tool_input | Add-Member -NotePropertyName subagent_type -NotePropertyValue 'haiku-delegation:general-purpose' -Force
            $out = [ordered]@{ hookSpecificOutput = [ordered]@{ hookEventName = 'PreToolUse'; permissionDecision = 'allow'; permissionDecisionReason = 'general-purpose routed to haiku-delegation:general-purpose'; updatedInput = $in.tool_input } }
            $bytes = [Text.Encoding]::UTF8.GetBytes(($out | ConvertTo-Json -Depth 10 -Compress))
            $stdout = [Console]::OpenStandardOutput()
            $stdout.Write($bytes, 0, $bytes.Length)
            $stdout.Flush()
            exit 0
        }
    }
    if ($id -and $id -ne 'false' -and $id -ne '0') {
        # a subagent (agent_id present) that calls the built-in general-purpose type is blocked: routing only applies to the main agent
        if (($type -ceq 'general-purpose' -or -not $type) -and $env:AGENT_GENERAL_ROUTE -cne 'off') {
            [Console]::Error.WriteLine("BLOCKED: a subagent may not call the built-in general-purpose type. Call haiku-delegation:general-purpose or a kit agent instead. To allow it on purpose, set AGENT_GENERAL_ROUTE=off.")
            exit 2
        }
        exit 0
    }
    $base = $type.Substring($type.LastIndexOf(':') + 1)
    # the bare built-in general-purpose is never pinned: only haiku-delegation:general-purpose is (a bare name means the built-in agent)
    if ($base -and -not ($base -ceq 'general-purpose' -and $type -ceq $base)) {
        foreach ($row in (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'haiku-pinned.txt') -ErrorAction Stop)) {
            $f = @($row.Trim() -split '\s+')
            if ($f.Count -ge 1 -and -not $f[0].StartsWith('#') -and $f[0] -ceq $base) { exit 0 }
        }
    }
    $shown = ($type -creplace '[^A-Za-z0-9:_-]', ''); if ($shown.Length -gt 40) { $shown = $shown.Substring(0, 40) }
    if (-not $shown) { $shown = '(no type)' }
    $model = [string]$in.tool_input.model
    if (-not $model.ToLowerInvariant().Contains('haiku')) {
        [Console]::Error.WriteLine("BLOCKED: the agent '$shown' would run on the main model (Sonnet or Opus), about 20 to 40 times the cost of Haiku. Re-issue the call with the parameter model: `"haiku`", or use a kit agent for the job (for example haiku-delegation:code-explorer for reading). Keep the task atomic: one question and a few files per agent; split anything bigger into several agents launched in one message. To allow another model on purpose, set AGENT_MODEL_GUARD=off.")
        exit 2
    }
    # a brief that holds several units of work: 4 or more numbered steps, or more than 4000 characters (AGENT_BRIEF_GUARD=off disables this check)
    if ($env:AGENT_BRIEF_GUARD -ceq 'off') { exit 0 }
    $prompt = [string]$in.tool_input.prompt
    $steps = ([regex]::Matches($prompt, '(?m)^[ \t]*[0-9]+[.)][ \t]')).Count
    $size = [Text.Encoding]::UTF8.GetByteCount($prompt)
    if ($steps -ge 4 -or $size -gt 4000) {
        [Console]::Error.WriteLine("BLOCKED: the brief for '$shown' holds several units of work ($steps numbered steps, $size characters). A unit of work is the smallest piece of work that cannot be split any further, whether the pieces could run in parallel or one after another: one question or one deliverable with one result. Launch one agent per unit (independent units in the same message), each with a short brief: the one question, absolute paths, the output format. Keep the integration and the edits yourself. To allow a long brief on purpose, set AGENT_BRIEF_GUARD=off.")
        exit 2
    }
    exit 0
} catch {
    exit 0
}
