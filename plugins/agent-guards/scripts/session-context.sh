#!/bin/sh
# SessionStart hook: stdout is injected into the session context.
# POSIX sh port of session-context.ps1 (prints the machine shell, then ../policy/guards.md; the guards file is silent and
# exit 0 when it cannot be read). This version runs only where no Windows PowerShell is on PATH.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
printf '%s\n' "Machine shell: POSIX sh. Windows PowerShell is not on PATH on this machine: do not run powershell or pwsh, and do not call a .ps1 script. Use the Bash tool with POSIX commands; run kit scripts as sh <name>.sh."
cat "$KIT_SCRIPT_DIR/../policy/guards.md" 2>/dev/null
exit 0
