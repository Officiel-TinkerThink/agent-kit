# SubagentStart hook (agent-eval). Appends ONE metadata line per started subagent to <KIT_DATA>/usage/agent-starts.jsonl: ids, agent type, time and the path where the
# subagent's transcript will be. A run the user stops never reaches SubagentStop, so it never gets a usage record; this line lets the annotator find such a run.
# Metadata only (no prompt, no answer). Fails open: any problem writes to hook-errors.log and exits 0; it never blocks the subagent and prints nothing.
# PowerShell twin of subagent-start-log.sh. Override the file with AGENT_START_LOG.
function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $(if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
try {
    $in = $null
    try { $in = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { exit 0 }   # input that is not JSON: nothing to record (the sh twin is silent too)
    $id = [string]$in.agent_id
    if ($id -cnotmatch '^[A-Za-z0-9_-]{1,100}$') { exit 0 }
    $sid = [string]$in.session_id
    if ($sid -cnotmatch '^[A-Za-z0-9_-]{1,100}$') { $sid = '' }
    $tp = [string]$in.transcript_path
    $tx = ''
    # the subagent's transcript sits next to the session transcript: <folder of the session file>/<session id>/subagents/agent-<id>.jsonl
    if ($tp -and $sid) {
        $dir = [System.IO.Path]::GetDirectoryName($tp)
        if ($dir) { $tx = ([System.IO.Path]::Combine($dir, $sid, 'subagents', "agent-$id.jsonl")) -replace '\\', '/' }   # forward slashes, as the sh twin writes them
    }
    $log = $env:AGENT_START_LOG
    if (-not $log) { $log = (Get-KitData) + '/usage/agent-starts.jsonl' }
    $rec = [ordered]@{
        schema = 'agent-start/1'; type = 'start'; ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ', [Globalization.CultureInfo]::InvariantCulture); session_id = $sid; agent_id = $id
        agent_type = [string]$in.agent_type; cwd = [string]$in.cwd; transcript = $tx
    }
    $folder = Split-Path -Parent $log
    if ($folder -and -not (Test-Path -LiteralPath $folder)) { [void](New-Item -ItemType Directory -Path $folder -Force) }
    [System.IO.File]::AppendAllText($log, (($rec | ConvertTo-Json -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    exit 0
} catch {
    try { Add-Content -LiteralPath ((Get-KitData) + '/hook-errors.log') -Value ((Get-Date).ToUniversalTime().ToString('o') + " subagent-start-log: start record not written: $($_.Exception.Message)") -ErrorAction Stop } catch { }
    exit 0
}
