#!/bin/sh
# OS-neutral launcher for the kit's hooks, skills and tools. The one place that picks an implementation.
# Usage: sh run.sh [--hook] <script-path-without-extension> [args...]   (stdin is passed through)
#   Windows (uname reports MINGW*, MSYS* or CYGWIN*): <script>.ps1 in Windows PowerShell 5.1 (powershell.exe on PATH)
#   Linux, WSL and macOS:                             <script>.sh  in POSIX sh
#   AGENT_KIT_SHELL=ps|posix (machine environment only) forces one implementation.
#   --hook (hooks.json only): the hook input is read here for at most HOOK_INPUT_WAIT seconds and handed to the script
#   as a file, so the script always sees the end of its input. A script that reads to the end of a pipe the harness
#   leaves open would otherwise wait until the hook timeout killed it, and a killed hook decides nothing.
# Every call appends one line to <kit data>/verification-logs/_shell_routing.jsonl before it runs.
# A call that cannot be routed, or whose audit line cannot be written, exits 2 (fail closed).
# Design: docs/design/shell-adapter.md
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
HOOK_INPUT_WAIT=5

hook=0
if [ "${1:-}" = --hook ]; then hook=1; shift; fi
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

# --hook: copy stdin to a file with a time limit. A background cat with a timer, not timeout(1): under Git Bash the
# name can resolve to the Windows timeout.exe, which only waits. fd 3 keeps the caller's stdin for the background cat
# (an asynchronous command's own stdin is /dev/null). What arrived in time is passed on; each script then decides by
# its own rule what an incomplete input means. If no file can be made, stdin is passed through as before.
hook_in=""
if [ "$hook" = 1 ] && hook_in=$(mktemp "${TMPDIR:-/tmp}/agent-kit-hook.XXXXXX" 2>/dev/null); then
  trap 'rm -f "$hook_in"' EXIT
  trap 'rm -f "$hook_in"; exit 2' HUP INT TERM
  exec 3<&0
  cat <&3 >"$hook_in" 2>/dev/null &
  hook_cat=$!
  ( sleep "$HOOK_INPUT_WAIT"; kill "$hook_cat" 2>/dev/null ) </dev/null >/dev/null 2>&1 3<&- &
  hook_timer=$!
  wait "$hook_cat" || hook_error run.sh "$cap: hook input not closed within $HOOK_INPUT_WAIT s; passing on what arrived"
  kill "$hook_timer" 2>/dev/null
  exec 3<&-
fi

# launch <command> [args...]: runs the implementation. With --hook its stdin is the input file, removed on exit.
launch() {
  if [ -n "$hook_in" ]; then "$@" <"$hook_in"; exit $?; fi
  exec "$@"
}

if [ "$impl" = ps ]; then
  # Git Bash rewrites Unix-looking arguments (/etc/passwd, a/b c) before it execs a native program, which changes what a
  # guard sees. Turn that off, and give powershell.exe the script as a Windows path, so the arguments arrive as written.
  if command -v cygpath >/dev/null 2>&1; then psfile=$(cygpath -w "$script.ps1"); else psfile="$script.ps1"; fi
  export MSYS2_ARG_CONV_EXCL='*'
  export MSYS_NO_PATHCONV=1
  launch powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$psfile" "$@"
fi
launch sh "$script.sh" "$@"
