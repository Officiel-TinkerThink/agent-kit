function Test-AgentIs([string]$Type, [string[]]$Names) {
    # plugin agents report agent_type as "<plugin>:<name>"; user-level agents report "<name>"
    foreach ($n in $Names) { if ($Type -eq $n -or $Type.EndsWith(':' + $n)) { return $true } }
    return $false
}
# PreToolUse hook (Bash), registered by the agent-guards plugin. Applies ONLY to the changelog-summarizer subagent:
# allow a single read-only git command (optionally `git -C <path> ...`); block everything else.
# Unparseable input fails open: the caller is unknown, and every other agent is out of scope. Fails closed once the
# caller is known to be changelog-summarizer.
$isSummarizer = $false
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if (-not (Test-AgentIs ([string]$in.agent_type) @('changelog-summarizer'))) { exit 0 }
    $isSummarizer = $true
    $cmd = [string]$in.tool_input.command
    $ro = '^\s*git\s+(-C\s+("[^"]+"|''[^'']+''|[^\s;&|<>`$"'']+)\s+)?(--no-pager\s+)?(diff|log|show|status|shortlog|blame|rev-parse|ls-files)(\s|$)'
    if ($cmd -match $ro -and $cmd -cnotmatch '[;&|<>`$]|--output|--ext-diff|\s-c\s') { exit 0 }
    [Console]::Error.WriteLine("BLOCKED: only a single read-only git command (diff, log, show, status, shortlog, blame, rev-parse, ls-files; optional -C <path>) is allowed for changelog-summarizer.")
    exit 2
} catch { if ($isSummarizer) { [Console]::Error.WriteLine("BLOCKED: guard error"); exit 2 }; exit 0 }
