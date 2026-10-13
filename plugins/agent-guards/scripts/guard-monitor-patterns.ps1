# PreToolUse hook (Bash). Blocks FOREGROUND monitor-style commands that stream or poll into the conversation:
# tail -f, watch, Get-Content -Wait, docker/kubectl/journalctl logs -f, and unbounded `while true` loops.
# Background runs (run_in_background=true) are allowed. Fail-open on any internal error.
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if ($in.tool_name -ne 'Bash') { exit 0 }
    if ($in.tool_input.run_in_background -eq $true) { exit 0 }
    $cmd = [string]$in.tool_input.command
    # ignore text inside quotes (commit messages, grep patterns, echo strings)
    $c = [regex]::Replace($cmd, "'[^']*'|`"[^`"]*`"", '""')

    $reason = $null
    if ($c -match '\btail\s+(-[A-Za-z]*[fF][A-Za-z]*|--follow)\b') { $reason = '`tail -f`' }
    elseif ($c -match '(^|[;&|(]\s*|\b(sudo|timeout\s+\S+|nohup|env)\s+)watch\s') { $reason = '`watch`' }
    elseif ($c -match '(?i)get-content\b.*\s-wait\b') { $reason = '`Get-Content -Wait`' }
    elseif ($c -match '(?i)\b(docker(\s+compose)?|kubectl|journalctl)\b.*\s(-f|--follow)\b') { $reason = 'a follow-mode log command (`logs -f`)' }
    elseif ($c -match '\bwhile\s+(true|:|\[\s*1\s*\])\b' -and $c -notmatch '\b(break|exit)\b' -and $c -notmatch '\btimeout\b') { $reason = 'an unbounded `while true` loop' }
    elseif ($c -match '\buntil\s+false\b' -and $c -notmatch '\b(break|exit)\b') { $reason = 'an unbounded `until false` loop' }

    if ($reason) {
        [Console]::Error.WriteLine("BLOCKED: $reason in the foreground streams or polls output into the conversation and re-bills the whole context on every turn. " +
            "Use ONE of: (a) Bash with run_in_background=true and a command that exits when the condition is true, e.g. [until grep -q READY app.log; do sleep 1; done] (a single completion notification); " +
            "(b) the Monitor tool with a filtered stream, e.g. [tail -f app.log | grep --line-buffered -E 'ERROR|Traceback|FAILED|READY'], whose filter covers failure states as well as success; " +
            "(c) a bounded check that prints a few lines and exits, e.g. [tail -n 20 app.log].")
        exit 2
    }
    exit 0
} catch { exit 0 }
