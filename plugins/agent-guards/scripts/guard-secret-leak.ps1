# PreToolUse hook (matcher: SubagentHandback|WebFetch|WebSearch). Deterministic secret-leak gate for subagents.
#  * SubagentHandback (the ONLY way a subagent's answer reaches the main model): secret values are REDACTED from the message (updatedInput),
#    whether they match a known credential format OR equal a secret-looking value the agent itself read in this run (taint taken from its transcript).
#  * WebFetch / WebSearch: a call whose URL, query or prompt contains such a value is BLOCKED (exfiltration).
# Audit: <kit data>/audit/secret-guard-audit.jsonl records agent, tool, count and KINDS only. It never stores a secret value.
# Known limits: values with no recognisable format that sit outside key=value / flag / URL-credential / CLI-positional shapes are not detected;
# pure lowercase values of 9 characters or fewer are treated as ordinary words; redaction is exact-match (a re-encoded value, e.g. base64 of a secret, is not caught).
param([string]$SelfTestInput = '')

$script:Kinds = New-Object System.Collections.ArrayList
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

function Test-IsReference([string]$v) {
    if ($v -match '^(\$|\{\{|<|%|@\()') { return $true }
    if ($v -match '(?i)^(os\.environ|environ|getenv|process\.env|secrets\.|vars\.|env\.|credentials\(|system\.getenv|ENV\[|params\.|var\.|data\.|file\()') { return $true }
    if ($v -match '\$\{|\{\{') { return $true }
    if ($v -match '(?i)^(x{3,}|\*{3,}|\.{3,}|changeme|change_me|your[-_].*|example.*|placeholder|redacted|none|null|true|false|string|required|todo|secret|password|token|apikey|api_key)$') { return $true }
    if ($v -match '<redacted') { return $true }
    return $false
}

function Test-WorthRedacting([string]$v) {
    if ($v.Length -lt 6) { return $false }
    if ($v -cmatch '^[a-z]{1,9}$') { return $false }        # ordinary lowercase word
    if ($v -match '^[0-9a-fA-F]{32,}$') { return $false }   # hash or id, not a credential by shape
    return $true
}

# Returns a hashtable value -> kind for every secret-looking value in $Text.
function Find-SecretValues([string]$Text) {
    $found = @{}
    if (-not $Text) { return $found }
    function Add-Val($val, $kind) { $val = $val.Trim().TrimEnd('.', ',', ')', ']', '}'); if ((Test-WorthRedacting $val) -and -not (Test-IsReference $val)) { $found[$val] = $kind } }
    $fixed = [ordered]@{
        'aws_access_key'   = 'A[KS]IA[0-9A-Z]{16}'
        'sonarqube_token'  = 'sq[upa]_[0-9a-f]{20,}'
        'github_token'     = 'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}'
        'slack_token'      = 'xox[abprs]-[A-Za-z0-9-]{10,}'
        'google_api_key'   = 'AIza[0-9A-Za-z_-]{35}'
        'jwt'              = 'eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}'
        'private_key'      = '-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)'
    }
    foreach ($k in $fixed.Keys) { foreach ($m in [regex]::Matches($Text, $fixed[$k])) { Add-Val $m.Value $k } }
    foreach ($m in [regex]::Matches($Text, '://[^/\s:@''"]+:([^@\s/''"]{3,})@')) { Add-Val $m.Groups[1].Value 'url_credential' }
    foreach ($m in [regex]::Matches($Text, '(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{16,})')) { Add-Val $m.Groups[1].Value 'bearer_token' }
    foreach ($m in [regex]::Matches($Text, '(?i)\bBasic\s+([A-Za-z0-9+/=]{16,})')) { Add-Val $m.Groups[1].Value 'basic_auth' }
    # key = value where the KEY names a secret (credential ids / variable names / file paths are not secrets)
    $assign = '(?i)([\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key|credential|auth[_-]?key)[\w.-]*)["'']?\s*[:=]\s*["'']?([^\s"''`,;)}\]]{6,})'
    foreach ($m in [regex]::Matches($Text, $assign)) {
        if ($m.Groups[1].Value -match '(?i)(id|ids|name|names|file|path|dir|ref|var|variable|env|type|mode|policy|header|field|label|prefix|suffix|url|uri|endpoint|host|provider|store|manager|usage|scope|expiry|expires|ttl)$') { continue }
        Add-Val $m.Groups[2].Value 'secret_assignment'
    }
    foreach ($m in [regex]::Matches($Text, '(?i)(?<![\w-])--?(?:password|passwd|token|secret|api-key|apikey|client-secret)(?:[= ]+)["'']?([^\s"''`]{6,})')) { Add-Val $m.Groups[1].Value 'cli_credential_flag' }
    foreach ($m in [regex]::Matches($Text, '(?i)\balias\s+set\s+\S+\s+\S+\s+(\S{4,})\s+(\S{4,})')) { Add-Val $m.Groups[1].Value 'cli_positional_credential'; Add-Val $m.Groups[2].Value 'cli_positional_credential' }
    foreach ($m in [regex]::Matches($Text, '(?i)\bcurl\b[^\r\n]*\s-u\s+["'']?[^\s:''"]+:([^\s"'']{4,})')) { Add-Val $m.Groups[1].Value 'cli_basic_auth' }
    return $found
}

function Get-AgentTaint($In) {
    $taint = @{}
    try {
        $tp = [string]$In.transcript_path
        if (-not $tp -or -not $In.agent_id -or -not $In.session_id) { return $taint }
        $agentTx = Join-Path (Join-Path (Join-Path ([System.IO.Path]::GetDirectoryName($tp)) ([string]$In.session_id)) 'subagents') ('agent-' + [string]$In.agent_id + '.jsonl')
        if (-not (Test-Path -LiteralPath $agentTx)) { return $taint }
        $budget = 4MB
        foreach ($line in [System.IO.File]::ReadLines($agentTx)) {
            if ($budget -le 0) { break }
            if ($line.IndexOf('tool_result', [StringComparison]::Ordinal) -lt 0) { continue }
            try { $o = $line | ConvertFrom-Json } catch { continue }
            if ($o.type -ne 'user' -or $o.message.content -isnot [System.Array]) { continue }
            foreach ($b in $o.message.content) {
                if ($b.type -ne 'tool_result') { continue }
                $txt = ''
                if ($b.content -is [string]) { $txt = $b.content }
                elseif ($b.content -is [System.Array]) { $txt = ($b.content | ForEach-Object { if ($_.text) { $_.text } }) -join "`n" }
                if ($txt.Length -gt 0 -and $txt -notmatch 'Report delivered to your caller') { $budget -= $txt.Length; foreach ($kv in (Find-SecretValues $txt).GetEnumerator()) { $taint[$kv.Key] = $kv.Value } }
            }
        }
    } catch {}
    return $taint
}

function Write-Audit($In, [string]$Tool, [int]$Count, $Kinds, [string]$Action) {
    try {
        $f = $env:SECRET_GUARD_AUDIT; if (-not $f) { $f = Join-Path (Get-KitData) 'audit/secret-guard-audit.jsonl' }
        [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $f))
        $rec = [ordered]@{ schema = 'secret-guard/1'; ts = (Get-Date).ToUniversalTime().ToString('o'); session_id = [string]$In.session_id; agent_id = [string]$In.agent_id; agent_type = [string]$In.agent_type
                           tool = $Tool; action = $Action; count = $Count; kinds = @($Kinds | Sort-Object -Unique) }
        [System.IO.File]::AppendAllText($f, (($rec | ConvertTo-Json -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    } catch { try { Add-Content -LiteralPath ((Get-KitData) + '/hook-errors.log') -Value ("{0} guard-secret-leak audit write failed: {1}" -f (Get-Date).ToString('o'), $_.Exception.Message) -Encoding UTF8 } catch { } }
}

$in = $null
try {
    if ($SelfTestInput) { $in = Get-Content -LiteralPath $SelfTestInput -Raw | ConvertFrom-Json } else { $in = [Console]::In.ReadToEnd() | ConvertFrom-Json }
} catch { exit 0 }

try {
    $tool = [string]$in.tool_name
    if ($tool -eq 'SubagentHandback') {
        $msg = [string]$in.tool_input.message
        if (-not $msg) { exit 0 }
        $vals = Find-SecretValues $msg
        foreach ($kv in (Get-AgentTaint $in).GetEnumerator()) { if ($msg.Contains($kv.Key)) { $vals[$kv.Key] = $kv.Value } }
        $present = @($vals.Keys | Where-Object { $msg.Contains($_) } | Sort-Object { $_.Length } -Descending)
        if ($present.Count -eq 0) { exit 0 }
        $new = $msg; $kinds = @()
        foreach ($v in $present) { $new = $new.Replace($v, '<redacted:secret>'); $kinds += $vals[$v] }
        $new = $new.TrimEnd() + "`n`n[secret-guard: $($present.Count) secret value(s) were redacted from this answer by a hook. Use the cited source locations; the values themselves are never passed on.]"
        $ui = @{}
        foreach ($p in $in.tool_input.PSObject.Properties) { $ui[$p.Name] = $p.Value }
        $ui['message'] = $new
        Write-Audit $in $tool $present.Count $kinds 'redacted'
        [Console]::Out.WriteLine((@{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'allow'; permissionDecisionReason = 'secret-guard: secret values redacted'; updatedInput = $ui } } | ConvertTo-Json -Depth 6 -Compress))
        exit 0
    }
    if ($tool -eq 'WebFetch' -or $tool -eq 'WebSearch') {
        $blob = (@([string]$in.tool_input.url, [string]$in.tool_input.query, [string]$in.tool_input.prompt) -join "`n")
        $vals = Find-SecretValues $blob
        $hit = @($vals.Keys | Where-Object { $blob.Contains($_) })
        if ($in.agent_id) { foreach ($kv in (Get-AgentTaint $in).GetEnumerator()) { if ($blob.Contains($kv.Key)) { $hit += $kv.Key; $vals[$kv.Key] = $kv.Value } } }
        if ($hit.Count -gt 0) {
            Write-Audit $in $tool $hit.Count @($hit | ForEach-Object { $vals[$_] }) 'blocked'
            [Console]::Error.WriteLine("BLOCKED by secret-guard: this $tool call contains $($hit.Count) value(s) that look like credentials ($((@($hit | ForEach-Object { $vals[$_] }) | Sort-Object -Unique) -join ', ')). Remove them and retry; credentials must never be sent to a web service.")
            exit 2
        }
    }
    exit 0
} catch {
    if ([string]$in.tool_name -eq 'SubagentHandback') { [Console]::Error.WriteLine("BLOCKED by secret-guard: internal error while checking the answer ($($_.Exception.Message)); the answer was withheld. Retry the hand-back with the answer shortened to path:line references only."); exit 2 }
    exit 0
}
