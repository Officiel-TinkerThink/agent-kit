#!/bin/sh
# SubagentStart hook: tells selected subagents where this kit keeps its data (their prompts refer to KIT_DATA).
# POSIX sh port of inject-context.ps1. Needs sh, sed and coreutils (timeout, when present). Always exits 0 (fail open).

KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
LC_ALL=C
NL='
'

# --- bounded stdin read: an unread pipe must not hang the hook until the harness kills it.
if command -v timeout >/dev/null 2>&1; then
  INPUT=$(timeout 10 cat)
  RC=$?
  if [ "$RC" = 124 ]; then
    hook_error inject-context 'stdin not closed within 10 s; no context injected'
    exit 0
  fi
else
  INPUT=$(cat)
fi

# A hook input that is not a JSON object is traced and ignored.
TRIMMED=$(printf '%s' "$INPUT" | sed 's/^[[:space:]]*//')
case "$TRIMMED" in
  \{*) ;;
  *) hook_error inject-context 'stdin is not a JSON object; no context injected'; exit 0 ;;
esac

AGENT_TYPE=$(json_get "$INPUT" agent_type 2>/dev/null; printf x); AGENT_TYPE=${AGENT_TYPE%x}
agent_is "$AGENT_TYPE" annotator || exit 0

# Kit data folder and config folder, printed the way the ps1 prints them (forward slashes, no trailing slash).
KD=$(kit_data | sed 's#\\#/#g; s#/\{2,\}#/#g; s#/*$##')
CFG="${CLAUDE_CONFIG_DIR:-}"
if [ -z "$CFG" ]; then
  case "$KIT_SCRIPT_DIR" in */plugins/cache/*) CFG="${KIT_SCRIPT_DIR%%/plugins/cache/*}" ;; esac
fi
[ -n "$CFG" ] || CFG="${HOME:-/root}/.claude"
CFG=$(printf '%s' "$CFG" | sed 's#\\#/#g; s#/*$##')

CTX="KIT_DATA=$KD${NL}CONFIG_DIR=$CFG"
CTX_JSON=$(json_str "$CTX")
printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"SubagentStart\",\"additionalContext\":$CTX_JSON}}"
exit 0
