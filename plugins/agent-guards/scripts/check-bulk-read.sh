#!/bin/sh
# PreToolUse hook (matcher: Read|Bash). Blocks whole-file reads of large text files in the MAIN
# conversation and redirects Claude to the Haiku-backed `code-explorer` subagent.
# Fails open on any internal error (cost optimisation only - not a compliance control).
# Threshold: env BULK_READ_MIN_LINES (default 200). Audit trail: <kit data>/audit/bulk-read-audit.jsonl.
# POSIX sh port of check-bulk-read.ps1. Line counting follows .NET StreamReader.ReadLine (LF, CRLF and CR).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

# Threshold: digits only, leading zeros dropped (dash arithmetic would read 0-prefixed numbers as octal).
MIN=200
case "${BULK_READ_MIN_LINES:-}" in
  ''|*[!0-9]*) ;;
  *)
    MIN=$(printf '%s' "$BULK_READ_MIN_LINES" | sed 's/^0*//')
    [ -n "$MIN" ] || MIN=0
    ;;
esac
# Values beyond the .ps1 [int] range make it fail outside its try block: fail open here.
[ "${#MIN}" -le 10 ] || exit 0

SKIP_EXT=" .png .jpg .jpeg .gif .webp .pdf .ipynb .svg "

# rx_test <text> <ere>: exit 0 when the ERE matches anywhere in text (pattern passed via the environment).
rx_test() {
  printf '%s' "$1" | RX_PAT="$2" awk 'BEGIN { RS = "\001"; re = ENVIRON["RX_PAT"] }
    { found = ($0 ~ re) } END { exit !found }'
}

# json_ok <text>: cheap structural check that the hook input is one JSON object.
json_ok() {
  _t=$(printf '%s' "$1" | tr -d ' \t\r\n')
  case "$_t" in \{*\}) return 0 ;; esac
  return 1
}

# has_value <json> <path>: the path exists and its value is not JSON null.
has_value() {
  _v=$(json_get "$1" "$2") || return 1
  [ "$_v" != "null" ]
}

# session_token <json>: the session_id as a JSON token (null when absent).
session_token() {
  if has_value "$1" session_id; then
    json_str "$(json_get "$1" session_id)"
  else
    printf 'null'
  fi
}

# write_audit <tool> <path> <lines> <decision> <session-json-token>: one JSONL record, never blocks.
write_audit() {
  _u="${USERNAME:-}"
  [ -n "$_u" ] || _u="${USER:-}"
  if [ -n "$_u" ]; then _uj=$(json_str "$_u"); else _uj=null; fi
  _rec=$(printf '{"ts":%s,"user":%s,"session":%s,"tool":%s,"path":%s,"lines":%s,"threshold":%s,"decision":%s}' \
    "$(json_str "$(now_utc)")" "$_uj" "$5" "$(json_str "$1")" "$(json_str "$2")" "$3" "$MIN" "$(json_str "$4")")
  append_line "$(kit_data)/audit/bulk-read-audit.jsonl" "$_rec" 2>/dev/null \
    || hook_error check-bulk-read "audit write failed: cannot append to the audit file"
}

# count_lines <file>: number of lines as .NET ReadLine counts them (LF, CRLF or CR terminators; a final unterminated line counts).
count_lines() {
  awk 'BEGIN { RS = "\r\n|\n|\r" } END { print NR + 0 }' < "$1"
}

# Trims surrounding double and single quotes, as the .ps1 Trim('"', "'") does.
trim_quotes() {
  printf '%s' "$1" | sed "s/^[\"']*//; s/[\"']*\$//"
}

INPUT=$(cat)
if ! json_ok "$INPUT"; then
  write_audit hook-error '' 0 "fail-open: invalid JSON hook input" '""'
  exit 0
fi

# Subagents (incl. code-explorer) may read freely.
AGENT_ID=$(json_get "$INPUT" agent_id)
case "$AGENT_ID" in
  ''|false|0|null) ;;
  *) exit 0 ;;
esac

TOOL=$(json_get "$INPUT" tool_name)
TOOL_L=$(printf '%s' "$TOOL" | tr 'A-Z' 'a-z')
TARGET=""

case "$TOOL_L" in
  read)
    # A targeted read (offset or limit present) is allowed.
    if has_value "$INPUT" tool_input.offset || has_value "$INPUT" tool_input.limit; then exit 0; fi
    TARGET=$(json_get "$INPUT" tool_input.file_path)
    ;;
  bash)
    CMD=$(json_get "$INPUT" tool_input.command)
    # Piped, compound or redirected commands are targeted use.
    if rx_test "$CMD" '[|;&<>`$]'; then exit 0; fi
    # Only a bare `cat|less|more <file>` is whole-file; head/tail are already bounded, anything else passes.
    BULK_RE=$(cat <<'RE'
^[[:space:]]*(cat|less|more)[[:space:]]+("[^"]+"|'[^']+'|[^[:space:]]+)[[:space:]]*$
RE
)
    rx_test "$(printf '%s' "$CMD" | tr 'A-Z' 'a-z')" "$BULK_RE" || exit 0
    # Target = the command minus its leading whitespace, the verb and the trailing whitespace (the regex group 2).
    TARGET=$(printf '%s' "$CMD" | awk 'BEGIN { RS = "\001"; ORS = "" }
      { sub(/^[[:space:]]*/, ""); sub(/^[^[:space:]]+[[:space:]]+/, ""); sub(/[[:space:]]*$/, ""); print }')
    ;;
esac
[ -n "$TARGET" ] || exit 0

RAW=$(trim_quotes "$TARGET")
case "$RAW" in
  /*) FULL="$RAW" ;;
  *)
    CWD=$(json_get "$INPUT" cwd)
    if [ -z "$CWD" ] || [ "$CWD" = "null" ]; then
      write_audit hook-error '' 0 "fail-open: relative path without a cwd" '""'
      exit 0
    fi
    FULL="${CWD%/}/$RAW"
    ;;
esac

[ -f "$FULL" ] || exit 0

# Extension of the file name (text after the last dot), case-insensitive, skipped when binary or visual.
BASE="${FULL##*/}"
case "$BASE" in
  *.*) EXT=".${BASE##*.}" ;;
  *) EXT="" ;;
esac
EXT=$(printf '%s' "$EXT" | tr 'A-Z' 'a-z')
case "$SKIP_EXT" in
  *" $EXT "*) [ -n "$EXT" ] && exit 0 ;;
esac

# Cheap pre-filter (<~20 bytes per line). ls works without read permission, as Get-Item does.
SIZE=$(ls -ln "$FULL" 2>/dev/null | awk '{ print $5 }')
if [ -z "$SIZE" ]; then
  write_audit hook-error '' 0 "fail-open: cannot stat $FULL" '""'
  exit 0
fi
[ "$SIZE" -lt "$((MIN * 20))" ] && exit 0

LINES=$(count_lines "$FULL" 2>/dev/null)
if [ -z "$LINES" ]; then
  write_audit hook-error '' 0 "fail-open: cannot read $FULL" '""'
  exit 0
fi
[ "$LINES" -le "$MIN" ] && exit 0

write_audit "$TOOL" "$FULL" "$LINES" blocked "$(session_token "$INPUT")"
printf "BLOCKED: '%s' has %s lines (limit %s). Do not read it whole in the main context. Delegate with the Agent tool: subagent_type='code-explorer', prompt = a first line 'Task kind: read', then the exact question + absolute file path(s). For edits or exact line numbers, re-issue Read with offset/limit on the relevant section instead.\n" "$FULL" "$LINES" "$MIN" >&2
exit 2
