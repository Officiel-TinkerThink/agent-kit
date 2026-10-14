# PreToolUse hook (matcher: Read|Bash). Blocks whole-file reads of large text files in the MAIN
# conversation and redirects Claude to the Haiku-backed `bulk-reader` subagent.
# Fails open on any internal error (cost optimisation only - not a compliance control).
# Threshold: env BULK_READ_MIN_LINES (default 200). Audit trail: <kit data>/audit/bulk-read-audit.jsonl.
$ErrorActionPreference = 'Stop'
$MinLines = 200
if ($env:BULK_READ_MIN_LINES -match '^\d+$') { $MinLines = [int]$env:BULK_READ_MIN_LINES }
$SkipExt = '.png','.jpg','.jpeg','.gif','.webp','.pdf','.ipynb','.svg'
function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $(if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
function Test-AgentIs([string]$Type, [string[]]$Names) {
    # plugin agents report agent_type as "<plugin>:<name>"; user-level agents report "<name>"
    foreach ($n in $Names) { if ($Type -eq $n -or $Type.EndsWith(':' + $n)) { return $true } }
    return $false
}

function Write-Audit([string]$Tool, [string]$Path, [int]$Lines, [string]$Decision, [string]$Session) {
    try {
        $rec = [ordered]@{
            ts = (Get-Date).ToUniversalTime().ToString('o'); user = $(if ($env:USERNAME) { $env:USERNAME } else { $env:USER }); session = $Session
            tool = $Tool; path = $Path; lines = $Lines; threshold = $MinLines; decision = $Decision
        }
        $f = Join-Path (Get-KitData) 'audit/bulk-read-audit.jsonl'
        [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $f))
        [System.IO.File]::AppendAllText($f, (($rec | ConvertTo-Json -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    } catch { try { Add-Content -LiteralPath ((Get-KitData) + '/hook-errors.log') -Value ("{0} check-bulk-read audit write failed: {1}" -f (Get-Date).ToString('o'), $_.Exception.Message) -Encoding UTF8 } catch { } }
}

function Get-LineCount([string]$Path) {
    $n = 0
    $sr = [System.IO.StreamReader]::new($Path)
    try { while ($null -ne $sr.ReadLine()) { $n++ } } finally { $sr.Dispose() }
    return $n
}

function Resolve-Target([string]$Raw, [string]$Cwd) {
    $p = $Raw.Trim('"', "'")
    if ([System.IO.Path]::DirectorySeparatorChar -eq [char]92 -and $p -match '^/([a-zA-Z])/(.*)$') { $p = "$($Matches[1]):\$($Matches[2])" }   # Git Bash style /d/core/...
    if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $Cwd $p }
    return $p
}

try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if ($in.agent_id) { exit 0 }                       # subagents (incl. bulk-reader) may read freely

    $target = $null
    if ($in.tool_name -eq 'Read') {
        if ($null -ne $in.tool_input.offset -or $null -ne $in.tool_input.limit) { exit 0 }   # targeted read
        $target = $in.tool_input.file_path
    }
    elseif ($in.tool_name -eq 'Bash') {
        $cmd = [string]$in.tool_input.command
        if ($cmd -match '[|;&<>`$]') { exit 0 }        # piped / compound / redirected = targeted use
        if ($cmd -match '^\s*(cat|less|more)\s+("[^"]+"|''[^'']+''|\S+)\s*$') { $target = $Matches[2] }
        else { exit 0 }                                # head/tail already bounded; anything else passes
    }
    if (-not $target) { exit 0 }

    $full = Resolve-Target $target $in.cwd
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { exit 0 }
    if ($SkipExt -contains [System.IO.Path]::GetExtension($full).ToLowerInvariant()) { exit 0 }
    if ((Get-Item -LiteralPath $full).Length -lt ($MinLines * 20)) { exit 0 }   # cheap pre-filter (<~20 B/line)

    $lines = Get-LineCount $full
    if ($lines -le $MinLines) { exit 0 }

    Write-Audit $in.tool_name $full $lines 'blocked' $in.session_id
    [Console]::Error.WriteLine(
        "BLOCKED (intentional guard, not a hook failure): '$full' has $lines lines (limit $MinLines). Do not read it whole in the main context. " +
        "Delegate with the Agent tool: subagent_type='bulk-reader', prompt = the exact question + absolute file path(s). " +
        "Reading the file in chunks is always allowed, for any purpose (edits, exact line numbers, a code review or quality check): re-issue Read with offset/limit on the sections you need. Only whole-file reads over the limit are redirected.")
    exit 2
}
catch {
    Write-Audit 'hook-error' '' 0 "fail-open: $($_.Exception.Message)" ''
    exit 0
}
