#!/bin/sh
# PreToolUse hook (PowerShell and Bash), registered by the agent-guards plugin. run.sh runs this POSIX version only when
# no Windows PowerShell is on PATH (Linux, macOS, or a shell without powershell.exe). A call that needs PowerShell cannot
# run there, so it is blocked here and the message names the POSIX alternative.
# Scope: accidental use. A call hidden inside eval, a base64 string or a script file is not seen.
# Unparseable hook input is blocked (fail-closed), as in the other guards.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

# json_ok <text>: cheap structural check that the hook input is one JSON object.
json_ok() {
  _t=$(printf '%s' "$1" | tr -d ' \t\r\n')
  case "$_t" in \{*\}) return 0 ;; esac
  return 1
}

# pwsh or powershell (optionally .exe) started as a command: at the start of the text or after ; & | ( or a quote.
PS_CALL=$(cat <<'RE'
(^|[;&|("'`])[[:space:]]*(pwsh|powershell)(\.exe)?([[:space:]]|$)
RE
)

INPUT=$(cat)
json_ok "$INPUT" || { printf '%s\n' "BLOCKED: guard error" >&2; exit 2; }

TOOL=$(json_get "$INPUT" tool_name)
case "$TOOL" in
  PowerShell)
    printf '%s\n' "BLOCKED: PowerShell is not available on this machine. Use the Bash tool with the POSIX command instead (for example ls, cat, grep, find), or run the sh version of the kit script (<name>.sh)." >&2
    exit 2 ;;
  Bash) ;;
  *) exit 0 ;;
esac

CMD=$(json_get "$INPUT" tool_input.command)
if printf '%s' "$CMD" | grep -E -i -q "$PS_CALL"; then
  printf '%s\n' "BLOCKED: pwsh and powershell are not available on this machine. Use the POSIX command, or the sh version of the kit script (<name>.sh)." >&2
  exit 2
fi
exit 0
