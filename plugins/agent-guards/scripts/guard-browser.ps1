# PreToolUse hook (mcp__claude-in-chrome__*), registered by the agent-guards plugin. Applies ONLY to browser-explorer and browser-operator.
# browser-explorer: read-only. Tool allowlist; `computer` limited to screenshot|wait|scroll|scroll_to|zoom|hover.
# browser-operator: tool allowlist; every click/type/key/form_input must carry an action_summary, and a summary that names an
#   irreversible effect (submit, delete, send, pay, approve, sign, confirm, export, publish...) is blocked: the agent reports instead.
# Both: navigate / url must be http(s) (no file:, chrome:, javascript:, data:); optional host allowlist in <KIT_DATA>/browser-policy.json {"allowedHosts":[...]}.
# Every operator decision (allowed or blocked) is appended to <KIT_DATA>/audit/browser-actions.jsonl (typed text is never logged, only its length).
# The main thread is redirected to those agents for browser tools (override: AGENT_KIT_BROWSER_MAIN=allow); other agents are not affected (exit 0). Unparseable input fails open; for the two guarded agents an internal error fails closed.
$guarded = $false
function Test-AgentIs([string]$Type, [string[]]$Names) {
    # plugin agents report agent_type as "<plugin>:<name>"; user-level agents report "<name>"
    foreach ($n in $Names) { if ($Type -eq $n -or $Type.EndsWith(':' + $n)) { return $true } }
    return $false
}
function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $env:USERPROFILE '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
function Write-HookError([string]$Msg) {
    # best effort: a trace beside the audit log, and on stderr; never throws
    [Console]::Error.WriteLine("guard-browser: $Msg")
    try { Add-Content -LiteralPath ((Get-KitData) + '/hook-errors.log') -Value ("{0} guard-browser {1}" -f (Get-Date).ToString('o'), $Msg) -Encoding UTF8 } catch { }
}
function Add-BlockedRequest([string]$Kind, [string]$Value, [string]$Agent) {
    # feeds /kit-allow: what the user could approve; best effort, never throws
    try {
        $dir = (Get-KitData) + '/audit'
        [void](New-Item -ItemType Directory -Force -Path $dir)
        $rec = [ordered]@{ ts = (Get-Date).ToUniversalTime().ToString('o'); kind = $Kind; value = $Value.Substring(0, [Math]::Min(300, $Value.Length)); agent = $Agent }
        Add-Content -LiteralPath ($dir + '/blocked-requests.jsonl') -Value ($rec | ConvertTo-Json -Compress) -Encoding UTF8 -ErrorAction Stop
    } catch { }
}
function Write-Audit($in, [string]$tool, [string]$decision, [string]$reason) {
    try {
        $dir = (Get-KitData) + '/audit'
        [void](New-Item -ItemType Directory -Force -Path $dir)
        $ti = $in.tool_input
        $rec = [ordered]@{
            ts = (Get-Date).ToString('o'); agent = [string]$in.agent_type; session = [string]$in.session_id; tool = $tool; decision = $decision
            action = [string]$ti.action; summary = [string]$ti.action_summary; tabId = $ti.tabId; url = [string]$ti.url
            text_len = ([string]$ti.text).Length; reason = $reason
            policy_sha256 = $(try { $pf = (Get-KitData) + '/browser-policy.json'; if (Test-Path -LiteralPath $pf) { (Get-FileHash -Algorithm SHA256 -LiteralPath $pf).Hash.ToLower() } else { $null } } catch { $null })
        }
        Add-Content -LiteralPath ($dir + '/browser-actions.jsonl') -Value ($rec | ConvertTo-Json -Compress) -Encoding UTF8 -ErrorAction Stop
        return $true
    } catch {
        Write-HookError "audit write failed ($decision $tool): $($_.Exception.Message)"
        return $false
    }
}
function Block($in, [string]$tool, [bool]$audit, [string]$msg) {
    if ($audit) { [void](Write-Audit $in $tool 'blocked' $msg) }
    [Console]::Error.WriteLine("BLOCKED: $msg")
    exit 2
}
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $type = [string]$in.agent_type
    $isExplorer = Test-AgentIs $type @('browser-explorer')
    $isOperator = Test-AgentIs $type @('browser-operator')
    # Main thread: browser tool calls are redirected to the browser agents (raw page dumps and screenshots would fill the main context).
    # Set AGENT_KIT_BROWSER_MAIN=allow to let the main thread use the browser tools itself.
    if (-not ($isExplorer -or $isOperator)) {
        if ([string]::IsNullOrEmpty($type) -and ([string]$in.tool_name) -like 'mcp__claude-in-chrome__*' -and $env:AGENT_KIT_BROWSER_MAIN -ne 'allow') {
            [Console]::Error.WriteLine("BLOCKED: do not call the browser tools from the main thread. Delegate with the Agent tool: subagent_type='browser-explorer' to open and read pages (read-only), or 'browser-operator' for named click/fill steps. Put the exact URL(s), the question, and what to report in the prompt. (Set AGENT_KIT_BROWSER_MAIN=allow to override.)")
            exit 2
        }
        exit 0
    }
    $guarded = $true
    $full = [string]$in.tool_name
    if ($full -notlike 'mcp__claude-in-chrome__*') { exit 0 }
    $tool = $full.Substring('mcp__claude-in-chrome__'.Length)
    $ti = $in.tool_input

    $read = @('tabs_context_mcp', 'tabs_create_mcp', 'tabs_close_mcp', 'navigate', 'read_page', 'get_page_text', 'find', 'read_console_messages', 'read_network_requests', 'computer')
    $allowed = if ($isOperator) { $read + @('form_input') } else { $read }
    if ($allowed -notcontains $tool) {
        Block $in $tool $isOperator "$tool is not available to $type. Allowed: $($allowed -join ', '). Report to the main agent what you needed."
    }

    # URL safety (navigate)
    if ($tool -eq 'navigate' -and $ti.url) {
        $u = ([string]$ti.url).Trim()
        if ($u -notin @('back', 'forward')) {
            if ($u -match '^(?i:(file|chrome|chrome-extension|javascript|data|view-source|about|blob|ftp)):') { Block $in $tool $isOperator "URL scheme not allowed: only http(s) pages may be opened." }
            $hostName = ''
            try { $hostName = ([uri]($(if ($u -match '^[a-zA-Z][a-zA-Z0-9+.-]*://') { $u } else { 'https://' + $u }))).Host.ToLower() } catch { Block $in $tool $isOperator "Unparseable URL." }
            $pol = (Get-KitData) + '/browser-policy.json'
            if (Test-Path -LiteralPath $pol) {
                $hosts = @((Get-Content -Raw -LiteralPath $pol | ConvertFrom-Json).allowedHosts)
                if ($hosts.Count -gt 0 -and ($hosts | ForEach-Object { $_.ToLower() }) -notcontains $hostName) {
                    Add-BlockedRequest 'host' $hostName $type
                    Block $in $tool $isOperator "Host '$hostName' is not in allowedHosts of browser-policy.json. Report the URL to the main agent, which asks the user whether to allow this host (/agent-guards:kit-allow); never open it another way."
                }
            }
        }
    }

    if ($tool -eq 'computer') {
        $act = [string]$ti.action
        if ($isExplorer -and $act -notin @('screenshot', 'wait', 'scroll', 'scroll_to', 'zoom', 'hover')) {
            Block $in $tool $false "browser-explorer is read-only: computer action '$act' is not allowed (allowed: screenshot, wait, scroll, scroll_to, zoom, hover). Report to the main agent that this task needs the browser-operator."
        }
    }

    if ($isOperator) {
        $needsSummary = ($tool -eq 'form_input') -or ($tool -eq 'computer' -and [string]$ti.action -in @('left_click', 'right_click', 'double_click', 'triple_click', 'left_click_drag', 'type', 'key'))
        if ($needsSummary) {
            $s = [string]$ti.action_summary
            if ($tool -eq 'computer' -and [string]$ti.action -eq 'key' -and [string]$ti.text -match '(?i)(^|[\s+])(enter|return)($|[\s+])') { Block $in $tool $true "Pressing Enter can submit a form without naming it. Use the visible control by its ref instead, or stop and report." }
            if ([string]::IsNullOrWhiteSpace($s)) { Block $in $tool $true "action_summary is required on every click, type, key and form_input: state the effect and what it acts on." }
            if ($s -match '(?i)\b(submit\w*|delet\w*|remov\w*|send\w*|pay\w*|purchas\w*|buy\w*|approv\w*|sign\w*|confirm\w*|export\w*|publish\w*|post\w*|transfer\w*|discard\w*|reset\w*|clos\w* account|cancel\w* (order|subscription))\b') {
                Block $in $tool $true "action_summary '$s' names an irreversible or outward-facing effect. Do not perform it: stop and report to the main agent what you were about to do. The main agent must ask the user before any other route to this step."
            }
        }
        # No record, no action: an operator step that cannot be audited is not performed.
        if (-not (Write-Audit $in $tool 'allowed' '')) {
            Block $in $tool $false "the audit trail could not be written to $(Get-KitData)/audit (see hook-errors.log), so this operator action is not allowed. Report to the main agent that the browser audit log is not writable."
        }
    }
    exit 0
} catch {
    if ($guarded) { [Console]::Error.WriteLine("BLOCKED: the browser guard hit an internal error and fails closed for this agent. ($($_.Exception.Message))"); exit 2 }
    exit 0
}
