# Operator tool behind /subagents-init (haiku-delegation). Copies the shipped SUBAGENTS.md roster to a project root and
# imports it from CLAUDE.md or AGENTS.md. PowerShell twin of subagents-init.sh (same flags, stdout, files and exit codes).
#   subagents-init.ps1 [-Project <dir>] [-Import auto|claude|agents|none] [-Keep] [-NoOrchestration] [-DryRun]
# Never loses text: an existing SUBAGENTS.md that differs is refreshed (only the part above "## Project facts"; the project's
# own facts are kept) after writing SUBAGENTS.md.bak-<UTC timestamp>; the same for the orchestration block (only the text between
# the markers). -Keep leaves both as they are. -Update is accepted as before (it is the default now). A SUBAGENTS.md
# without a "## Project facts" section is replaced by the shipped one (backup first, a note under "Project facts" names the backup).
# The import line (@SUBAGENTS.md) is added once, to CLAUDE.md when it exists, else AGENTS.md, else a new CLAUDE.md.
# Exit codes: 0 ok, 1 refused (bad input), 2 internal error.
param(
    [string]$Project = '',
    [string]$Import = 'auto',
    [switch]$Update,
    [switch]$Keep,
    [switch]$DryRun,
    [switch]$NoOrchestration
)
$doUpdate = -not $Keep   # refreshing is the default; -Keep leaves SUBAGENTS.md and the rules block as they are (-Update is accepted as before)
$Template = Join-Path $PSScriptRoot '..\templates\SUBAGENTS.md'
$Marker = '## Project facts'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Refuse([string]$m) { [Console]::Error.WriteLine("REFUSED: $m"); exit 1 }
function FailInternal([string]$m) { [Console]::Error.WriteLine("subagents-init failed: $m"); exit 2 }
function IsLink([string]$p) { $i = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue; return ($i -and ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) }
function SameBytes([string]$a, [string]$b) {
    $x = [IO.File]::ReadAllBytes($a); $y = [IO.File]::ReadAllBytes($b)
    if ($x.Length -ne $y.Length) { return $false }
    for ($i = 0; $i -lt $x.Length; $i++) { if ($x[$i] -ne $y[$i]) { return $false } }
    return $true
}

if (@('auto', 'claude', 'agents', 'none') -notcontains $Import) { [Console]::Error.WriteLine("subagents-init: -Import '$Import' is not one of auto, claude, agents, none"); exit 1 }
if (-not (Test-Path -LiteralPath $Template -PathType Leaf)) { FailInternal "template not found: $Template" }
$Template = (Resolve-Path -LiteralPath $Template).Path

try {
    if ($Project) {
        if (-not (Test-Path -LiteralPath $Project -PathType Container)) { Refuse "-Project is not a folder: $Project" }
        $root = (Resolve-Path -LiteralPath $Project).Path
    } else {
        $root = $null
        $g = Get-Command git -ErrorAction SilentlyContinue
        if ($g) { $top = & git rev-parse --show-toplevel 2>$null; if ($LASTEXITCODE -eq 0 -and $top -and (Test-Path -LiteralPath $top -PathType Container)) { $root = (Resolve-Path -LiteralPath $top).Path } }
        if (-not $root) { $root = (Get-Location).Path }
    }
    Write-Output "ROOT: $($root -replace '\\', '/')"

    $dest = Join-Path $root 'SUBAGENTS.md'
    if (Test-Path -LiteralPath $dest) { if (IsLink $dest) { Refuse 'SUBAGENTS.md in the project root is a symbolic link; replace it with a real file first' } }

    # --- step 1: SUBAGENTS.md
    if (-not (Test-Path -LiteralPath $dest)) {
        if ($DryRun) { Write-Output 'WOULD CREATE SUBAGENTS.md' }
        else { Copy-Item -LiteralPath $Template -Destination $dest; Write-Output 'CREATED SUBAGENTS.md' }
    } elseif (SameBytes $Template $dest) {
        Write-Output 'UNCHANGED SUBAGENTS.md (identical to the shipped version)'
    } elseif (-not $doUpdate) {
        Write-Output 'EXISTS SUBAGENTS.md differs from the shipped version; kept as it is (-Keep)'
    } elseif (-not [regex]::IsMatch([IO.File]::ReadAllText($dest), '(?m)^' + [regex]::Escape($Marker))) {
        # an older SUBAGENTS.md without a "Project facts" section: the project's own text cannot be told apart from the shipped text,
        # so the file is replaced by the shipped one (no second copy of the roster) and the old file is saved as a backup that a
        # one-line note under "Project facts" points to
        if ($DryRun) { Write-Output "WOULD MIGRATE SUBAGENTS.md (backup first; replaced by the shipped version)" }
        else {
            $ship = [IO.File]::ReadAllText($Template)
            $bak = $dest + '.bak-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
            Copy-Item -LiteralPath $dest -Destination $bak
            $bn = Split-Path -Leaf $bak
            $new = $ship + "`n> Migrated: the previous SUBAGENTS.md is saved as $bn. Copy the facts about this project from it into the list above.`n"
            [IO.File]::WriteAllText($dest, $new, $utf8)
            Write-Output "MIGRATED SUBAGENTS.md (replaced by the shipped version; previous version: $bn; copy this project's facts from it into '$Marker')"
        }
    } else {
        $own = [IO.File]::ReadAllText($dest)
        $ship = [IO.File]::ReadAllText($Template)
        $mo = [regex]::Match($own, '(?m)^' + [regex]::Escape($Marker))
        $ms = [regex]::Match($ship, '(?m)^' + [regex]::Escape($Marker))
        if (-not $ms.Success) { FailInternal "the shipped template has no '$Marker' section" }
        $new = $ship.Substring(0, $ms.Index) + $own.Substring($mo.Index)
        if ($new -ceq $own) { Write-Output 'UNCHANGED SUBAGENTS.md (shipped part already up to date)' }
        elseif ($DryRun) { Write-Output 'WOULD UPDATE SUBAGENTS.md (backup first)' }
        else {
            $bak = $dest + '.bak-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
            Copy-Item -LiteralPath $dest -Destination $bak
            [IO.File]::WriteAllText($dest, $new, $utf8)
            Write-Output "UPDATED SUBAGENTS.md (previous version: $(Split-Path -Leaf $bak))"
        }
    }

    # --- step 2: the @SUBAGENTS.md import
    if ($Import -eq 'none') { Write-Output 'IMPORT skipped (-Import none)'; Write-Output 'ORCHESTRATION skipped (-Import none)'; Write-Output 'DONE'; exit 0 }
    $claude = Join-Path $root 'CLAUDE.md'; $agents = Join-Path $root 'AGENTS.md'
    if ($Import -eq 'claude') { $target = 'CLAUDE.md' }
    elseif ($Import -eq 'agents') { $target = 'AGENTS.md' }
    elseif (Test-Path -LiteralPath $claude -PathType Leaf) { $target = 'CLAUDE.md' }
    elseif (Test-Path -LiteralPath $agents -PathType Leaf) { $target = 'AGENTS.md' }
    else { $target = 'CLAUDE.md' }
    $tf = Join-Path $root $target
    $exists = Test-Path -LiteralPath $tf -PathType Leaf
    if ($exists -and (IsLink $tf)) { Refuse "$target is a symbolic link; edit its target by hand" }
    if ($exists -and (Get-Item -LiteralPath $tf).IsReadOnly) { Refuse "$target is read-only; make it writable first" }
    # refuse damaged orchestration markers up front, so a refused run has written nothing to $target
    if (-not $NoOrchestration -and $exists) {
        $ptext = [IO.File]::ReadAllText($tf)
        $pb = [regex]::Matches($ptext, '(?m)^<!-- agent-kit:orchestration:begin'); $pe = [regex]::Matches($ptext, '(?m)^<!-- agent-kit:orchestration:end -->')
        if ($pb.Count -ne 0 -or $pe.Count -ne 0) {
            if ($pb.Count -ne 1 -or $pe.Count -ne 1 -or $pb[0].Index -ge $pe[0].Index) {
                Refuse "the orchestration markers in $target are damaged ($($pb.Count) begin line(s), $($pe.Count) end line(s), or the end comes first); fix them by hand or remove both marker lines and the text between them"
            }
        }
    }
    $block = "## Subagents`n`n@SUBAGENTS.md`n"
    if ($exists -and ([IO.File]::ReadAllText($tf) -match '@SUBAGENTS\.md')) {
        Write-Output "IMPORT already in $target"
    } elseif ($DryRun) {
        if ($exists) { Write-Output "WOULD ADD import to $target" } else { Write-Output "WOULD CREATE $target with the import" }
    } elseif ($exists) {
        $text = [IO.File]::ReadAllText($tf)
        $prefix = ''
        if ($text.Length -gt 0) { if (-not $text.EndsWith("`n")) { $prefix = "`n" }; $prefix += "`n" }
        [IO.File]::AppendAllText($tf, $prefix + $block, $utf8)
        Write-Output "IMPORT added to $target"
    } else {
        [IO.File]::WriteAllText($tf, $block, $utf8)
        Write-Output "IMPORT created $target"
    }

    # --- step 3: the orchestration block = the shipped AGENTS.md text, verbatim, between two marker lines, in the same file as the import.
    # Everything already in the file stays byte for byte. -Update replaces only what sits between the markers (backup first).
    if ($NoOrchestration) {
        Write-Output 'ORCHESTRATION skipped (-NoOrchestration)'
    } else {
        $otemplate = Join-Path $PSScriptRoot '..\templates\AGENTS.md'
        if (-not (Test-Path -LiteralPath $otemplate -PathType Leaf)) { FailInternal "template not found: $otemplate" }
        $obegin = '<!-- agent-kit:orchestration:begin (managed by /haiku-delegation:subagents-init; the text between the markers is replaced by -Update, everything outside is yours) -->'
        $oend = '<!-- agent-kit:orchestration:end -->'
        $tpl = [IO.File]::ReadAllText($otemplate).Replace("`r", '')
        if (-not $tpl.EndsWith("`n")) { $tpl += "`n" }
        $block = $obegin + "`n" + $tpl + $oend + "`n"
        $text = ''; $tfExists = Test-Path -LiteralPath $tf -PathType Leaf
        if ($tfExists) { $text = [IO.File]::ReadAllText($tf) }
        $crlf = $text.Contains("`r")
        if ($crlf) { $block = $block.Replace("`n", "`r`n") }
        $nb = [regex]::Matches($text, '(?m)^<!-- agent-kit:orchestration:begin').Count
        $ne = [regex]::Matches($text, '(?m)^<!-- agent-kit:orchestration:end -->').Count
        $mb = [regex]::Match($text, '(?m)^<!-- agent-kit:orchestration:begin')
        $me = [regex]::Match($text, '(?m)^<!-- agent-kit:orchestration:end -->')
        if ($nb -eq 0 -and $ne -eq 0) {
            $norm = $text.Replace("`r", '')
            if ($text.Length -gt 0 -and $norm.IndexOf($tpl.TrimEnd("`n"), [StringComparison]::Ordinal) -ge 0) {
                Write-Output "ORCHESTRATION already present in $target (verbatim; no markers added)"
            } elseif ($DryRun) {
                Write-Output "WOULD ADD orchestration to $target"
            } else {
                $eol = if ($crlf) { "`r`n" } else { "`n" }
                $prefix = ''
                if ($text.Length -gt 0) { if (-not $text.EndsWith("`n")) { $prefix = $eol }; $prefix += $eol }
                [IO.File]::AppendAllText($tf, $prefix + $block, $utf8)
                Write-Output "ORCHESTRATION added to $target"
            }
        } elseif ($nb -eq 1 -and $ne -eq 1 -and $mb.Index -lt $me.Index) {
            $lines = $text -split "`n"
            $bi = -1; $ei = -1
            for ($i = 0; $i -lt $lines.Length; $i++) {
                if ($bi -lt 0 -and $lines[$i].StartsWith('<!-- agent-kit:orchestration:begin')) { $bi = $i }
                elseif ($bi -ge 0 -and $lines[$i].StartsWith('<!-- agent-kit:orchestration:end -->')) { $ei = $i; break }
            }
            $inner = (($lines[($bi + 1)..($ei - 1)] | ForEach-Object { $_.Replace("`r", '') }) -join "`n")
            if ($ei -eq $bi + 1) { $inner = '' } else { $inner += "`n" }
            if ($inner -ceq $tpl) {
                Write-Output "ORCHESTRATION up to date in $target"
            } elseif (-not $doUpdate) {
                Write-Output "ORCHESTRATION outdated in $target; kept as it is (-Keep); run again without -Keep to refresh the block (text outside the markers is never touched)"
            } elseif ($DryRun) {
                Write-Output "WOULD UPDATE orchestration in $target (backup first)"
            } else {
                $blockLines = $block.Substring(0, $block.Length - 1) -split "`n"
                $new = @(); if ($bi -gt 0) { $new += $lines[0..($bi - 1)] }
                $new += $blockLines
                if ($ei + 1 -le $lines.Length - 1) { $new += $lines[($ei + 1)..($lines.Length - 1)] }
                $newText = $new -join "`n"
                if (-not $newText.EndsWith("`n")) { $newText += "`n" }
                $bak = $tf + '.bak-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
                Copy-Item -LiteralPath $tf -Destination $bak
                [IO.File]::WriteAllText($tf, $newText, $utf8)
                Write-Output "ORCHESTRATION updated in $target (previous version: $(Split-Path -Leaf $bak))"
            }
        } else {
            Refuse "the orchestration markers in $target are damaged ($nb begin line(s), $ne end line(s), or the end comes first); fix them by hand or remove both marker lines and the text between them"
        }
    }
    Write-Output 'DONE'
    exit 0
} catch {
    FailInternal $_.Exception.Message
}
