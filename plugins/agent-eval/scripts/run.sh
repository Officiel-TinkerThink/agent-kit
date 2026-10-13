#!/bin/sh
# OS-neutral launcher for the kit's hooks, skills and tools.
# Usage: sh run.sh <script-path-without-extension> [args...]   (stdin is passed through)
# The machine decides the implementation, so no command shown to a user or an agent names a shell language:
#   Windows (powershell.exe on PATH): <script>.ps1 in Windows PowerShell 5.1
#   Linux / macOS:                    <script>.sh  in POSIX sh (no PowerShell, no Python needed)
# A script with no version for this machine exits 2 (a guard that cannot run blocks instead of being skipped).
script="${1%.ps1}"
[ -n "$script" ] || { echo "run.sh: missing script name" >&2; exit 2; }
shift
if command -v powershell.exe >/dev/null 2>&1; then
  [ -f "$script.ps1" ] || { echo "agent-kit: no PowerShell version of $script (expected $script.ps1)." >&2; exit 2; }
  exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$script.ps1" "$@"
fi
[ -f "$script.sh" ] || { echo "agent-kit: no shell version of $script (expected $script.sh)." >&2; exit 2; }
exec sh "$script.sh" "$@"
