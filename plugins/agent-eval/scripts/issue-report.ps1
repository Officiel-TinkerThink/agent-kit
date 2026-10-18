# /agent-eval:report-issue (PowerShell twin of issue-report.sh). Turns the kit's local error evidence into a GitHub issue, ONLY when the user asks and confirms.
#   issue-report.ps1 draft  [-Days N]         writes <KIT_DATA>/reports/issue-draft-<time>.md and prints DRAFT/TITLE/FINGERPRINT; sends nothing
#   issue-report.ps1 submit -Draft <file>     re-sanitizes the draft, looks for an issue with the same fingerprint, creates one with gh, or prints a prefilled URL
# The draft holds counts, script names, versions and sanitized hook-error messages. Never prompts, answers, transcripts or file contents.
# Overrides: AGENT_KIT_DATA (data folder), AGENT_KIT_REPO (owner/name), AGENT_KIT_GH (path of the gh program).
param([string]$Action = 'draft', [int]$Days = 30, [string]$Draft = '')
$ErrorActionPreference = 'Stop'
$Repo = if ($env:AGENT_KIT_REPO) { $env:AGENT_KIT_REPO } else { 'Officiel-TinkerThink/agent-kit' }
if ($Days -lt 1 -or $Days -gt 365) { 'REJECTED: -Days must be 1 to 365'; exit 2 }
if ($Action -ne 'draft' -and $Action -ne 'submit') { 'REJECTED: action must be draft or submit'; exit 2 }

function Get-KitData {
    $d = $env:AGENT_KIT_DATA
    if (-not $d) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $(if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) '.claude' }; $d = Join-Path $c 'agent-kit' }
    return ($d -replace '\\', '/').TrimEnd('/')
}
$Data = Get-KitData
$Utf8 = New-Object System.Text.UTF8Encoding($false)

# Same rules, same order as sanitize() in issue-report.sh.
function Sanitize([string]$Text) {
    $t = $Text
    $t = [regex]::Replace($t, '://[^/@ ]+@', '://<redacted:secret>@')
    $t = [regex]::Replace($t, '(Bearer|Basic) +[A-Za-z0-9._~+/=-]+', '$1 <redacted:secret>', 'IgnoreCase')
    $t = [regex]::Replace($t, '(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|xox[a-z]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{8,}|AIza[A-Za-z0-9_-]{8,})', '<redacted:secret>')
    $t = [regex]::Replace($t, '((pass(word)?|pwd|secret|token|api[_-]?key|credential)[A-Za-z0-9_]*[=:] *)[^ ,;"'']+', '$1<redacted:secret>', 'IgnoreCase')
    $t = [regex]::Replace($t, '[A-Za-z0-9+/=_-]{32,}', '<redacted:secret>')
    $t = [regex]::Replace($t, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '<email>')
    $t = [regex]::Replace($t, '[A-Za-z]:[\\/]+Users[\\/]+[^\\/ ]+', '<home>', 'IgnoreCase')
    $t = [regex]::Replace($t, '/(Users|home)/[^/ ]+', '<home>')
    $t = [regex]::Replace($t, '/root([/ ]|$)', '<home>$1')
    $t = [regex]::Replace($t, '([A-Za-z]:)?[\\/]([^ \\/"'']+[\\/])+([^ \\/"'']+)', '<path>/$3')
    $t = [regex]::Replace($t, ' +', ' ')
    return $t
}
function Get-Word([string]$W) { if ($W -cmatch '^[a-z0-9:_-]{1,60}$') { return $W } else { return 'other' } }
function Get-PluginVersion {
    try { $m = [regex]::Match([System.IO.File]::ReadAllText((Join-Path $PSScriptRoot '../.claude-plugin/plugin.json')), '"version"\s*:\s*"([0-9][0-9.]*)"'); if ($m.Success) { return $m.Groups[1].Value } } catch { }
    return 'unknown'
}
# The highest installed version of a kit plugin (installed layout .../agent-kit/<plugin>/<version>/, or this repository), else 'not installed'. Same lookup as version_of in the shell twin.
function Get-PluginVersionOf([string]$Plugin) {
    if ($Plugin -eq 'agent-eval') { return (Get-PluginVersion) }
    $found = @()
    $cands = @()
    try { $cands += @(Get-ChildItem -Path (Join-Path $PSScriptRoot "../../../$Plugin/*/.claude-plugin/plugin.json") -ErrorAction SilentlyContinue) } catch { }
    $repo = Join-Path $PSScriptRoot "../../$Plugin/.claude-plugin/plugin.json"
    if (Test-Path -LiteralPath $repo) { $cands += Get-Item -LiteralPath $repo }
    foreach ($f in $cands) {
        $m = [regex]::Match([System.IO.File]::ReadAllText($f.FullName), '"version"\s*:\s*"([0-9][0-9.]*)"')
        if ($m.Success) { try { $found += [version]$m.Groups[1].Value } catch { } }
    }
    if ($found.Count -eq 0) { return 'not installed' }
    return (($found | Sort-Object | Select-Object -Last 1).ToString())
}
function Get-ClaudeVersion {
    try {
        $c = Get-Command claude -ErrorAction SilentlyContinue
        if (-not $c) { return 'unknown' }
        $o = (& $c.Source --version 2>$null | Select-Object -First 1)
        $m = [regex]::Match([string]$o, '^([0-9][0-9.]*)')
        if ($m.Success) { return $m.Groups[1].Value }
    } catch { }
    return 'unknown'
}
function Get-VersionsLine {
    return ("**Versions:** agent-kit $(Get-PluginVersion) (agent-eval $(Get-PluginVersionOf 'agent-eval'), agent-guards $(Get-PluginVersionOf 'agent-guards'), haiku-delegation $(Get-PluginVersionOf 'haiku-delegation'), verification-runner $(Get-PluginVersionOf 'verification-runner')), claude-code $(Get-ClaudeVersion), os $(Sanitize (Get-OsName))")
}
function Get-OsName {
    $o = [System.Environment]::OSVersion.Platform.ToString() + ' ' + [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    return $o
}
function Get-Cell([string]$S) { return ($S -replace '\|', '\|' -replace '`', "'") }
# Get-Pct: percent-encodes every UTF-8 byte except RFC 3986 unreserved characters (A-Z a-z 0-9 - . _ ~), upper-case hex, as the sh twin does
function Get-Pct([string]$S) { return Get-PctBytes ($Utf8.GetBytes($S)) }
function Get-PctBytes([byte[]]$Bytes) {
    $sb = New-Object System.Text.StringBuilder
    foreach ($b in $Bytes) {
        $c = [string][char]$b
        if ($c -cmatch '^[A-Za-z0-9._~-]$') { [void]$sb.Append($c) } else { [void]$sb.Append('%' + $b.ToString('X2')) }
    }
    return $sb.ToString()
}
function Get-Fingerprint([string]$S) {
    $b = $Utf8.GetBytes($S)
    $h = [System.Security.Cryptography.SHA256]::Create().ComputeHash($b)
    return (($h | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0, 12)
}
function Get-CutDate { return (Get-Date).ToUniversalTime().AddDays(-$Days).ToString('yyyy-MM-dd') }
function Compare-Ordinal([string]$A, [string]$B) { return [string]::CompareOrdinal($A, $B) }

function Get-Errors {   # objects sorted like the shell twin: count desc, then signature (ordinal) asc
    $log = "$Data/hook-errors.log"
    if (-not (Test-Path -LiteralPath $log)) { return @() }
    $cut = Get-CutDate
    $groups = @{}
    $lines = @(Get-Content -LiteralPath $log -Tail 2000 -Encoding UTF8)
    foreach ($l in $lines) {
        $mm = [regex]::Match($l, '^(\S+) +(\S+) *(.*)$')
        if (-not $mm.Success) { continue }
        $ts = $mm.Groups[1].Value; $sc = $mm.Groups[2].Value -replace ':$', ''
        if ($ts -notmatch '^\d{4}-\d{2}-\d{2}T[0-9:.]+') { continue }
        if ([string]::CompareOrdinal($ts.Substring(0, 10), $cut) -lt 0) { continue }
        if ($sc -notmatch '^[A-Za-z0-9_.-]+$' -or $sc.Length -gt 60) { continue }
        $msg = Sanitize (($mm.Groups[3].Value -replace "[\t\r]", ' '))
        $ts19 = $ts.Substring(0, [Math]::Min(19, $ts.Length))
        $key = $sc + '|' + ($msg -replace '[0-9]+', 'N')
        if (-not $groups.ContainsKey($key)) { $groups[$key] = [pscustomobject]@{ Count = 0; First = $ts19; Last = $ts19; Script = $sc; Message = $msg.Substring(0, [Math]::Min(240, $msg.Length)); Key = $key } }
        $g = $groups[$key]; $g.Count++
        if ([string]::CompareOrdinal($ts19, $g.First) -lt 0) { $g.First = $ts19 }
        if ([string]::CompareOrdinal($ts19, $g.Last) -gt 0) { $g.Last = $ts19 }
    }
    $arr = @($groups.Values)
    [Array]::Sort($arr, [System.Comparison[object]]{ param($x, $y) if ($x.Count -ne $y.Count) { return $y.Count.CompareTo($x.Count) }; return [string]::CompareOrdinal($x.Key, $y.Key) })
    return $arr
}
function Get-Annotations {
    $f = "$Data/eval/annotations.jsonl"
    if (-not (Test-Path -LiteralPath $f)) { return @() }
    $cut = Get-CutDate
    $groups = @{}
    foreach ($l in @(Get-Content -LiteralPath $f -Tail 500 -Encoding UTF8)) {
        if (-not $l) { continue }
        try { $o = $l | ConvertFrom-Json } catch { continue }
        $ts = [string]$o.ts
        if ($ts.Length -lt 10 -or [string]::CompareOrdinal($ts.Substring(0, 10), $cut) -lt 0) { continue }
        if ([string]$o.verified -eq 'no') { continue }
        $key = (Get-Word ([string]$o.agent_type)) + "`t" + (Get-Word ([string]$o.outcome)) + "`t" + (Get-Word ([string]$o.code)) + "`t" + (Get-Word ([string]$o.severity))
        if ($groups.ContainsKey($key)) { $groups[$key]++ } else { $groups[$key] = 1 }
    }
    $arr = @($groups.GetEnumerator() | ForEach-Object { [pscustomobject]@{ Count = $_.Value; Key = $_.Key } })
    [Array]::Sort($arr, [System.Comparison[object]]{ param($x, $y) if ($x.Count -ne $y.Count) { return $y.Count.CompareTo($x.Count) }; return [string]::CompareOrdinal($x.Key, $y.Key) })
    return $arr
}

function Invoke-Draft {
    $err = @(Get-Errors); $ann = @(Get-Annotations)
    if ($err.Count -eq 0 -and $ann.Count -eq 0) { "NO ERRORS in the last $Days days (hook-errors.log and eval/annotations.jsonl). Nothing to report."; exit 0 }
    $sigs = @(); foreach ($e in $err) { $sigs += ('E|' + $e.Key) }
    foreach ($a in $ann) { $sigs += ('A|' + ($a.Key -replace "`t", '|')) }
    $sorted = [string[]]$sigs; [Array]::Sort($sorted, [System.StringComparer]::Ordinal)
    $fp = Get-Fingerprint ($sorted -join "`n")
    if ($err.Count -gt 0) { $top = $err[0]; $title = "[agent-kit $(Get-PluginVersion)] Error report: $($top.Script): $($top.Message.Substring(0, [Math]::Min(60, $top.Message.Length)))" }
    else { $p = $ann[0].Key -split "`t"; $title = "[agent-kit $(Get-PluginVersion)] Agent failure report: $($p[0]) $($p[2])" }
    $title = Sanitize $title
    $outDir = "$Data/reports"
    [void](New-Item -ItemType Directory -Path $outDir -Force)
    $out = "$outDir/issue-draft-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')).md"
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append("<!-- agent-kit-report fingerprint: $fp -->`n<!-- title: $title -->`n")
    [void]$sb.Append("## Error report from a plugin user (reviewed by the user before sending)`n`n")
    [void]$sb.Append("Contains only counts, script names, versions and sanitized error messages. No prompts, answers, transcripts or file contents.`n`n")
    [void]$sb.Append((Get-VersionsLine) + "`n")
    [void]$sb.Append("**Window:** last $Days days`n`n")
    [void]$sb.Append("### Hook errors ($($err.Count) kinds)`n`n")
    if ($err.Count -gt 0) {
        [void]$sb.Append("| Count | First seen | Last seen | Script | Message |`n|---|---|---|---|---|`n")
        foreach ($e in $err) { [void]$sb.Append("| $($e.Count) | $($e.First) | $($e.Last) | ``$(Get-Cell $e.Script)`` | ``$(Get-Cell $e.Message)`` |`n") }
    } else { [void]$sb.Append("none`n") }
    [void]$sb.Append("`n### Annotated agent failures ($($ann.Count) kinds)`n`n")
    if ($ann.Count -gt 0) {
        [void]$sb.Append("| Count | Agent | Outcome | Code | Severity |`n|---|---|---|---|---|`n")
        foreach ($a in $ann) { $p = $a.Key -split "`t"; [void]$sb.Append("| $($a.Count) | ``$($p[0])`` | $($p[1]) | $($p[2]) | $($p[3]) |`n") }
    } else { [void]$sb.Append("none`n") }
    [System.IO.File]::WriteAllText($out, $sb.ToString(), $Utf8)
    "DRAFT $out"; "TITLE $title"; "FINGERPRINT $fp"; "HOOK_ERROR_KINDS $($err.Count) ANNOTATION_KINDS $($ann.Count)"
    'NOTHING SENT. Show the draft to the user; submit only after they confirm.'
}

function Invoke-Submit {
    if (-not $Draft) { 'REJECTED: -Draft <file> is required'; exit 2 }
    if (-not (Test-Path -LiteralPath "$Data/reports")) { 'REJECTED: no reports folder yet; run draft first'; exit 2 }
    $dir = (Resolve-Path -LiteralPath "$Data/reports").Path.TrimEnd('\', '/')
    $full = if (Test-Path -LiteralPath $Draft -PathType Leaf) { (Resolve-Path -LiteralPath $Draft).Path } else { '' }
    $ok = $full -and ((Split-Path -Parent $full).TrimEnd('\', '/') -ieq $dir) -and ((Split-Path -Leaf $full) -like 'issue-draft-*.md')
    if (-not $ok) { "REJECTED: the draft must be a file issue-draft-*.md inside $($dir -replace '\\', '/')"; exit 2 }
    if ((Get-Item -LiteralPath $full).Length -gt 60000) { 'REJECTED: draft is larger than 60000 bytes'; exit 2 }
    $text = [System.IO.File]::ReadAllText($full, $Utf8)
    $fm = [regex]::Match($text, '^<!-- agent-kit-report fingerprint: ([0-9a-f]{12}) -->')
    if (-not $fm.Success) { 'REJECTED: the draft has no fingerprint line on its first line'; exit 2 }
    $fp = $fm.Groups[1].Value
    $lines = $text -split "`n"
    $title = ''
    if ($lines.Count -gt 1) { $tm = [regex]::Match($lines[1], '^<!-- title: (.*) -->\s*$'); if ($tm.Success) { $title = (Sanitize $tm.Groups[1].Value) } }
    if ($title.Length -gt 120) { $title = $title.Substring(0, 120) }
    if (-not $title) { $title = "Error report from a plugin user ($fp)" }
    $rest = @($lines | Select-Object -Skip 2)
    $body = "<!-- agent-kit-report fingerprint: $fp -->`n" + (Sanitize ($rest -join "`n"))
    $bodyFile = "$Data/reports/.submit-body.md"
    [System.IO.File]::WriteAllText($bodyFile, $body, $Utf8)
    $gh = $env:AGENT_KIT_GH
    if (-not $gh) { $c = Get-Command gh -ErrorAction SilentlyContinue; if ($c) { $gh = $c.Source } }
    if ($gh) { try { & $gh auth status *> $null; if ($LASTEXITCODE -ne 0) { $gh = $null } } catch { $gh = $null } }
    if ($gh) {
        $found = [regex]::Match((& $gh issue list --repo $Repo --state all --search "$fp in:body" --json url --limit 5 2>$null | Out-String), 'https://[^"\s]+')
        if ($found.Success) { "DUPLICATE $($found.Value)"; 'An issue with this fingerprint exists; nothing created. Add a comment there if the user wants.'; exit 0 }
        $made = [regex]::Matches((& $gh issue create --repo $Repo --title $title --body-file $bodyFile 2>$null | Out-String), 'https://\S+')
        if ($made.Count -eq 0) { 'FAILED gh issue create returned no URL'; exit 1 }
        "CREATED $($made[$made.Count - 1].Value)"; exit 0
    }
    # as the sh twin: the first 2200 bytes, with trailing newlines removed (shell command substitution)
    $bytes = $Utf8.GetBytes($body)
    if ($bytes.Length -gt 2200) { $bytes = $bytes[0..2199] }
    $end = $bytes.Length
    while ($end -gt 0 -and $bytes[$end - 1] -eq 10) { $end-- }
    "NO_GH gh is missing or not logged in. Open this link in a browser and press `"Submit new issue`":"
    $kept = New-Object byte[] $end
    [Array]::Copy($bytes, $kept, $end)
    "https://github.com/$Repo/issues/new?title=$(Get-Pct $title)&body=$(Get-PctBytes $kept)"
}

try {
    if ($Action -eq 'draft') { Invoke-Draft } else { Invoke-Submit }
} catch {
    "FAILED $($_.Exception.Message -replace '\s+', ' ')"
    exit 1
}
