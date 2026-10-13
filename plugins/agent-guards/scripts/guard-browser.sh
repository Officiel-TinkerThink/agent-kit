#!/bin/sh
# PreToolUse hook (mcp__claude-in-chrome__*), registered by the agent-guards plugin. POSIX sh port of guard-browser.ps1.
# Applies ONLY to browser-explorer and browser-operator.
# browser-explorer: read-only. Tool allowlist; `computer` limited to screenshot|wait|scroll|scroll_to|zoom|hover.
# browser-operator: tool allowlist; every click/type/key/form_input must carry an action_summary, and a summary that names an
#   irreversible effect (submit, delete, send, pay, approve, sign, confirm, export, publish...) is blocked: the agent reports instead.
# Both: navigate / url must be http(s) (no file:, chrome:, javascript:, data:); optional host allowlist in <KIT_DATA>/browser-policy.json {"allowedHosts":[...]}.
# Every operator decision (allowed or blocked) is appended to <KIT_DATA>/audit/browser-actions.jsonl (typed text is never logged, only its length).
# The main thread is redirected to those agents for browser tools (override: AGENT_KIT_BROWSER_MAIN=allow); other agents are not affected (exit 0).
# Unparseable input fails open; for the two guarded agents an internal error fails closed (exit 2).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

PREFIX='mcp__claude-in-chrome__'
READ_TOOLS='tabs_context_mcp, tabs_create_mcp, tabs_close_mcp, navigate, read_page, get_page_text, find, read_console_messages, read_network_requests, computer'
ENTER_RE='(^|[[:space:]+])(enter|return)($|[[:space:]+])'
IRREV_RE='(^|[^a-z0-9_])(submit|delet|remov|send|pay|purchas|buy|approv|sign|confirm|export|publish|post|transfer|discard|reset)[a-z0-9_]*|(^|[^a-z0-9_])(clos[a-z0-9_]* account|cancel[a-z0-9_]* (order|subscription))([^a-z0-9_]|$)'
ARRAY_OF_STRINGS_RE='^\[[[:space:]]*(("([^"\\]|\\.)*")[[:space:]]*(,[[:space:]]*("([^"\\]|\\.)*")[[:space:]]*)*)?\]$'

GUARDED=0
IS_EXP=0
IS_OP=0
GS=''
INPUT=''
AGENT_TYPE=''
FULL=''
TOOL=''
TOOL_L=''
SESSION_ID=''
ACTION_RAW=''
ACT_L=''
SUMMARY=''
TEXT_RAW=''
URL_RAW=''
TABID_JSON='null'
TEXT_LEN='0'
ALLOWED_TXT=''

# --- helpers ---------------------------------------------------------------------------------------------

to_lower() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }

# true when the value of a top-level or nested key is a JSON string (the key appears as "key": "...").
is_string_key() { printf '%s' "$INPUT" | LC_ALL=C grep -Eq "\"$1\"[[:space:]]*:[[:space:]]*\""; }

# get_s <dotted.path>  sets GS to the decoded value; '' when absent or JSON null (trailing newlines kept).
get_s() {
  GS=$(json_get "$INPUT" "$1"; printf x)
  GS=${GS%x}
  if [ "$GS" = null ] && ! is_string_key "${1##*.}"; then GS=''; fi
}

# characters (code points) of a text; '' -> 0. The ps1 counts UTF-16 units, which differs only for characters outside the BMP.
text_length() {
  if [ -z "$1" ]; then printf 0; return 0; fi
  _tl=$(printf '%s' "$1" | LC_ALL=C.UTF-8 wc -m 2>/dev/null) || _tl=$(printf '%s' "$1" | wc -c)
  printf '%s' "$_tl" | tr -d ' \t'
}

write_hook_error() {
  printf 'guard-browser: %s\n' "$1" >&2
  hook_error guard-browser "$1"
}

# audit_write <decision> <tool> <reason>: appends one JSONL record. Returns non-zero when it cannot be written.
audit_write() {
  _adir="$(kit_data)/audit"
  _pol_hash=null
  _pf="$(kit_data)/browser-policy.json"
  if [ -e "$_pf" ]; then
    _h=$(sha256_of "$_pf")
    if [ -n "$_h" ]; then _pol_hash=$(json_str "$_h"); fi
  fi
  _ts=$(date '+%Y-%m-%dT%H:%M:%S.%3N%:z')
  _rec="{\"ts\":$(json_str "$_ts"),\"agent\":$(json_str "$AGENT_TYPE"),\"session\":$(json_str "$SESSION_ID"),\"tool\":$(json_str "$2"),\"decision\":$(json_str "$1"),\"action\":$(json_str "$ACTION_RAW"),\"summary\":$(json_str "$SUMMARY"),\"tabId\":$TABID_JSON,\"url\":$(json_str "$URL_RAW"),\"text_len\":$TEXT_LEN,\"reason\":$(json_str "$3"),\"policy_sha256\":$_pol_hash}"
  if ! mkdir -p "$_adir" 2>/dev/null || ! append_line "$_adir/browser-actions.jsonl" "$_rec"; then
    write_hook_error "audit write failed ($1 $2): $_adir/browser-actions.jsonl is not writable"
    return 1
  fi
  return 0
}

# block <audit 1|0> <tool> <message>: records a blocked decision when asked, prints BLOCKED on stderr, exits 2.
block() {
  if [ "$1" = 1 ]; then audit_write blocked "$2" "$3" || true; fi
  printf 'BLOCKED: %s\n' "$3" >&2
  exit 2
}

# internal_error <detail>: fails closed for the guarded agents, open for every other agent.
internal_error() {
  if [ "$GUARDED" = 1 ]; then
    printf 'BLOCKED: the browser guard hit an internal error and fails closed for this agent. (%s)\n' "$1" >&2
    exit 2
  fi
  exit 0
}

# add_blocked_request <kind> <value> <agent>: feeds /kit-allow; best effort, never fails the hook.
add_blocked_request() {
  _bdir="$(kit_data)/audit"
  mkdir -p "$_bdir" 2>/dev/null || return 0
  _bval=$(printf '%s' "$2" | cut -c1-300)
  _bts=$(date -u '+%Y-%m-%dT%H:%M:%S.%3NZ')
  append_line "$_bdir/blocked-requests.jsonl" "{\"ts\":$(json_str "$_bts"),\"kind\":$(json_str "$1"),\"value\":$(json_str "$_bval"),\"agent\":$(json_str "$3")}" 2>/dev/null || true
}

# check_host_policy <policy file> <lower-case host>: enforces allowedHosts. Fails closed when the policy is unreadable or invalid.
check_host_policy() {
  _praw=$(sed '1s/^\xef\xbb\xbf//' "$1") || internal_error "browser-policy.json is not readable"
  _pcompact=$(printf '%s' "$_praw" | tr -d ' \t\r\n')
  case "$_pcompact" in
    '{'*'}') ;;
    *) internal_error "browser-policy.json is not a JSON object" ;;
  esac
  json_has "$_praw" allowedHosts || internal_error "browser-policy.json has no allowedHosts"
  _arr=$(json_get "$_praw" allowedHosts; printf x)
  _arr=${_arr%x}
  _aflat=$(printf '%s' "$_arr" | tr -d '\r\n\t')
  printf '%s' "$_aflat" | LC_ALL=C grep -Eq "$ARRAY_OF_STRINGS_RE" || internal_error "allowedHosts must be an array of strings"
  _idx=0
  _hit=0
  while json_has "$_arr" "$_idx"; do
    _entry=$(json_get "$_arr" "$_idx"; printf x)
    _entry=${_entry%x}
    if [ "$(to_lower "$_entry")" = "$2" ]; then _hit=1; fi
    _idx=$((_idx + 1))
  done
  if [ "$_idx" -gt 0 ] && [ "$_hit" = 0 ]; then
    add_blocked_request host "$2" "$AGENT_TYPE"
    block "$IS_OP" "$TOOL" "Host '$2' is not in allowedHosts of browser-policy.json. Report the URL to the main agent, which asks the user whether to allow this host (/agent-guards:kit-allow); never open it another way."
  fi
}

# check_navigate_url <raw url>: scheme, parseability and host allowlist checks for navigate.
check_navigate_url() {
  _u=$(printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  _ul=$(to_lower "$_u")
  if [ "$_ul" = back ] || [ "$_ul" = forward ]; then return 0; fi
  case "$_ul" in
    file:*|chrome:*|chrome-extension:*|javascript:*|data:*|view-source:*|about:*|blob:*|ftp:*)
      block "$IS_OP" "$TOOL" "URL scheme not allowed: only http(s) pages may be opened." ;;
  esac
  _clean=$(printf '%s' "$_u" | LC_ALL=C tr -d '\000-\037\177')
  if [ "$_clean" != "$_u" ]; then block "$IS_OP" "$TOOL" "Unparseable URL."; fi
  if printf '%s' "$_u" | LC_ALL=C grep -Eq '^[A-Za-z][A-Za-z0-9+.-]*://'; then
    _scheme=$(to_lower "${_u%%://*}")
    case "$_scheme" in
      http|https) ;;
      *) block "$IS_OP" "$TOOL" "URL scheme not allowed: only http(s) pages may be opened." ;;
    esac
    _rest=${_u#*://}
  elif printf '%s' "$_u" | LC_ALL=C grep -Eq '^[A-Za-z][A-Za-z0-9+.-]*:([^0-9]|$)'; then
    block "$IS_OP" "$TOOL" "URL scheme not allowed: only http(s) pages may be opened."
  else
    _rest=$_u
  fi
  _auth=${_rest%%[/?#]*}
  case "$_auth" in *@*) _auth=${_auth##*@} ;; esac
  case "$_auth" in
    \[*)
      case "$_auth" in *\]*) ;; *) block "$IS_OP" "$TOOL" "Unparseable URL." ;; esac
      _host=${_auth%%]*}
      _host=${_host#\[}
      _after=${_auth#*]}
      case "$_after" in
        '') _port='' ;;
        :*) _port=${_after#:} ;;
        *) block "$IS_OP" "$TOOL" "Unparseable URL." ;;
      esac
      ;;
    *)
      case "$_auth" in
        *:*) _host=${_auth%%:*}; _port=${_auth#*:} ;;
        *) _host=$_auth; _port='' ;;
      esac
      ;;
  esac
  case "$_port" in
    '') ;;
    *[!0-9]*) block "$IS_OP" "$TOOL" "Unparseable URL." ;;
    *)
      if [ "${#_port}" -gt 5 ] || [ "$_port" -gt 65535 ]; then block "$IS_OP" "$TOOL" "Unparseable URL."; fi
      ;;
  esac
  if [ -z "$_host" ]; then block "$IS_OP" "$TOOL" "Unparseable URL."; fi
  _bad=$(printf '%s' "$_host" | LC_ALL=C tr -d 'A-Za-z0-9._:\200-\377-')
  if [ -n "$_bad" ]; then block "$IS_OP" "$TOOL" "Unparseable URL."; fi
  _hl=$(to_lower "$_host")
  _pf="$(kit_data)/browser-policy.json"
  if [ -e "$_pf" ]; then check_host_policy "$_pf" "$_hl"; fi
}

# --- hook body -------------------------------------------------------------------------------------------

INPUT=$(cat)
_compact=$(printf '%s' "$INPUT" | tr -d ' \t\r\n')
case "$_compact" in
  '{'*'}') ;;
  *) exit 0 ;;
esac

get_s agent_type
AGENT_TYPE=$GS
get_s tool_name
FULL=$GS

if agent_is "$AGENT_TYPE" browser-explorer; then IS_EXP=1; fi
if agent_is "$AGENT_TYPE" browser-operator; then IS_OP=1; fi

# Main thread: browser tool calls are redirected to the browser agents (raw page dumps and screenshots would fill the main context).
if [ "$IS_EXP" = 0 ] && [ "$IS_OP" = 0 ]; then
  if [ -z "$AGENT_TYPE" ]; then
    case "$FULL" in
      "$PREFIX"*)
        if [ "$(to_lower "${AGENT_KIT_BROWSER_MAIN:-}")" != allow ]; then
          printf '%s\n' "BLOCKED: do not call the browser tools from the main thread. Delegate with the Agent tool: subagent_type='browser-explorer' to open and read pages (read-only), or 'browser-operator' for named click/fill steps. Put the exact URL(s), the question, and what to report in the prompt. (Set AGENT_KIT_BROWSER_MAIN=allow to override.)" >&2
          exit 2
        fi
        ;;
    esac
  fi
  exit 0
fi

GUARDED=1
case "$FULL" in
  "$PREFIX"*) ;;
  *) exit 0 ;;
esac
TOOL=${FULL#"$PREFIX"}
TOOL_L=$(to_lower "$TOOL")

get_s session_id
SESSION_ID=$GS
get_s tool_input.action
ACTION_RAW=$GS
ACT_L=$(to_lower "$ACTION_RAW")
get_s tool_input.action_summary
SUMMARY=$GS
get_s tool_input.text
TEXT_RAW=$GS
get_s tool_input.url
URL_RAW=$GS
TEXT_LEN=$(text_length "$TEXT_RAW")

if json_has "$INPUT" tool_input.tabId; then
  GS=$(json_get "$INPUT" tool_input.tabId; printf x)
  GS=${GS%x}
  if [ -z "$GS" ]; then
    TABID_JSON=null
  elif printf '%s' "$INPUT" | LC_ALL=C grep -Eq '"tabId"[[:space:]]*:[[:space:]]*"'; then
    TABID_JSON=$(json_str "$GS")
  else
    TABID_JSON=$GS
  fi
else
  TABID_JSON=null
fi

if [ "$IS_OP" = 1 ]; then
  ALLOWED_TXT="$READ_TOOLS, form_input"
else
  ALLOWED_TXT=$READ_TOOLS
fi

_ok=0
case "$TOOL_L" in
  tabs_context_mcp|tabs_create_mcp|tabs_close_mcp|navigate|read_page|get_page_text|find|read_console_messages|read_network_requests|computer)
    _ok=1 ;;
  form_input)
    if [ "$IS_OP" = 1 ]; then _ok=1; fi ;;
esac
if [ "$_ok" = 0 ]; then
  block "$IS_OP" "$TOOL" "$TOOL is not available to $AGENT_TYPE. Allowed: $ALLOWED_TXT. Report to the main agent what you needed."
fi

if [ "$TOOL_L" = navigate ] && [ -n "$URL_RAW" ]; then
  check_navigate_url "$URL_RAW"
fi

if [ "$TOOL_L" = computer ] && [ "$IS_EXP" = 1 ]; then
  case "$ACT_L" in
    screenshot|wait|scroll|scroll_to|zoom|hover) ;;
    *) block 0 "$TOOL" "browser-explorer is read-only: computer action '$ACTION_RAW' is not allowed (allowed: screenshot, wait, scroll, scroll_to, zoom, hover). Report to the main agent that this task needs the browser-operator." ;;
  esac
fi

if [ "$IS_OP" = 1 ]; then
  NEEDS=0
  case "$TOOL_L" in
    form_input) NEEDS=1 ;;
    computer)
      case "$ACT_L" in
        left_click|right_click|double_click|triple_click|left_click_drag|type|key) NEEDS=1 ;;
      esac
      ;;
  esac
  if [ "$NEEDS" = 1 ]; then
    if [ "$TOOL_L" = computer ] && [ "$ACT_L" = key ] && printf '%s' "$(to_lower "$TEXT_RAW")" | LC_ALL=C grep -Eq "$ENTER_RE"; then
      block 1 "$TOOL" "Pressing Enter can submit a form without naming it. Use the visible control by its ref instead, or stop and report."
    fi
    if [ -z "$(printf '%s' "$SUMMARY" | tr -d ' \t\r\n\013\014')" ]; then
      block 1 "$TOOL" "action_summary is required on every click, type, key and form_input: state the effect and what it acts on."
    fi
    if printf '%s' "$(to_lower "$SUMMARY")" | LC_ALL=C grep -Eq "$IRREV_RE"; then
      block 1 "$TOOL" "action_summary '$SUMMARY' names an irreversible or outward-facing effect. Do not perform it: stop and report to the main agent what you were about to do. The main agent must ask the user before any other route to this step."
    fi
  fi
  # No record, no action: an operator step that cannot be audited is not performed.
  if ! audit_write allowed "$TOOL" ""; then
    block 0 "$TOOL" "the audit trail could not be written to $(kit_data)/audit (see hook-errors.log), so this operator action is not allowed. Report to the main agent that the browser audit log is not writable."
  fi
fi

exit 0
