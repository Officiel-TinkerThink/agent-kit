#!/bin/sh
# PreToolUse hook (Grep|Read), registered by the agent-guards plugin. Applies ONLY to agents that must never read real env files.
# Blocks (exit 2): Read of a real env file, a Grep aimed at a real env file, and a directory-wide Grep that does not exclude env files.
# Example/template env files (.env.example, .env.sample, .env.template) stay readable.
# POSIX sh port of guard-env-files.ps1. Unparseable hook input is blocked (fail-closed), as in the .ps1.
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

# is_env <path>: a real env file (.env, .env.local, dir/.env ...), case-insensitive, not an example/template file.
is_env() {
  _l=$(printf '%s' "$1" | tr 'A-Z' 'a-z')
  rx_test "$_l" '(^|[\\/])\.env(\.[^\\/]*)?$' || return 1
  rx_test "$_l" '\.(example|sample|template)$' && return 1
  return 0
}

INPUT=$(cat)
json_ok "$INPUT" || { printf '%s\n' "BLOCKED: env guard error" >&2; exit 2; }

TYPE=$(json_get "$INPUT" agent_type)
agent_is "$TYPE" secret-candidate-lister config-drift-checker infra-reader compliance-lister annotator || exit 0

TOOL=$(json_get "$INPUT" tool_name)
TOOL_L=$(printf '%s' "$TOOL" | tr 'A-Z' 'a-z')

case "$TOOL_L" in
  read)
    P=$(json_get "$INPUT" tool_input.file_path)
    if is_env "$P"; then
      printf 'BLOCKED: real env files must not be read by this agent (%s). Example files (.env.example) are allowed.\n' "$P" >&2
      exit 2
    fi
    exit 0
    ;;
  grep)
    PATH_ARG=$(json_get "$INPUT" tool_input.path)
    GLOB=$(json_get "$INPUT" tool_input.glob)
    if [ -n "$PATH_ARG" ] && is_env "$PATH_ARG"; then
      printf 'BLOCKED: real env files must not be searched by this agent (%s).\n' "$PATH_ARG" >&2
      exit 2
    fi
    # A path with a short extension is a single file; anything else is a directory-wide search and must exclude env files.
    if ! rx_test "$PATH_ARG" '\.[[:alnum:]]{1,8}$'; then
      GLOB_L=$(printf '%s' "$GLOB" | tr 'A-Z' 'a-z')
      case "$GLOB_L" in
        '!**/.env'*) ;;
        *)
          printf '%s\n' 'BLOCKED: a directory-wide Grep must exclude real env files. Re-run with glob `"!**/.env*`" (or search named files individually).' >&2
          exit 2
          ;;
      esac
    fi
    exit 0
    ;;
esac
exit 0
