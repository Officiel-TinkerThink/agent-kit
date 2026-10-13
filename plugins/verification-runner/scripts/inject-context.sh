#!/bin/sh
# inject-context.sh - SubagentStart hook: tells verification-runner subagents where this kit keeps its data
# (POSIX sh port of inject-context.ps1). Fails open: any internal error is traced to hook-errors.log and exits 0.
LC_ALL=C
export LC_ALL
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

# Bounded stdin read: an unread pipe must not hang the hook until the harness kills it.
if command -v timeout >/dev/null 2>&1; then
  INPUT=$(timeout 10 cat)
  ic_rc=$?
  if [ "$ic_rc" = 124 ]; then
    hook_error inject-context 'stdin not closed within 10 s; no context injected'
    exit 0
  fi
else
  INPUT=$(cat)
fi

ic_t=$(printf '%s' "$INPUT" | tr -d ' \t\r\n')
[ -n "$ic_t" ] || exit 0
case "$ic_t" in
  "{"*) ;;
  *) hook_error inject-context 'input is not a JSON object; no context injected'; exit 0 ;;
esac

ic_type=$(json_get "$INPUT" agent_type) || ic_type=""
agent_is "$ic_type" verification-runner || exit 0

ic_data=$(kit_data)
if ! mkdir -p "$ic_data/verification-logs" 2>/dev/null; then
  hook_error inject-context "cannot create $ic_data/verification-logs; no context injected"
  exit 0
fi

ic_cfg=${CLAUDE_CONFIG_DIR:-}
if [ -z "$ic_cfg" ]; then
  case "$KIT_SCRIPT_DIR" in
    */plugins/cache/*) ic_cfg=${KIT_SCRIPT_DIR%%/plugins/cache/*} ;;
  esac
fi
[ -n "$ic_cfg" ] || ic_cfg="${HOME:-/root}/.claude"
ic_cfg=$(printf '%s' "$ic_cfg" | sed 's:/*$::')
ic_data=$(printf '%s' "$ic_data" | sed 's:/*$::')

ic_ctx="KIT_DATA=$ic_data
CONFIG_DIR=$ic_cfg"
ic_json=$(json_str "$ic_ctx")
printf '{"hookSpecificOutput":{"hookEventName":"SubagentStart","additionalContext":%s}}\n' "$ic_json"
exit 0
