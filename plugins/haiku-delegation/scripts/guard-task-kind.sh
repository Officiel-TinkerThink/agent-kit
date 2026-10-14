#!/bin/sh
# PreToolUse hook (Agent), registered by the haiku-delegation plugin. The merged agents code-explorer and contracts-reader serve several kinds of task;
# the brief must start with `Task kind: <kind>` (several kinds separated by commas). Without it the agent has to guess the section and the usage log cannot
# pick the footer checks. A brief with no valid kind line is blocked once, with the message the main agent needs to fix it.
# POSIX sh port of guard-task-kind.ps1. Convenience guard, not a safety guard: any parse problem allows the call (fail-open).
# Set TASK_KIND_GUARD=off in the environment to disable it.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

[ "${TASK_KIND_GUARD:-on}" = "off" ] && exit 0
INPUT=$(cat)
_t=$(printf '%s' "$INPUT" | tr -d ' \t\r\n')
case "$_t" in \{*\}) ;; *) exit 0 ;; esac

TYPE=$(json_get "$INPUT" tool_input.subagent_type) || exit 0
BASE=$(printf '%s' "$TYPE" | sed 's/^.*://')
case "$BASE" in
  code-explorer)    VALID="locate read map inventory tests" ;;
  contracts-reader) VALID="schema api-spec migrations api-match" ;;
  *) exit 0 ;;
esac

PROMPT=$(json_get "$INPUT" tool_input.prompt) || exit 0
FIRST=$(printf '%s\n' "$PROMPT" | awk 'NF { print; exit }')
KINDS=$(printf '%s' "$FIRST" | sed -n 's/^[[:space:]]*Task kind:[[:space:]]*//p' | tr ',' ' ')

fail() {
  printf '%s\n' "BLOCKED: the brief for $BASE must start with a first line 'Task kind: <kind>'. $1 Valid kinds: $(printf '%s' "$VALID" | sed 's/ /, /g') (several kinds separated by commas when the task mixes them). Example first line: 'Task kind: $(printf '%s' "$VALID" | awk '{ print $1 }')'. Re-issue the call with that line added; nothing else changes." >&2
  exit 2
}

[ -n "$KINDS" ] || fail "No such line was found."
for k in $KINDS; do
  case " $VALID " in *" $k "*) ;; *) fail "'$k' is not a kind of this agent." ;; esac
done
exit 0
