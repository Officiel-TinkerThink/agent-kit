# PreToolUse hook (Write|Bash). Applies ONLY to the `annotator` subagent; everything else exits 0 untouched.
# The annotator may (a) create NEW .json files in agent-eval/inbox and (b) run exactly one command:
#   python <agent-eval>/annotate.py --file <agent-eval>/inbox/<name>.json
# Anything else is blocked. Fails CLOSED for the annotator (internal error -> block), open for every other agent.
$isAnnotator = $false
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
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if (-not (Test-AgentIs ([string]$in.agent_type) @('annotator'))) { exit 0 }
    $isAnnotator = $true
    $base = (Get-KitData) + '/eval/inbox/'
    $baseRe = [regex]::Escape((Get-KitData) + '/eval')
    $selfScript = Join-Path $PSScriptRoot 'annotate.py'
    $tool = [string]$in.tool_name

    if ($tool -eq 'Write') {
        $p = ([string]$in.tool_input.file_path) -replace '\\', '/'
        if ($p -notmatch ('^' + [regex]::Escape($base) + '[A-Za-z0-9_.-]+\.json$') -or $p -match '\.\.') {
            [Console]::Error.WriteLine("BLOCKED: the annotator may only write NEW .json files directly inside $base (letters, digits, _ . - in the name).")
            exit 2
        }
        if (Test-Path -LiteralPath ($p -replace '/', '\')) {
            [Console]::Error.WriteLine('BLOCKED: that file already exists; annotation files are never overwritten. Use a new unique file name.')
            exit 2
        }
        exit 0
    }
    if ($tool -eq 'Bash') {
        $cmd = ([string]$in.tool_input.command).Trim()
        $m = [regex]::Match($cmd, '^python3?\s+"?([^"\s]+/annotate\.py)"?\s+--file\s+"?(' + $baseRe + '/inbox/[A-Za-z0-9_.-]+\.json)"?$')
        if (-not $m.Success) {
            [Console]::Error.WriteLine("BLOCKED: the annotator may run only: python <plugin>/scripts/annotate.py --file ${base}<name>.json  (no pipes, chaining or other commands).")
            exit 2
        }
        # the script path must be THIS plugin's annotate.py (compared by content, so 8.3 or case differences in the path do not matter)
        $given = $m.Groups[1].Value -replace '/', '\'
        if (-not (Test-Path -LiteralPath $given -PathType Leaf) -or ((Get-FileHash -LiteralPath $given -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $selfScript -Algorithm SHA256).Hash)) {
            [Console]::Error.WriteLine('BLOCKED: that is not the annotate.py shipped with this plugin.')
            exit 2
        }
        if (-not (Test-Path -LiteralPath ($m.Groups[2].Value -replace '/', '\'))) {
            [Console]::Error.WriteLine('BLOCKED: write the annotation file first; it does not exist yet.')
            exit 2
        }
        exit 0
    }
    exit 0
} catch {
    if ($isAnnotator) { [Console]::Error.WriteLine("BLOCKED: the annotator guard hit an internal error and fails closed. ($($_.Exception.Message))"); exit 2 }
    exit 0
}
