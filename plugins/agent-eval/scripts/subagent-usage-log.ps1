# SubagentStop hook. Appends ONE metadata record per finished subagent run to agent-usage.jsonl and runs the Layer 1
# mechanical contract checks (deterministic, no model). Metadata only: no prompts, no answers, no file content, and never a matched secret value.
# Fails open: any error exits 0 and never blocks the agent. Related: agent-usage-report.py, agent-eval/agent_eval.py.
#
# Flags are recorded as { code, sev (fail|warn|info), detail }.  fail/warn make the run a review candidate.
param([string]$SelfTestInput = '')
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
function Get-Flags {
    param([string]$Output, [string]$AgentType, [string]$Cwd, [bool]$HasHandback, [int]$BlockedCount, [string]$TaskKind = '')
    $flags = New-Object System.Collections.ArrayList
    $AgentType = ($AgentType -replace '^.*:', '')
    function Add-Flag($code, $sev, $detail) { [void]$flags.Add([ordered]@{ code = $code; sev = $sev; detail = $detail }) }

    if (-not $HasHandback) { Add-Flag 'no_final_answer' 'fail' 'run ended without a SubagentHandback result' }
    elseif ($Output.Trim().Length -lt 15) { Add-Flag 'empty_output' 'fail' ('answer is ' + $Output.Trim().Length + ' characters') }
    if ($BlockedCount -gt 0) { Add-Flag 'guard_blocked' 'info' ("$BlockedCount tool call(s) were blocked by a hook") }
    if ($Output.Length -gt 20000) { Add-Flag 'oversized_output' 'warn' ('answer is ' + $Output.Length + ' characters') }
    if (-not $HasHandback -or $Output.Trim().Length -lt 15) { return $flags }

    # --- secrets: report kind only, never the value
    $secretKinds = [ordered]@{
        'aws_access_key' = 'AKIA[0-9A-Z]{16}'; 'sonarqube_token' = 'squ_[0-9a-f]{20,}'; 'github_token' = 'gh[pousr]_[A-Za-z0-9]{30,}'
        'slack_token' = 'xox[abprs]-[A-Za-z0-9-]{10,}'; 'private_key_block' = '-----BEGIN [A-Z ]*PRIVATE KEY-----'
        'credential_in_url' = '://[^/\s:@]+:[^@\s]{4,}@'; 'password_assignment' = '(?i)\bpassword\s*[=:]\s*[^\s<`"'']{6,}'
    }
    foreach ($k in $secretKinds.Keys) { if ($Output -cmatch $secretKinds[$k]) { Add-Flag 'secret_pattern' 'fail' "output contains something shaped like: $k" } }

    # --- verdicts the agents are forbidden to give
    $forbidden = @('\bno known vulnerabilit', '(?<!not )(?<!n''t )(?<!never )\b(is|are) (now )?(safe|secure)\b', '\bsafe to (ship|upgrade|deploy|use)\b', '\b(is|are) (fully )?(part 11 )?compliant\b')
    foreach ($f in $forbidden) {
        $m = [regex]::Match($Output, $f, 'IgnoreCase')
        if ($m.Success) {
            $ctx = $Output.Substring([math]::Max(0, $m.Index - 40), [math]::Min(80, $Output.Length - [math]::Max(0, $m.Index - 40)))
            if ($ctx -match '(?i)(never|not|n''t|no)\s+(say|says|write|writes|mean|means|a verdict|determin)') { continue }
            Add-Flag 'forbidden_phrase' 'warn' ('matched: ' + $m.Value.Trim()); break
        }
    }

    # --- JSON validity when the answer is JSON
    $t = $Output.Trim(); $fenced = $false
    if ($t -match '^```(?:json)?\s*([\s\S]*?)\s*```$') { $t = $Matches[1]; $fenced = $true }
    $looksJson = ($t.StartsWith('{') -or $t.StartsWith('['))
    if ($looksJson) { try { [void]($t | ConvertFrom-Json) } catch { Add-Flag 'json_invalid' 'fail' 'answer starts like JSON but does not parse' } }

    # --- reconciliation: figures must agree, and required footers must exist (not for JSON-only answers)
    foreach ($m in [regex]::Matches($Output, '(?i)expected\s+(\d+)\s*/\s*listed\s+(\d+)')) {
        if ($m.Groups[1].Value -ne $m.Groups[2].Value) { Add-Flag 'reconciliation_mismatch' 'fail' ('expected ' + $m.Groups[1].Value + ' / listed ' + $m.Groups[2].Value) }
    }
    # merged agents: the `Task kind:` line of the brief says which contract applies ($kd is that line, lower case, at most 40 characters)
    # whole words only: `roadmap` is not `map`; text after the kind words (the pattern may run on into the sentence) is ignored by the exact comparison
    $kw = @($TaskKind.ToLowerInvariant() -split '[, ]+' | Where-Object { $_ })
    if ($AgentType -eq 'contracts-reader') { $recon = ($kw -contains 'schema' -or $kw -contains 'api-spec'); $cov = $recon }
    elseif ($AgentType -eq 'code-explorer') { $recon = $false; $cov = ($kw -contains 'locate' -or $kw -contains 'map' -or $kw -contains 'inventory') }
    else {
        $recon = @('schema-reader', 'contract-reader', 'pipeline-reader') -contains $AgentType
        $cov = @('schema-reader', 'contract-reader', 'pipeline-reader', 'inventory-extractor', 'module-mapper', 'repo-scout') -contains $AgentType
    }
    if (-not $looksJson -and $recon -and $Output -notmatch '(?i)reconciliation') { Add-Flag 'footer_missing' 'warn' 'no Reconciliation line' }
    if (-not $looksJson -and $cov -and $Output -notmatch '(?i)coverage') { Add-Flag 'footer_missing' 'warn' 'no Coverage line' }

    # --- citations: absolute paths only; the file must exist and the line must be inside it
    $seen = @{}; $n = 0
    foreach ($m in [regex]::Matches($Output, '((?:(?<![A-Za-z0-9])[A-Za-z]:[/\\]|(?<![A-Za-z0-9._~/\\-])/)[^\s`''"|<>*?():]+?\.[A-Za-z0-9]{1,8}):(\d+)(?:[-,](\d+))?')) {
        $path = $m.Groups[1].Value; $line = [int]$m.Groups[2].Value; $key = "$path`:$line"
        if ($seen.ContainsKey($key)) { continue }; $seen[$key] = 1; $n++; if ($n -gt 80) { break }
        $win = if ([System.IO.Path]::DirectorySeparatorChar -eq [char]92) { $path -replace '/', '\' } else { $path }
        if (-not (Test-Path -LiteralPath $win -PathType Leaf)) { Add-Flag 'citation_file_missing' 'fail' ("file not found: $path"); continue }
        $len = (Get-Item -LiteralPath $win).Length
        if ($len -gt 5MB) { continue }
        $count = 0; foreach ($l in [System.IO.File]::ReadLines($win)) { $count++ }
        if ($line -gt $count -or $line -lt 1) { Add-Flag 'citation_line_out_of_range' 'fail' ("$path`:$line but the file has $count lines") }
    }
    return $flags
}

function Get-SubagentRecord {
    param($In)
    $tp = [string]$In.agent_transcript_path
    $calls = @{}; $models = @{}; $tools = @{}; $first = $null; $last = $null; $toolCalls = 0
    $output = ''; $hasHandback = $false; $blocked = 0
    if ($tp -and (Test-Path -LiteralPath $tp)) {
        foreach ($line in [System.IO.File]::ReadLines($tp)) {
            if (-not $line.Trim()) { continue }
            try { $o = $line | ConvertFrom-Json } catch { continue }
            if ($o.timestamp) {
                $t = [datetime]::Parse([string]$o.timestamp, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind)
                if (-not $first -or $t -lt $first) { $first = $t }
                if (-not $last -or $t -gt $last) { $last = $t }
            }
            if ($o.type -eq 'assistant' -and $o.message) {
                $mid = [string]$o.message.id; if (-not $mid) { $mid = [string]$o.uuid }
                if ($o.message.usage) { $calls[$mid] = $o.message.usage }
                if ($o.message.model) { $models[[string]$o.message.model] = 1 }
                if ($o.message.content -is [System.Array]) {
                    foreach ($b in $o.message.content) {
                        if ($b.type -ne 'tool_use') { continue }
                        if ($b.name -eq 'SubagentHandback') { $hasHandback = $true; $output = [string]$b.input.message }
                        else { $toolCalls++; $tools[[string]$b.name] = 1 + [int]$tools[[string]$b.name] }
                    }
                }
            } elseif ($o.type -eq 'user' -and $o.message.content -is [System.Array]) {
                foreach ($b in $o.message.content) {
                    if ($b.type -eq 'tool_result' -and $b.is_error -eq $true -and ([string]($b.content | ConvertTo-Json -Compress -Depth 4)) -match 'BLOCKED') { $blocked++ }
                }
            }
        }
    }
    $inT = 0; $outT = 0; $cr = 0; $cw = 0
    foreach ($u in $calls.Values) { $inT += [int]$u.input_tokens; $outT += [int]$u.output_tokens; $cr += [int]$u.cache_read_input_tokens; $cw += [int]$u.cache_creation_input_tokens }
    # ESTIMATE ONLY: Haiku 5.5 list price per MTok: input 0.10, output 0.50 (<=100k prompts); cache read assumed 10% of input, cache write assumed 125%.
    $cost = [math]::Round(($inT * 0.10 + $cw * 0.125 + $cr * 0.01 + $outT * 0.50) / 1e6, 5)
    $dur = $null; if ($first -and $last) { $dur = [math]::Round(($last - $first).TotalSeconds, 1) }
    $sha = $null; if ($tp -and (Test-Path -LiteralPath $tp)) { $sha = (Get-FileHash -LiteralPath $tp -Algorithm SHA256).Hash }
    # the first `Task kind: ...` in the transcript is the brief's own line; empty when there is none
    $taskKind = ''
    # only the first lines are read (the brief is the first user message; a transcript can be large); case-sensitive, like the shell version
    if ($tp -and (Test-Path -LiteralPath $tp)) { try { $m = [regex]::Match((@(Get-Content -LiteralPath $tp -TotalCount 20) -join "`n"), 'Task kind: ([a-z, -]{1,40})'); if ($m.Success) { $taskKind = $m.Groups[1].Value } } catch { } }
    $flags = [System.Collections.ArrayList]@(Get-Flags -Output $output -AgentType ([string]$In.agent_type) -Cwd ([string]$In.cwd) -HasHandback $hasHandback -BlockedCount $blocked -TaskKind $taskKind)
    # secret-guard events for this agent (hooks/secret-guard-audit.jsonl holds kinds and counts only)
    try {
        $sg = Join-Path (Get-KitData) 'audit/secret-guard-audit.jsonl'
        if ($env:SECRET_GUARD_AUDIT) { $sg = $env:SECRET_GUARD_AUDIT }
        if (Test-Path -LiteralPath $sg) {
            foreach ($l in [System.IO.File]::ReadLines($sg)) {
                if ($l.IndexOf([string]$In.agent_id, [StringComparison]::Ordinal) -lt 0) { continue }
                $e = $l | ConvertFrom-Json
                if ($e.agent_id -ne [string]$In.agent_id) { continue }
                if ($e.action -eq 'redacted') { [void]$flags.Add([ordered]@{ code = 'secret_redacted'; sev = 'warn'; detail = ("$($e.count) value(s) redacted at hand-back: " + ($e.kinds -join ', ')) }) }
                elseif ($e.action -eq 'blocked') { [void]$flags.Add([ordered]@{ code = 'secret_exfil_blocked'; sev = 'fail'; detail = ("$($e.tool) call blocked: " + ($e.kinds -join ', ')) }) }
            }
        }
    } catch {}
    $flagged = [bool](@($flags | Where-Object { $_.sev -ne 'info' }).Count)
    return [ordered]@{
        schema = 'agent-usage/2'; type = 'run'; ts = (Get-Date).ToUniversalTime().ToString('o')
        session_id = [string]$In.session_id; agent_id = [string]$In.agent_id; agent_type = [string]$In.agent_type
        effort = [string]$In.effort.level; models = @($models.Keys); cwd = [string]$In.cwd
        duration_s = $dur; api_calls = $calls.Count; tool_calls = $toolCalls; tools = $tools
        tokens = [ordered]@{ input = $inT; cache_write = $cw; cache_read = $cr; output = $outT }
        est_cost_usd = $cost; output_chars = $output.Length; flagged = $flagged; flags = @($flags)
        transcript = $tp; transcript_sha256 = $sha
    }
}

try {
    if ($SelfTestInput) { $in = Get-Content -LiteralPath $SelfTestInput -Raw | ConvertFrom-Json } else { $in = [Console]::In.ReadToEnd() | ConvertFrom-Json }
    if (-not $in.agent_id) { exit 0 }
    $logFile = $env:AGENT_USAGE_LOG; if (-not $logFile) { $logFile = Join-Path (Get-KitData) 'usage/agent-usage.jsonl' }
    [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logFile))
    $rec = Get-SubagentRecord -In $in
    [System.IO.File]::AppendAllText($logFile, (($rec | ConvertTo-Json -Depth 6 -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    exit 0
} catch {
    try { Add-Content -LiteralPath ((Get-KitData) + '/hook-errors.log') -Value ("{0} subagent-usage-log run record not written: {1}" -f (Get-Date).ToString('o'), $_.Exception.Message) -Encoding UTF8 } catch { }
    exit 0
}
