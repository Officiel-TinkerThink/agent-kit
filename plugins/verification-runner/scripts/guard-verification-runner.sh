#!/bin/sh
# guard-verification-runner.sh - PreToolUse hook (Bash). POSIX sh port of guard-verification-runner.ps1.
# Applies ONLY to the verification-runner subagent. Which commands it may run is decided by Claude Code's own permissions
# (settings allow / ask / deny rules): this hook stays silent (exit 0) for them. It protects what permission rules cannot express:
#   - `rm` is validated against the safe-rm policy and REWRITTEN to the safe-rm.sh executor (updatedInput): items go to quarantine,
#     nothing is deleted. A delete hidden inside a longer command line is refused (exit 2): only a bare
#     `rm [-r] [-f] <absolute paths>` line is accepted.
#   - evidence logs: a redirect into <KIT_DATA>/verification-logs must create a NEW file (no >>, no .., no overwrite).
# Other agents and the main thread are not affected (exit 0). Unparseable input fails open; an internal error fails closed
# for the runner (exit 2).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
LC_ALL=C
export LC_ALL

TAB=$(printf '\t')
NL=$(printf '\n_')
NL=${NL%_}

INPUT=$(cat)

fail_closed() {
  printf 'BLOCKED: the verification-runner guard hit an internal error and fails closed for this agent. (%s)\n' "$1" >&2
  exit 2
}

# redirect_targets <command> <log root>: one line per redirect into the log root, "op TAB target" (op is > or >>).
# Only the target chars up to a shell delimiter are taken; no regex, no lookbehind.
redirect_targets() {
  RT_CMD=$1 RT_ROOT=$2 awk '
    BEGIN {
      c = ENVIRON["RT_CMD"]; root = ENVIRON["RT_ROOT"]
      DQ = sprintf("%c", 34); SQ = sprintf("%c", 39)
      delims = " \t\r\n" DQ SQ "<>|;&"
      rl = length(root) + 1; n = length(c); i = 1
      while (i <= n) {
        if (substr(c, i, 1) != ">") { i++; continue }
        op = ">"; j = i + 1
        if (substr(c, j, 1) == ">") { op = ">>"; j++ }
        while (substr(c, j, 1) == " " || substr(c, j, 1) == "\t") j++
        q = substr(c, j, 1)
        if (q == DQ || q == SQ) j++
        if (substr(c, j, rl) == root "/") {
          t = ""
          while (j <= n && index(delims, substr(c, j, 1)) == 0) { t = t substr(c, j, 1); j++ }
          printf "%s\t%s\n", op, t
          i = j
        } else i = i + length(op)
      }
    }'
}

agent=$(json_get "$INPUT" agent_type) || agent=""
agent_is "$agent" verification-runner || exit 0
tool=$(json_get "$INPUT" tool_name) || tool=""
[ "$tool" = Bash ] || exit 0
cmd=$(json_get "$INPUT" tool_input.command) || cmd=""
cmd=$(printf '%s' "$cmd" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

is_rm=0
case "$cmd" in
  rm|"rm "*|"rm$TAB"*|"rm$NL"*) is_rm=1 ;;
esac

# --- rm: validated against the safe-rm policy and rewritten to the safe-rm.sh executor (quarantine, audit first) ---
if [ "$is_rm" = 1 ]; then
  [ -f "$KIT_SCRIPT_DIR/safe-rm-lib.sh" ] || fail_closed "safe-rm-lib.sh not found next to the guard"
  . "$KIT_SCRIPT_DIR/safe-rm-lib.sh"
  srm_load_policy || fail_closed "$SRM_REASON"
  if ! srm_parse_command "$cmd"; then
    printf 'BLOCKED: %s. rm accepts: rm [-r] [-f] <absolute path>... (plain /-separated paths, or quoted).\n' "$SRM_REASON" >&2
    exit 2
  fi
  REC=$SRM_RECURSE
  TOKS=$SRM_TOKENS
  if ! srm_resolve_lines "$REC" "$TOKS"; then
    printf 'BLOCKED by safe-rm policy: %s\n' "$SRM_REASON" >&2
    exit 2
  fi

  sess=$(json_get "$INPUT" session_id 2>/dev/null | sed 's/[^A-Za-z0-9-]//g')
  srm_has_forbidden "$KIT_SCRIPT_DIR" && fail_closed "the scripts folder path contains a character that cannot be quoted"
  NEWCMD="sh \"$KIT_SCRIPT_DIR/safe-rm.sh\""
  if [ "$REC" = 1 ]; then NEWCMD="$NEWCMD -Recurse"; fi
  NEWCMD="$NEWCMD -Agent verification-runner -Session \"$sess\""
  while IFS= read -r rm_t; do
    [ -n "$rm_t" ] || continue
    srm_full_path "$rm_t" || fail_closed "$SRM_REASON"
    NEWCMD="$NEWCMD \"$SRM_PATH\""
  done <<EOF_RM_TOKS
$TOKS
EOF_RM_TOKS

  # keep the other tool_input members that are present (type-checked; anything else is not carried over)
  UI_EXTRA=""
  if json_has "$INPUT" tool_input.description; then
    UI_EXTRA="$UI_EXTRA, \"description\": $(json_str "$(json_get "$INPUT" tool_input.description)")"
  fi
  if json_has "$INPUT" tool_input.timeout; then
    rm_v=$(json_get "$INPUT" tool_input.timeout)
    case "$rm_v" in
      ''|*[!0-9]*) ;;
      *) UI_EXTRA="$UI_EXTRA, \"timeout\": $rm_v" ;;
    esac
  fi
  for rm_b in run_in_background dangerouslyDisableSandbox; do
    if json_has "$INPUT" "tool_input.$rm_b"; then
      rm_v=$(json_get "$INPUT" "tool_input.$rm_b")
      case "$rm_v" in
        true|false) UI_EXTRA="$UI_EXTRA, \"$rm_b\": $rm_v" ;;
      esac
    fi
  done

  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s,"updatedInput":{"command":%s%s}}}\n' \
    "$(json_str 'safe-rm: validated against policy; items are moved to quarantine (restorable), not deleted')" \
    "$(json_str "$NEWCMD")" "$UI_EXTRA"
  exit 0
fi

# a delete inside a longer command line would bypass the quarantine
if printf '%s\n' "$cmd" | grep -Eiq '(^|[;&|`(]|[[:space:]])(rm|rmdir|rd|del|erase|unlink|shred|Remove-Item)([[:space:]]|$)'; then
  printf '%s\n' "BLOCKED: deletions by verification-runner are only accepted as a bare line: rm [-r] [-f] <absolute paths> (they are moved to a restorable quarantine). Do not put rm, del or Remove-Item inside another command." >&2
  exit 2
fi

# --- evidence logs: a redirect into the verification-logs folder must create a NEW file ---
LOGROOT="$(kit_data)/verification-logs"
mkdir -p "$LOGROOT" 2>/dev/null || fail_closed "cannot create $LOGROOT"
RT=$(redirect_targets "$cmd" "$LOGROOT") || fail_closed "the redirect scan failed"
while IFS="$TAB" read -r rt_op rt_tgt; do
  [ -n "$rt_op" ] || continue
  if [ "$rt_op" = '>>' ]; then
    printf '%s\n' "BLOCKED: appending (>>) to a verification log would alter earlier evidence. Redirect to a NEW file with >." >&2
    exit 2
  fi
  case "/$rt_tgt/" in
    */../*)
      printf 'BLOCKED: a log path must stay inside %s (no '\''..'\'').\n' "$LOGROOT" >&2
      exit 2 ;;
  esac
  rt_name=${rt_tgt##*/}
  if [ -z "$rt_name" ]; then
    printf 'BLOCKED: a log redirect must name a file inside %s.\n' "$LOGROOT" >&2
    exit 2
  fi
  if [ -e "$rt_tgt" ] || [ -L "$rt_tgt" ]; then
    printf "BLOCKED: log file '%s' already exists; logs are never overwritten. Use a new unique name (for example add a run number).\n" "$rt_name" >&2
    exit 2
  fi
done <<EOF_RT
$RT
EOF_RT
exit 0
