#!/bin/sh
# PreToolUse hook (Bash). Blocks FOREGROUND monitor-style commands that stream or poll into the conversation:
# tail -f, watch, Get-Content -Wait, docker/kubectl/journalctl logs -f, and unbounded `while true` loops.
# Background runs (run_in_background=true) are allowed. Fail-open on any internal error.
# POSIX sh port of guard-monitor-patterns.ps1 (same verdicts, same stderr text, same exit codes).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

# rx_test <text> <ere>: exit 0 when the ERE matches anywhere in text. The pattern is passed through the
# environment (no shell or awk escape processing). "@NL@" stands for [^<newline>] (.NET '.' does not match newline).
rx_test() {
  printf '%s' "$1" | RX_PAT="$2" awk 'BEGIN { RS = "\001"; re = ENVIRON["RX_PAT"]
      while ((k = index(re, "@NL@")) > 0) re = substr(re, 1, k - 1) "[^\n]" substr(re, k + 4) }
    { found = ($0 ~ re) } END { exit !found }'
}

# json_ok <text>: cheap structural check that the hook input is one JSON object (fail-open paths decide on it).
json_ok() {
  _t=$(printf '%s' "$1" | tr -d ' \t\r\n')
  case "$_t" in \{*\}) return 0 ;; esac
  return 1
}

# Strips quoted segments ('...' and "...") to "" as the .ps1 does, then lower-cases and prefixes ";" so that
# every "start of text" and "word boundary" test becomes an explicit non-word character before the token.
STRIP_PROG=$(cat <<'AWK'
BEGIN { RS = "\001"; ORS = "" }
{ gsub(/'[^']*'|"[^"]*"/, "\"\""); print ";" tolower($0) }
AWK
)

INPUT=$(cat)
json_ok "$INPUT" || exit 0
TOOL=$(json_get "$INPUT" tool_name)
[ "$TOOL" = "Bash" ] || exit 0
BG=$(json_get "$INPUT" tool_input.run_in_background)
[ "$BG" = "true" ] && exit 0
CMD=$(json_get "$INPUT" tool_input.command)
S=$(printf '%s' "$CMD" | awk "$STRIP_PROG")

reason=""
if rx_test "$S" '[^[:alnum:]_]tail[[:space:]]+(-[[:alpha:]]*f[[:alpha:]]*|--follow)([^[:alnum:]_]|$)'; then
  reason='`tail -f`'
elif rx_test "$S" '([;&|(][[:space:]]*|[^[:alnum:]_](sudo|nohup|env|timeout[[:space:]]+[^[:space:]]+)[[:space:]]+)watch[[:space:]]'; then
  reason='`watch`'
elif rx_test "$S" 'get-content([^[:alnum:]_]@NL@*)?[[:space:]]-wait([^[:alnum:]_]|$)'; then
  reason='`Get-Content -Wait`'
elif rx_test "$S" '[^[:alnum:]_](docker([[:space:]]+compose)?|kubectl|journalctl)([^[:alnum:]_]@NL@*)?[[:space:]](-f|--follow)([^[:alnum:]_]|$)'; then
  reason='a follow-mode log command (`logs -f`)'
elif rx_test "$S" '[^[:alnum:]_]while[[:space:]]+(true([^[:alnum:]_]|$)|:[[:alnum:]_]|[[][[:space:]]*1[[:space:]]*[]][[:alnum:]_])' \
  && ! rx_test "$S" '[^[:alnum:]_](break|exit)([^[:alnum:]_]|$)' \
  && ! rx_test "$S" '[^[:alnum:]_]timeout([^[:alnum:]_]|$)'; then
  reason='an unbounded `while true` loop'
elif rx_test "$S" '[^[:alnum:]_]until[[:space:]]+false([^[:alnum:]_]|$)' \
  && ! rx_test "$S" '[^[:alnum:]_](break|exit)([^[:alnum:]_]|$)'; then
  reason='an unbounded `until false` loop'
fi

[ -n "$reason" ] || exit 0
printf 'BLOCKED: %s' "$reason" >&2
cat >&2 <<'MSG'
 in the foreground streams or polls output into the conversation and re-bills the whole context on every turn. Use ONE of: (a) Bash with run_in_background=true and a command that exits when the condition is true, e.g. [until grep -q READY app.log; do sleep 1; done] (a single completion notification); (b) the Monitor tool with a filtered stream, e.g. [tail -f app.log | grep --line-buffered -E 'ERROR|Traceback|FAILED|READY'], whose filter covers failure states as well as success; (c) a bounded check that prints a few lines and exits, e.g. [tail -n 20 app.log].
MSG
exit 2
