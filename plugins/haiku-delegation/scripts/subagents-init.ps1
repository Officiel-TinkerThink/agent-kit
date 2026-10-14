# Operator tool behind /subagents-init (haiku-delegation). Copies the shipped SUBAGENTS.md roster to a project root and
# imports it from CLAUDE.md or AGENTS.md. PowerShell twin of subagents-init.sh (same flags, stdout, files and exit codes).
#   subagents-init.ps1 [-Project <dir>] [-Import auto|claude|agents|none] [-Update] [-DryRun]
# Never overwrites: an existing SUBAGENTS.md that differs is kept unless -Update is given, and -Update replaces only the
# part above "## Project facts" (the project's own facts are kept) after writing SUBAGENTS.md.bak-<UTC timestamp>.
# The import line (@SUBAGENTS.md) is added once, to CLAUDE.md when it exists, else AGENTS.md, else a new CLAUDE.md.
# Exit codes: 0 ok, 1 refused (bad input), 2 internal error.
param(
    [string]$Project = '',
    [string]$Import = 'auto',
    [switch]$Update,
    [switch]$DryRun
)
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
    } elseif (-not $Update) {
        Write-Output "EXISTS SUBAGENTS.md differs from the shipped version; kept as it is (run again with -Update to refresh everything above '$Marker')"
    } else {
        $own = [IO.File]::ReadAllText($dest)
        $ship = [IO.File]::ReadAllText($Template)
        $mo = [regex]::Match($own, '(?m)^' + [regex]::Escape($Marker))
        $ms = [regex]::Match($ship, '(?m)^' + [regex]::Escape($Marker))
        if (-not $mo.Success) { Refuse "SUBAGENTS.md has no '$Marker' section, so the project's own text cannot be told apart; merge by hand" }
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
    if ($Import -eq 'none') { Write-Output 'IMPORT skipped (-Import none)'; Write-Output 'DONE'; exit 0 }
    $claude = Join-Path $root 'CLAUDE.md'; $agents = Join-Path $root 'AGENTS.md'
    if ($Import -eq 'claude') { $target = 'CLAUDE.md' }
    elseif ($Import -eq 'agents') { $target = 'AGENTS.md' }
    elseif (Test-Path -LiteralPath $claude -PathType Leaf) { $target = 'CLAUDE.md' }
    elseif (Test-Path -LiteralPath $agents -PathType Leaf) { $target = 'AGENTS.md' }
    else { $target = 'CLAUDE.md' }
    $tf = Join-Path $root $target
    $exists = Test-Path -LiteralPath $tf -PathType Leaf
    if ($exists -and (IsLink $tf)) { Refuse "$target is a symbolic link; edit its target by hand" }
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
    Write-Output 'DONE'
    exit 0
} catch {
    FailInternal $_.Exception.Message
}
