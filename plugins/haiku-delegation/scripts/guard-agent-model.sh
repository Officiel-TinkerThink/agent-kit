#!/bin/sh
# PreToolUse hook (Agent), registered by the haiku-delegation plugin. A subagent that is not one of the kit agents (general-purpose, Explore, Plan, no type at all)
# runs on the main model (Sonnet or Opus) unless the call says `model: "haiku"`: about 20 to 40 times the cost of Haiku. Such a call without a Haiku model is blocked
# with the message that fixes it. The kit agents pin Haiku in their own definition (haiku-pinned.txt) and are never blocked. Only the main agent's calls are checked.
# POSIX sh port of guard-agent-model.ps1. Convenience guard, not a safety guard: any parse problem allows the call (fail-open).
# Set AGENT_MODEL_GUARD=off in the environment to disable it (for a task that really needs another model).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

[ "${AGENT_MODEL_GUARD:-on}" = "off" ] && exit 0
INPUT=$(cat)
_t=$(printf '%s' "$INPUT" | tr -d ' \t\r\n')
case "$_t" in \{*\}) ;; *) exit 0 ;; esac

AGENT_ID=$(json_get "$INPUT" agent_id)
case "$AGENT_ID" in ''|false|0|null) ;; *) exit 0 ;; esac

TYPE=$(json_get "$INPUT" tool_input.subagent_type)
case "$TYPE" in null) TYPE="" ;; esac
BASE="${TYPE##*:}"
if [ -n "$BASE" ] && tr -d '\r' < "$KIT_SCRIPT_DIR/haiku-pinned.txt" 2>/dev/null | awk -v a="$BASE" '$1 !~ /^#/ && $1 == a { f = 1 } END { exit !f }'; then exit 0; fi

SHOWN=$(printf '%s' "$TYPE" | tr -cd 'A-Za-z0-9:_-' | cut -c1-40)
[ -n "$SHOWN" ] || SHOWN="(no type)"

MODEL=$(json_get "$INPUT" tool_input.model)
case $(printf '%s' "$MODEL" | tr 'A-Z' 'a-z') in
  *haiku*) ;;
  *)
    printf '%s\n' "BLOCKED: the agent '$SHOWN' would run on the main model (Sonnet or Opus), about 20 to 40 times the cost of Haiku. Re-issue the call with the parameter model: \"haiku\", or use a kit agent for the job (for example haiku-delegation:code-explorer for reading). Keep the task atomic: one question and a few files per agent; split anything bigger into several agents launched in one message. To allow another model on purpose, set AGENT_MODEL_GUARD=off." >&2
    exit 2 ;;
esac

# a brief that holds several units of work: 4 or more numbered steps, or more than 4000 characters (AGENT_BRIEF_GUARD=off disables this check)
[ "${AGENT_BRIEF_GUARD:-on}" = "off" ] && exit 0
PROMPT=$(json_get "$INPUT" tool_input.prompt) || exit 0
STEPS=$(printf '%s\n' "$PROMPT" | awk '/^[ \t]*[0-9]+[.)][ \t]/ { n++ } END { print n + 0 }')
SIZE=$(printf '%s' "$PROMPT" | wc -c | tr -d ' ')
if [ "$STEPS" -ge 4 ] || [ "$SIZE" -gt 4000 ]; then
  printf '%s\n' "BLOCKED: the brief for '$SHOWN' holds several units of work ($STEPS numbered steps, $SIZE characters). A unit of work is the smallest piece of work that cannot be split any further, whether the pieces could run in parallel or one after another: one question or one deliverable with one result. Launch one agent per unit (independent units in the same message), each with a short brief: the one question, absolute paths, the output format. Keep the integration and the edits yourself. To allow a long brief on purpose, set AGENT_BRIEF_GUARD=off." >&2
  exit 2
fi
exit 0
