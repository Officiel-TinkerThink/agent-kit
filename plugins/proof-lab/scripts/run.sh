#!/bin/sh
# OS-neutral launcher for the kit's hooks, skills and tools. The one place that picks an implementation.
# Usage: sh run.sh <script-path-without-extension> [args...]   (stdin is passed through)
#   Windows (uname reports MINGW*, MSYS* or CYGWIN*): <script>.ps1 in Windows PowerShell 5.1 (powershell.exe on PATH)
#   Linux, WSL and macOS:                             <script>.sh  in POSIX sh
#   AGENT_KIT_SHELL=ps|posix (machine environment only) forces one implementation.
# Every call appends one line to <kit data>/verification-logs/_shell_routing.jsonl before it runs.
# A call that cannot be routed, or whose audit line cannot be written, exits 2 (fail closed).
# Design: docs/design/shell-adapter.md
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

script="${1%.ps1}"
[ -n "$script" ] || { echo "run.sh: missing script name" >&2; exit 2; }
shift

os_name=$(uname -s 2>/dev/null | tr -d '"\\')
[ -n "$os_name" ] || os_name=unknown
impl=posix
reason=os
case "${AGENT_KIT_SHELL:-}" in
  ps) impl=ps; reason=override ;;
  posix) impl=posix; reason=override ;;
  '') case "$os_name" in MINGW*|MSYS*|CYGWIN*) impl=ps ;; esac ;;
  *) echo "agent-kit: AGENT_KIT_SHELL must be ps or posix (got '$AGENT_KIT_SHELL')." >&2; exit 2 ;;
esac

if [ "$impl" = ps ]; then
  command -v powershell.exe >/dev/null 2>&1 || { echo "agent-kit: powershell.exe is not on PATH. This Windows machine needs Windows PowerShell 5.1; pwsh is not used (see docs/design/shell-adapter.md)." >&2; exit 2; }
  [ -f "$script.ps1" ] || { echo "agent-kit: no PowerShell version of $script (expected $script.ps1)." >&2; exit 2; }
else
  [ -f "$script.sh" ] || { echo "agent-kit: no shell version of $script (expected $script.sh)." >&2; exit 2; }
fi

cap=$(basename "$script" | tr -d '"\\')
audit_dir="$(kit_data)/verification-logs"
line=$(printf '{"ts":"%s","capability":"%s","impl":"%s","reason":"%s","os":"%s"}' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$cap" "$impl" "$reason" "$os_name")
mkdir -p "$audit_dir" 2>/dev/null && printf '%s\n' "$line" >> "$audit_dir/_shell_routing.jsonl" 2>/dev/null || { echo "agent-kit: cannot write the shell routing audit line to $audit_dir. Call blocked (fail closed)." >&2; exit 2; }

if [ "$impl" = ps ]; then
  # Git Bash rewrites Unix-looking arguments (/etc/passwd, a/b c) before it execs a native program, which changes what a
  # guard sees. Turn that off, and give powershell.exe the script as a Windows path, so the arguments arrive as written.
  if command -v cygpath >/dev/null 2>&1; then psfile=$(cygpath -w "$script.ps1"); else psfile="$script.ps1"; fi
  export MSYS2_ARG_CONV_EXCL='*'
  export MSYS_NO_PATHCONV=1
  exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$psfile" "$@"
fi
exec sh "$script.sh" "$@"
