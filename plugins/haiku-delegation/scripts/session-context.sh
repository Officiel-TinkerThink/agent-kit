#!/bin/sh
# SessionStart hook: stdout is injected into the session context.
# POSIX sh port of session-context.ps1 (prints ../policy/haiku-delegation.md; silent and exit 0 when it cannot be read).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
cat "$KIT_SCRIPT_DIR/../policy/haiku-delegation.md" 2>/dev/null
exit 0
