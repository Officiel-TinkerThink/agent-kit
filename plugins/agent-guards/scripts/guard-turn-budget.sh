#!/bin/sh
# PreToolUse hook (matcher: .*), registered by the agent-guards plugin. Counts the tool calls of each kit subagent (key: agent_id)
# and, when the N-th call arrives (N from turn-budget.txt), blocks that one call with a message telling the agent to stop, write its
# final report and start it with PARTIAL. It never blocks again: the real cap (maxTurns = 3 x N in the agent file) is the safety margin.
# Fails open on any internal error (a cost and reliability aid, not a compliance control). State: <kit data>/turn-budget/<agent_id>.
# POSIX sh port of guard-turn-budget.ps1.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

INPUT=$(cat)
_t=$(printf '%s' "$INPUT" | tr -d ' \t\r\n')
case "$_t" in \{*\}) ;; *) exit 0 ;; esac

AGENT_ID=$(json_get "$INPUT" agent_id)
case "$AGENT_ID" in ''|false|0|null) exit 0 ;; esac
case "$AGENT_ID" in *[!A-Za-z0-9_-]*) exit 0 ;; esac

TOOL=$(json_get "$INPUT" tool_name)
[ "$TOOL" = SubagentHandback ] && exit 0

TYPE=$(json_get "$INPUT" agent_type)
BASE="${TYPE##*:}"
[ -n "$BASE" ] || exit 0
N=$(tr -d '\r' < "$KIT_SCRIPT_DIR/turn-budget.txt" 2>/dev/null | awk -v a="$BASE" '$1 !~ /^#/ && $1 == a { print $2; exit }')   # tr: a table checked out with CRLF must still be read
case "$N" in ''|*[!0-9]*) exit 0 ;; esac
[ "$N" -gt 0 ] || exit 0

DIR="$(kit_data)/turn-budget"
F="$DIR/$AGENT_ID"
mkdir -p "$DIR" 2>/dev/null || { hook_error guard-turn-budget "cannot create $DIR"; exit 0; }
C=0
[ -f "$F" ] && C=$(cat "$F" 2>/dev/null)
case "$C" in ''|*[!0-9]*) C=0 ;; esac
C=$((C + 1))
printf '%s\n' "$C" > "$F" 2>/dev/null || { hook_error guard-turn-budget "cannot write $F"; exit 0; }
# a new agent: drop count files of finished runs older than a day (only inside the turn-budget folder)
if [ "$C" -eq 1 ]; then
  find "$DIR" -type f -mtime +1 -exec rm -f {} + 2>/dev/null
fi

if [ "$C" -eq "$N" ]; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): turn budget reached ($N tool calls). Stop calling tools and write your final report now. Its first line is PARTIAL, then list what you did not do or did not check. Use another tool only if the report cannot be written without it." >&2
  exit 2
fi
exit 0
