#!/bin/sh
# SubagentStart hook (agent-eval). Appends ONE metadata line per started subagent to <KIT_DATA>/usage/agent-starts.jsonl: ids, agent type, time and the path where the
# subagent's transcript will be. A run the user stops never reaches SubagentStop, so it never gets a usage record; this line lets the annotator find such a run.
# Metadata only (no prompt, no answer). Fails open: any problem writes to hook-errors.log and exits 0; it never blocks the subagent and prints nothing.
# POSIX sh twin of subagent-start-log.ps1. Override the file with AGENT_START_LOG.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

INPUT=$(cat)
AGENT_ID=$(json_get "$INPUT" agent_id 2>/dev/null) || exit 0
case "$AGENT_ID" in ''|*[!A-Za-z0-9_-]*) exit 0 ;; esac
[ "${#AGENT_ID}" -le 100 ] || exit 0
SESSION=$(json_get "$INPUT" session_id 2>/dev/null) || SESSION=""
case "$SESSION" in *[!A-Za-z0-9_-]*) SESSION="" ;; esac
[ "${#SESSION}" -le 100 ] || SESSION=""
TYPE=$(json_get "$INPUT" agent_type 2>/dev/null) || TYPE=""
CWD=$(json_get "$INPUT" cwd 2>/dev/null) || CWD=""
TP=$(json_get "$INPUT" transcript_path 2>/dev/null) || TP=""

# the subagent's transcript sits next to the session transcript: <folder of the session file>/<session id>/subagents/agent-<id>.jsonl
TX=""
if [ -n "$TP" ] && [ -n "$SESSION" ]; then
  DIR=$(printf '%s' "$TP" | sed 's/[\\/][^\\/]*$//')
  [ -n "$DIR" ] && TX="$DIR/$SESSION/subagents/agent-$AGENT_ID.jsonl"
fi

LOG="${AGENT_START_LOG:-}"
[ -n "$LOG" ] || LOG="$(kit_data)/usage/agent-starts.jsonl"
REC=$(printf '{"schema":"agent-start/1","type":"start","ts":%s,"session_id":%s,"agent_id":%s,"agent_type":%s,"cwd":%s,"transcript":%s}' \
  "$(json_str "$(now_utc)")" "$(json_str "$SESSION")" "$(json_str "$AGENT_ID")" "$(json_str "$TYPE")" "$(json_str "$CWD")" "$(json_str "$TX")")
append_line "$LOG" "$REC" 2>/dev/null || hook_error subagent-start-log "start record not written: cannot append to $LOG"
exit 0
