# safe-rm-lib.ps1 - shared parsing + validation for safe-rm (dot-sourced by guard-verification-runner.ps1 and safe-rm.ps1).
# Windows PowerShell 5.1 compatible. Nothing here changes the filesystem.

function Get-SafeRmPolicy {
    param([string]$PolicyFile)
    # policy: -PolicyFile (tests) > <kit data>/safe-rm-policy.json (yours) > the shipped default (only the verification-logs folder is deletable)
    $data = $env:AGENT_KIT_DATA
    if (-not $data) { $c = $env:CLAUDE_CONFIG_DIR; if (-not $c -and $PSScriptRoot -match '^(.*?)[\\/]plugins[\\/]cache[\\/]') { $c = $Matches[1] }; if (-not $c) { $c = Join-Path $env:USERPROFILE '.claude' }; $data = Join-Path $c 'agent-kit' }
    $data = ($data -replace '\\', '/').TrimEnd('/')
    if (-not $PolicyFile) {
        $PolicyFile = Join-Path $data 'safe-rm-policy.json'
        if (-not (Test-Path -LiteralPath $PolicyFile)) { $PolicyFile = Join-Path $PSScriptRoot '..\policy\safe-rm-policy.default.json' }
    }
    $raw = (Get-Content -LiteralPath $PolicyFile -Raw -Encoding UTF8).Replace('${DATA}', $data)
    return ($raw | ConvertFrom-Json)
}

# Parse an `rm` command line the way a strict, tiny shell would. No expansion of any kind is performed.
function ConvertFrom-SafeRmCommand {
    param([string]$Command, $Policy)
    $c = $Command.Trim()
    if ($c -notmatch '^rm(\s+.*)?$') { return @{ Ok = $false; Reason = 'not an rm command' } }
    $rest = $c.Substring(2)
    $recurse = $false
    $tokens = New-Object System.Collections.ArrayList
    $pos = 0
    $len = $rest.Length
    $flagsOpen = $true
    while ($pos -lt $len) {
        while ($pos -lt $len -and $rest[$pos] -match '\s') { $pos++ }
        if ($pos -ge $len) { break }
        $ch = $rest[$pos]
        if ($ch -eq '"' -or $ch -eq "'") {
            $end = $rest.IndexOf($ch, $pos + 1)
            if ($end -lt 0) { return @{ Ok = $false; Reason = 'unterminated quote' } }
            $tok = $rest.Substring($pos + 1, $end - $pos - 1)
            $pos = $end + 1
            if ($pos -lt $len -and $rest[$pos] -notmatch '\s') { return @{ Ok = $false; Reason = 'text glued to a quoted argument' } }
            if ($tok -match '[\$`%;&|<>''"\x00-\x1f]') { return @{ Ok = $false; Reason = 'forbidden character in quoted path' } }
            $flagsOpen = $false
            [void]$tokens.Add($tok)
            continue
        }
        $start = $pos
        while ($pos -lt $len -and $rest[$pos] -notmatch '\s') { $pos++ }
        $tok = $rest.Substring($start, $pos - $start)
        if ($flagsOpen -and $tok -match '^-[A-Za-z]+$') {
            if ($tok -notmatch '^-[rRfv]+$') { return @{ Ok = $false; Reason = "unsupported rm option '$tok' (only -r, -R, -f, -v)" } }
            if ($tok -match '[rR]') { $recurse = $true }
            continue
        }
        if ($tok -match '^-') { return @{ Ok = $false; Reason = "unsupported rm option '$tok'" } }
        if ($tok -notmatch '^[A-Za-z0-9_./:@+=,*?-]+$') { return @{ Ok = $false; Reason = "unquoted path has shell-special characters ('$tok'); use plain /-separated paths or quote the path" } }
        $flagsOpen = $false
        [void]$tokens.Add($tok)
    }
    if ($tokens.Count -eq 0) { return @{ Ok = $false; Reason = 'no path given' } }
    $max = 20
    if ($Policy -and $Policy.caps -and $Policy.caps.maxTokens) { $max = [int]$Policy.caps.maxTokens }
    if ($tokens.Count -gt $max) { return @{ Ok = $false; Reason = "too many paths ($($tokens.Count) > $max)" } }
    return @{ Ok = $true; Recurse = $recurse; Tokens = @($tokens) }
}

# Turn one raw path token into a canonical Windows path. Refuses anything ambiguous.
function ConvertTo-SafeRmFullPath {
    param([string]$Raw)
    $s = $Raw.Trim()
    if ($s -eq '') { return @{ Ok = $false; Reason = 'empty path' } }
    if ($s -match '[\$`%;&|<>''"\x00-\x1f]') { return @{ Ok = $false; Reason = "forbidden character in path '$Raw'" } }
    if ($s -match '^(\\\\|//)') { return @{ Ok = $false; Reason = "network/UNC and device paths are not allowed ('$Raw')" } }
    if ($s -match '^/([A-Za-z])(/.*)?$') {
        $tail = $Matches[2]; if (-not $tail) { $tail = '/' }
        $s = $Matches[1].ToUpper() + ':' + $tail
    }
    if ($s -notmatch '^[A-Za-z]:[\\/]') { return @{ Ok = $false; Reason = "path must be absolute (drive letter or /c/...): '$Raw'" } }
    if ($s.Substring(2) -match ':') { return @{ Ok = $false; Reason = "alternate data streams / extra colons are not allowed ('$Raw')" } }
    $devices = @('CON','PRN','AUX','NUL','CLOCK$') + (1..9 | ForEach-Object { "COM$_"; "LPT$_" })
    foreach ($comp in ($s.Substring(3) -split '[\\/]')) {
        if ($comp -eq '' -or $comp -eq '.' -or $comp -eq '..') { continue }
        if ($comp -match '~\d') { return @{ Ok = $false; Reason = "8.3 short names are not allowed ('$comp')" } }
        if ($comp -match '[. ]$') { return @{ Ok = $false; Reason = "components ending in a dot or space are not allowed ('$comp')" } }
        if ($devices -contains (($comp -split '\.')[0].ToUpper())) { return @{ Ok = $false; Reason = "reserved device name ('$comp')" } }
    }
    # A wildcard is only legal in the last segment; canonicalize the folder part and re-attach the pattern (GetFullPath rejects * and ?).
    $leafGlob = $null
    $lastSep = $s.LastIndexOfAny([char[]]@('\', '/'))
    $lastSeg = $s.Substring($lastSep + 1)
    if ($lastSeg -match '[*?]') {
        $leafGlob = $lastSeg
        $s = $s.Substring(0, $lastSep + 1)
    }
    if ($s -match '[*?]') { return @{ Ok = $false; Reason = "wildcards are only allowed in the last path segment ('$Raw')" } }
    try { $full = [System.IO.Path]::GetFullPath($s) } catch { return @{ Ok = $false; Reason = "invalid path '$Raw'" } }
    $full = $full.TrimEnd('\')
    if ($leafGlob) { $full = $full + '\' + $leafGlob }
    return @{ Ok = $true; Path = $full }
}

function Test-SafeRmProtected {
    param([string[]]$RelComponents, $Policy)
    foreach ($comp in $RelComponents) {
        foreach ($p in @($Policy.protectedComponents)) { if ($comp -ieq $p) { return "protected folder '$comp'" } }
        foreach ($p in @($Policy.protectedNames))      { if ($comp -ilike $p) { return "protected name '$comp' (matches '$p')" } }
    }
    return $null
}

function Find-SafeRmRoot {
    param([string]$Full, $Policy)
    foreach ($r in @($Policy.allowedRoots)) {
        $root = [System.IO.Path]::GetFullPath($r.path).TrimEnd('\')
        if ($Full.Length -gt $root.Length -and $Full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            return @{ Rule = $r; Root = $root }
        }
    }
    return $null
}

# Walk a directory without following links; refuse reparse points and protected names; enforce size caps.
function Measure-SafeRmTree {
    param([string]$Dir, [string]$Root, $Policy)
    $files = 0; $bytes = [int64]0
    $stack = New-Object System.Collections.Stack
    $stack.Push((New-Object System.IO.DirectoryInfo($Dir)))
    while ($stack.Count -gt 0) {
        $d = $stack.Pop()
        foreach ($e in $d.GetFileSystemInfos()) {
            if ($e.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                return @{ Ok = $false; Reason = "contains a symlink or junction ('$($e.FullName)')" }
            }
            $prot = Test-SafeRmProtected -RelComponents @($e.Name) -Policy $Policy
            if ($prot) { return @{ Ok = $false; Reason = "contains a $prot ('$($e.FullName)')" } }
            if ($e.Attributes -band [System.IO.FileAttributes]::Directory) { $stack.Push($e) }
            else {
                $files++; $bytes += $e.Length
                if ($files -gt [int]$Policy.caps.maxFiles) { return @{ Ok = $false; Reason = "too many files (> $($Policy.caps.maxFiles))" } }
                if ($bytes -gt [int64]$Policy.caps.maxBytes) { return @{ Ok = $false; Reason = "too large (> $($Policy.caps.maxBytes) bytes)" } }
            }
        }
    }
    return @{ Ok = $true; Files = $files; Bytes = $bytes }
}

# Validate all tokens. Returns @{Ok; Reason; Items=@(@{Full;Root;IsDir;Files;Bytes}); Skipped=@()}.
function Resolve-SafeRmPaths {
    param($Policy, [string[]]$Tokens, [bool]$Recurse)
    $items = New-Object System.Collections.ArrayList
    $skipped = New-Object System.Collections.ArrayList
    $perRoot = @{}
    foreach ($tok in $Tokens) {
        $conv = ConvertTo-SafeRmFullPath -Raw $tok
        if (-not $conv.Ok) { return @{ Ok = $false; Reason = $conv.Reason } }
        $full = $conv.Path
        $leaf = Split-Path -Leaf $full
        $isGlob = $leaf -match '[*?]'
        $parent = Split-Path -Parent $full
        if ($parent -match '[*?]') { return @{ Ok = $false; Reason = "wildcards are only allowed in the last path segment ('$tok')" } }
        $candidates = @()
        if ($isGlob) {
            $probe = Find-SafeRmRoot -Full ($parent + '\' + 'x') -Policy $Policy
            if (-not $probe) { return @{ Ok = $false; Reason = "'$tok' is outside the allowed zones" } }
            if (-not $probe.Rule.allowGlob) { return @{ Ok = $false; Reason = "wildcards are not allowed in this zone; name each item ('$tok')" } }
            if (Test-Path -LiteralPath $parent -PathType Container) {
                $matches = @([System.IO.Directory]::GetFileSystemEntries($parent) | Where-Object { (Split-Path -Leaf $_) -ilike $leaf })
                if ($matches.Count -gt [int]$Policy.caps.maxGlobMatches) { return @{ Ok = $false; Reason = "'$tok' matches too many items ($($matches.Count) > $($Policy.caps.maxGlobMatches))" } }
                $candidates = $matches
            }
            if ($candidates.Count -eq 0) { [void]$skipped.Add("$tok (no match)"); continue }
        } else {
            $candidates = @($full)
        }
        foreach ($cand in $candidates) {
            $rootInfo = Find-SafeRmRoot -Full $cand -Policy $Policy
            if (-not $rootInfo) { return @{ Ok = $false; Reason = "'$cand' is outside the allowed zones (or is a zone root itself)" } }
            $rel = $cand.Substring($rootInfo.Root.Length + 1)
            $comps = @($rel -split '\\')
            if ($comps.Count -lt [int]$rootInfo.Rule.minDepth) { return @{ Ok = $false; Reason = "'$cand' is too close to the zone root (minimum depth $($rootInfo.Rule.minDepth))" } }
            $prot = Test-SafeRmProtected -RelComponents $comps -Policy $Policy
            if ($prot) { return @{ Ok = $false; Reason = "'$cand' is blocked: $prot" } }
            if (-not (Test-Path -LiteralPath $cand)) { [void]$skipped.Add("$cand (does not exist)"); continue }
            $info = Get-Item -LiteralPath $cand -Force
            if ($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { return @{ Ok = $false; Reason = "'$cand' is a symlink or junction" } }
            # no reparse point on any parent between the zone root and the item
            $walk = Split-Path -Parent $cand
            while ($walk.Length -gt $rootInfo.Root.Length) {
                $pi = Get-Item -LiteralPath $walk -Force
                if ($pi.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { return @{ Ok = $false; Reason = "'$cand' sits below a symlink or junction ('$walk')" } }
                $walk = Split-Path -Parent $walk
            }
            $isDir = [bool]($info.Attributes -band [System.IO.FileAttributes]::Directory)
            $files = 0; $bytes = [int64]0
            if ($isDir) {
                if (-not $Recurse) { return @{ Ok = $false; Reason = "'$cand' is a directory; use rm -r" } }
                $m = Measure-SafeRmTree -Dir $cand -Root $rootInfo.Root -Policy $Policy
                if (-not $m.Ok) { return @{ Ok = $false; Reason = "'$cand': $($m.Reason)" } }
                $files = $m.Files; $bytes = $m.Bytes
            } else { $files = 1; $bytes = $info.Length
                if ($bytes -gt [int64]$Policy.caps.maxBytes) { return @{ Ok = $false; Reason = "'$cand' is too large (> $($Policy.caps.maxBytes) bytes)" } }
            }
            $key = $rootInfo.Root
            if (-not $perRoot.ContainsKey($key)) { $perRoot[$key] = 0 }
            $perRoot[$key]++
            if ($perRoot[$key] -gt [int]$rootInfo.Rule.maxItems) { return @{ Ok = $false; Reason = "too many items in zone '$($rootInfo.Root)' (max $($rootInfo.Rule.maxItems) per command)" } }
            [void]$items.Add(@{ Full = $cand; Root = $rootInfo.Root; IsDir = $isDir; Files = $files; Bytes = $bytes })
        }
    }
    return @{ Ok = $true; Items = @($items); Skipped = @($skipped) }
}
