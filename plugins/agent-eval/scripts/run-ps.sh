#!/bin/sh
# Cross-platform launcher for the kit's PowerShell hooks and tools.
# Usage: sh run-ps.sh <script.ps1> [args...]   (stdin is passed through)
# Windows: Windows PowerShell 5.1 (powershell.exe). Linux/macOS: PowerShell 7 (pwsh).
script="$1"
[ -n "$script" ] || { echo "run-ps.sh: missing script path" >&2; exit 2; }
shift
if command -v powershell.exe >/dev/null 2>&1; then
  exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$script" "$@"
elif command -v pwsh >/dev/null 2>&1; then
  exec pwsh -NoProfile -File "$script" "$@"
fi
echo "agent-kit: PowerShell not found. On Ubuntu install PowerShell 7 (package 'powershell' from packages.microsoft.com) so 'pwsh' is on PATH." >&2
exit 2
