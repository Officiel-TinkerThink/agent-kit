#!/bin/sh
# PreToolUse hook (Write|Bash). Applies ONLY to the `annotator` subagent; everything else exits 0 untouched.
# The annotator may (a) create NEW .json files in agent-eval/inbox and (b) run exactly one command:
#   python <agent-eval>/annotate.py --file <agent-eval>/inbox/<name>.json
# Anything else is blocked. Fails CLOSED for the annotator (internal error -> block), open for every other agent.
# POSIX sh port of guard-annotator.ps1 (dash, busybox ash). Needs sh, sed, grep, awk and coreutils (sha256sum).

KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
LC_ALL=C
NL='
'

# block <message>: writes the reason to stderr and exits 2 (the harness refuses the tool call).
block() { printf '%s\n' "$1" >&2; exit 2; }

# ere_escape <text>: escapes ERE metacharacters so the text can sit inside a regular expression literally.
ere_escape() { printf '%s' "$1" | sed 's#[][\.*^$()+?{}|/]#\\&#g'; }

# --- hook input: one JSON object on stdin. A missing or unparsable field yields "" (the checks below then block).
INPUT=$(cat)
AGENT_TYPE=$(json_get "$INPUT" agent_type 2>/dev/null; printf x); AGENT_TYPE=${AGENT_TYPE%x}
agent_is "$AGENT_TYPE" annotator || exit 0

# Kit data folder as the ps1 prints it: forward slashes, no trailing slash.
KD=$(kit_data | sed 's#\\#/#g; s#/\{2,\}#/#g; s#/*$##')
[ -n "$KD" ] || block "BLOCKED: the annotator guard hit an internal error and fails closed. (kit data folder is empty)"
BASE="$KD/eval/inbox/"
BASE_RE=$(ere_escape "$KD/eval")
SELF="$KIT_SCRIPT_DIR/annotate.py"
SELF_HASH=$(sha256_of "$SELF")
[ -n "$SELF_HASH" ] || block "BLOCKED: the annotator guard hit an internal error and fails closed. (cannot hash $SELF)"

TOOL=$(json_get "$INPUT" tool_name 2>/dev/null; printf x); TOOL=${TOOL%x}
# PowerShell -eq is case-insensitive, so the tool name is compared in lower case.
TOOL_L=$(printf '%s' "$TOOL" | tr 'A-Z' 'a-z')

case "$TOOL_L" in
write)
  RAW=$(json_get "$INPUT" tool_input.file_path 2>/dev/null; printf x); RAW=${RAW%x}
  case "$RAW" in *"$NL"*) block "BLOCKED: the annotator may only write NEW .json files directly inside $BASE (letters, digits, _ . - in the name)." ;; esac
  # Backslashes are treated as separators, as in the ps1 (a test relies on this).
  P=$(printf '%s' "$RAW" | sed 's#\\#/#g')
  WRITE_RE='^'"$BASE_RE"'/inbox/[A-Za-z0-9_.-]+\.json$'
  OK=0
  if printf '%s\n' "$P" | grep -E -q -e "$WRITE_RE"; then OK=1; fi
  case "$P" in *..*) OK=0 ;; esac
  [ "$OK" = 1 ] || block "BLOCKED: the annotator may only write NEW .json files directly inside $BASE (letters, digits, _ . - in the name)."
  # Existence is checked on both the converted and the raw spelling, and symlinks count as existing.
  for X in "$P" "$RAW"; do
    if [ -e "$X" ] || [ -L "$X" ]; then
      block "BLOCKED: that file already exists; annotation files are never overwritten. Use a new unique file name."
    fi
  done
  exit 0
  ;;
bash)
  CMD=$(json_get "$INPUT" tool_input.command 2>/dev/null; printf x); CMD=${CMD%x}
  # .Trim(): strip leading and trailing whitespace, then reject any remaining line break (fail closed: a
  # line-oriented sed would otherwise match only the first line of a multi-line command).
  CMD=$(printf '%s' "$CMD" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  BASH_MSG="BLOCKED: the annotator may run only: python <plugin>/scripts/annotate.py --file ${BASE}<name>.json  (no pipes, chaining or other commands)."
  case "$CMD" in *"$NL"*) block "$BASH_MSG" ;; esac
  RE_PREFIX='^python3?[[:space:]]+"?([^"[:space:]]+/annotate\.py)"?[[:space:]]+--file[[:space:]]+"?('
  RE_SUFFIX='/inbox/[A-Za-z0-9_.-]+\.json)"?$'
  RE_ALL="$RE_PREFIX$BASE_RE$RE_SUFFIX"
  # Group 1 = script path, group 2 = annotation file. An empty group means no match.
  SCRIPT_PATH=$(printf '%s\n' "$CMD" | sed -n -E "s#$RE_ALL#\\1#p" 2>/dev/null)
  ANN_PATH=$(printf '%s\n' "$CMD" | sed -n -E "s#$RE_ALL#\\2#p" 2>/dev/null)
  if [ -z "$SCRIPT_PATH" ] || [ -z "$ANN_PATH" ]; then block "$BASH_MSG"; fi
  # The script must be THIS plugin's annotate.py, compared by content.
  if [ ! -f "$SCRIPT_PATH" ] || [ "$(sha256_of "$SCRIPT_PATH")" != "$SELF_HASH" ]; then
    block "BLOCKED: that is not the annotate.py shipped with this plugin."
  fi
  if [ ! -e "$ANN_PATH" ] && [ ! -L "$ANN_PATH" ]; then
    block "BLOCKED: write the annotation file first; it does not exist yet."
  fi
  exit 0
  ;;
*)
  exit 0
  ;;
esac
