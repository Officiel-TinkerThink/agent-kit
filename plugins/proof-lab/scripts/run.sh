#!/bin/sh
# Routes a hook to its implementation: sh run.sh <script-path-without-extension>.
# Windows (Git Bash: MINGW, MSYS or CYGWIN) runs <name>.ps1 in Windows PowerShell; other systems run <name>.sh.
# AGENT_KIT_SHELL=ps or posix forces one. Same routing as agent-guards' run.sh, without its audit log.
# Fails closed: when the script or its interpreter is missing, exit 2 (a hook exit of 2 blocks the call; any other
# failure would let the Bash call through unguarded).
script="${1%.ps1}"
script="${script%.sh}"
[ -n "$script" ] || { echo "run.sh: no script given" >&2; exit 2; }
shift
case "${AGENT_KIT_SHELL:-}" in
  ps) mode=ps ;;
  posix) mode=posix ;;
  *) case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) mode=ps ;; *) mode=posix ;; esac ;;
esac
if [ "$mode" = ps ]; then
  [ -f "$script.ps1" ] || { echo "run.sh: $script.ps1 not found; the guard fails closed" >&2; exit 2; }
  command -v powershell.exe >/dev/null 2>&1 || { echo "run.sh: powershell.exe is not on PATH, so $script.ps1 cannot run; the guard fails closed" >&2; exit 2; }
  exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$script.ps1" "$@"
fi
[ -f "$script.sh" ] || { echo "run.sh: $script.sh not found; the guard fails closed" >&2; exit 2; }
exec sh "$script.sh" "$@"
