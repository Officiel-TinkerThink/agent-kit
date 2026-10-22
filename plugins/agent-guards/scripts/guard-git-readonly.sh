#!/bin/sh
# PreToolUse hook (Bash), registered by the agent-guards plugin. Applies ONLY to the changelog-summarizer subagent:
# allow a single read-only git command (optionally `git -C <path> ...`); block everything else.
# POSIX sh port of guard-git-readonly.ps1. Unparseable hook input is blocked (fail-closed), as in the .ps1.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

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

INPUT=$(cat)
json_ok "$INPUT" || { printf '%s\n' "BLOCKED: guard error" >&2; exit 2; }

TYPE=$(json_get "$INPUT" agent_type)
agent_is "$TYPE" changelog-summarizer || exit 0

CMD=$(json_get "$INPUT" tool_input.command)
LOWER=$(printf '%s' "$CMD" | tr 'A-Z' 'a-z')

# Read-only subcommand, optional -C <path> (quoted or bare) and optional --no-pager. Matched case-insensitively
# on the lower-cased command, as the .ps1 -match does.
RO=$(cat <<'RE'
^[[:space:]]*git[[:space:]]+(-c[[:space:]]+("[^"]+"|'[^']+'|[^[:space:];&|<>`$"']+)[[:space:]]+)?(--no-pager[[:space:]]+)?(diff|log|show|status|shortlog|blame|rev-parse|ls-files)([[:space:]]|$)
RE
)
# Case-sensitive deny list on the original command (the .ps1 uses -cnotmatch).
DENY='[;&|<>`$]|--output|--ext-diff|[[:space:]]-c[[:space:]]'

if rx_test "$LOWER" "$RO" && ! rx_test "$CMD" "$DENY"; then
  exit 0
fi
printf '%s\n' "BLOCKED: only a single read-only git command (diff, log, show, status, shortlog, blame, rev-parse, ls-files; optional -C <path>) is allowed for changelog-summarizer." >&2
exit 2
