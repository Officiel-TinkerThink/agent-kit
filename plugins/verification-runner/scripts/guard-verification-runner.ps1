# PreToolUse hook (Bash). Applies ONLY to the `verification-runner` subagent.
# Which commands the runner may run is decided by Claude Code's own permissions (settings allow / ask / deny rules): this hook stays silent
# (exit 0) for them, so the normal permission flow applies. It only protects what permission rules cannot express:
#   - `rm` is rewritten to the safe-rm executor (policy zones, quarantine instead of deletion, audit first). A delete hidden inside a longer
#     command line is refused: deletions are only accepted as a bare `rm [-r] [-f] <absolute paths>` line.
#   - evidence logs: a redirect into <KIT_DATA>/verification-logs must create a NEW file (no overwrite, no append, no `..`).
# Other agents and the main thread are not affected (exit 0). Unparseable input fails open; an internal error fails closed for the runner.
$isRunner = $false
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
    if (-not (Test-AgentIs ([string]$in.agent_type) @('verification-runner'))) { exit 0 }
    $isRunner = $true
    if ($in.tool_name -ne 'Bash') { exit 0 }
    $cmd = ([string]$in.tool_input.command).Trim()

    $logRoot = (Get-KitData) + '/verification-logs'
    $drive = $logRoot.Substring(0, 1)
    $gitBash = '/' + $drive.ToLower() + $logRoot.Substring(2)       # /c/Users/... form
    $logAlt = '(?:' + ([regex]::Escape($logRoot) -replace '/', '[/\\]') + '|' + ([regex]::Escape($gitBash) -replace '/', '[/\\]') + ')'

    # --- rm: routed through safe-rm (policy zones, protected names, quarantine instead of deletion, audit first). See safe-rm-policy.json.
    # The agent keeps typing plain `rm`; after validation this hook REWRITES the command to the safe-rm.ps1 executor (updatedInput).
    if ($cmd -match '^rm(\s|$)') {
        . (Join-Path $PSScriptRoot 'safe-rm-lib.ps1')
        $policy = Get-SafeRmPolicy
        $parsed = ConvertFrom-SafeRmCommand -Command $cmd -Policy $policy
        if (-not $parsed.Ok) { [Console]::Error.WriteLine("BLOCKED: $($parsed.Reason). rm accepts: rm [-r] [-f] <absolute path>... (plain /-separated paths, or quoted)."); exit 2 }
        $res = Resolve-SafeRmPaths -Policy $policy -Tokens $parsed.Tokens -Recurse $parsed.Recurse
        if (-not $res.Ok) { [Console]::Error.WriteLine("BLOCKED by safe-rm policy: $($res.Reason)"); exit 2 }
        $wrapper = (Join-Path $PSScriptRoot 'safe-rm.ps1') -replace '\\', '/'
        $sess = ([string]$in.session_id) -replace '[^A-Za-z0-9-]', ''
        $parts = New-Object System.Collections.ArrayList
        [void]$parts.Add('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $wrapper + '"')
        if ($parsed.Recurse) { [void]$parts.Add('-Recurse') }
        [void]$parts.Add('-Agent verification-runner -Session "' + $sess + '"')
        foreach ($tok in $parsed.Tokens) { $conv = ConvertTo-SafeRmFullPath -Raw $tok; [void]$parts.Add('"' + ($conv.Path -replace '\\', '/') + '"') }
        $ui = @{}
        foreach ($prop in $in.tool_input.PSObject.Properties) { $ui[$prop.Name] = $prop.Value }
        $ui['command'] = ($parts -join ' ')
        $out = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'allow'; permissionDecisionReason = 'safe-rm: validated against policy; items are moved to quarantine (restorable), not deleted'; updatedInput = $ui } } | ConvertTo-Json -Depth 6 -Compress
        [Console]::Out.WriteLine($out)
        exit 0
    }

    # a delete inside a longer command line would bypass the quarantine
    if ($cmd -match '(^|[;&|`(\s])(rm|rmdir|rd|del|erase|unlink|shred|Remove-Item)(\s|$)') {
        [Console]::Error.WriteLine("BLOCKED: deletions by verification-runner are only accepted as a bare line: rm [-r] [-f] <absolute paths> (they are moved to a restorable quarantine). Do not put rm, del or Remove-Item inside another command.")
        exit 2
    }

    # evidence logs: a redirect into the verification-logs folder must create a NEW file
    foreach ($m in [regex]::Matches($cmd, '(?<![0-9&])(>>?)\s*("?)(' + $logAlt + '[/\\][^\s"''<>|;&]*)\2')) {
        $op = $m.Groups[1].Value; $target = $m.Groups[3].Value
        if ($op -eq '>>') { [Console]::Error.WriteLine("BLOCKED: appending (>>) to a verification log would alter earlier evidence. Redirect to a NEW file with >."); exit 2 }
        if ($target -match '(^|[/\\])\.\.([/\\]|$)') { [Console]::Error.WriteLine("BLOCKED: a log path must stay inside $logRoot (no '..')."); exit 2 }
        [void](New-Item -ItemType Directory -Force -Path ($logRoot -replace '/', '\'))   # the redirect target folder must exist
        $name = [regex]::Match($target, '[^/\\]+$').Value
        $path = Join-Path ($logRoot -replace '/', '\') $name
        if (Test-Path -LiteralPath $path) {
            [Console]::Error.WriteLine("BLOCKED: log file '$name' already exists; logs are never overwritten. Use a new unique name (for example add a run number).")
            exit 2
        }
    }
    [void](New-Item -ItemType Directory -Force -Path ($logRoot -replace '/', '\'))
    exit 0   # silent: Claude Code's permission rules decide whether this command runs
} catch {
    if ($isRunner) { [Console]::Error.WriteLine("BLOCKED: the verification-runner guard hit an internal error and fails closed for this agent. ($($_.Exception.Message))"); exit 2 }
    exit 0
}
