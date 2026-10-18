function Test-AgentIs([string]$Type, [string[]]$Names) {
    # plugin agents report agent_type as "<plugin>:<name>"; user-level agents report "<name>"
    foreach ($n in $Names) { if ($Type -eq $n -or $Type.EndsWith(':' + $n)) { return $true } }
    return $false
}
# PreToolUse hook (Grep|Read), registered by the agent-guards plugin. Applies ONLY to agents that must never read real env files.
# Blocks (exit 2): Read of a real env file, a Grep aimed at a real env file, and a directory-wide Grep that does not exclude env files.
# Example/template env files (.env.example, .env.sample, .env.template) stay readable.
try {
    $in = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $guarded = @('secret-candidate-lister', 'config-drift-checker', 'infra-reader', 'compliance-lister', 'annotator')
    if (-not (Test-AgentIs ([string]$in.agent_type) $guarded)) { exit 0 }

    $ti = $in.tool_input
    $isEnv = { param($p) ($p -match '(^|[\\/])\.env(\.[^\\/]*)?$') -and ($p -notmatch '\.(example|sample|template)$') }

    if ($in.tool_name -eq 'Read') {
        $p = [string]$ti.file_path
        if (& $isEnv $p) {
            [Console]::Error.WriteLine("BLOCKED (intentional guard, not a hook failure): real env files must not be read by this agent ($p). Example files (.env.example) are allowed.")
            exit 2
        }
        exit 0
    }

    if ($in.tool_name -eq 'Grep') {
        $path = [string]$ti.path
        $glob = [string]$ti.glob
        if ($path -and (& $isEnv $path)) {
            [Console]::Error.WriteLine("BLOCKED (intentional guard, not a hook failure): real env files must not be searched by this agent ($path).")
            exit 2
        }
        $looksLikeFile = $path -match '\.[A-Za-z0-9]{1,8}$'
        if (-not $looksLikeFile) {
            # directory-wide (or default-path) search: it must exclude env files with a negated glob
            if ($glob -notmatch '^!\*\*/\.env') {
                [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): a directory-wide Grep must exclude real env files. Re-run with glob `"!**/.env*`" (or search named files individually).')
                exit 2
            }
        }
        exit 0
    }
    exit 0
} catch { [Console]::Error.WriteLine("BLOCKED: env guard error"); exit 2 }
