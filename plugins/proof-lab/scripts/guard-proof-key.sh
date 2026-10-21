#!/bin/sh
# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# The rules are in docs/design/proof-lab-guard-v2.md (the design of record); guard-proof-key.ps1 has the same rules.
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner is blocked unless the command value is one closed form and no other
#      part of the input names a runner: `node ${CLAUDE_PLUGIN_ROOT}/.../setup.mjs ...`, or `node .../prove.js ... --verify`.
#   4. A node command, or a word that names a runner or a script, with a glob, brace or backslash is blocked.
# Unreadable hook input is blocked (fail-closed).
INPUT=$(cat)
case "$(printf '%s' "$INPUT" | tr -d ' \t\r\n')" in
  \{*\}) ;;
  *) printf '%s\n' "BLOCKED: proof-lab guard error (the hook input is not one JSON object)" >&2; exit 2 ;;
esac
# RAWU: the input as the harness wrote it (JSON escapes kept), newlines as chains, the sanctioned ${CLAUDE_PLUGIN_ROOT}
# written as ROOT. RAW: RAWU with the JSON escapes decoded (\" dropped, \n a chain, \t and \r spaces). Decoding can only
# add a chain, never hide one, so chains are judged on RAW; node and glob words are judged on both texts.
RAWU=$(printf '%s' "$INPUT" | tr '\n\r' ';;' | sed 's/[$]{CLAUDE_PLUGIN_ROOT}/@PLUGIN_ROOT@/g')
RAW=$(printf '%s' "$RAWU" | sed 's/\\"//g; s/\\n/;/g; s/\\[tr]/ /g')
# The command value: the text after the one `command:` key. CMD_D is decoded, CMD_U is as written.
CMD_D=$(printf '%s' "${RAW#*\"command\"}" | sed 's/^[[:space:]]*://; s/"[[:space:]]*[,}].*$//')
CMD_U=$(printf '%s' "${RAWU#*\"command\"}" | sed 's/\\"//g; s/^[[:space:]]*://; s/"[[:space:]]*[,}].*$//')
# VALUE: the closed-form candidate, quotes dropped, cut at the next JSON separator.
VALUE=$(printf '%s' "$CMD_D" | tr -d "\"'" | sed 's/[,}].*$//')
# Two views of a text: the shell view (characters the shell drops or expands are removed, quotes too) and the path
# view (a backslash reads as a path separator). A name is searched in both, so neither view can hide it.
view() {
  printf '%s\n%s\n' "$(printf '%s' "$1" | tr -d '\\$*?[]{}()`' | tr -d "\"'")" "$(printf '%s' "$1" | tr '\\' '/')"
}
PROOF='PROOF_LAB|run-spec|(^|[^[:alnum:]_])prove|lab\.js|setup\.mjs'
RUNNER='run-spec|(^|[^[:alnum:]_-])prove(\.js)?([^[:alnum:]_.-]|$)|npm[[:space:]]+run[[:space:]]+prove([^[:alnum:]_.-]|$)|(^|[^[:alnum:]_-])lab(\.js)?[[:space:]]+run([^[:alnum:]_.-]|$)|(^|[^[:alnum:]_-])setup[.]mjs[[:space:]]+--run([^[:alnum:]_.-]|$)'
NODE_WORD='(^|[^[:alnum:]_])node([^[:alnum:]_]|$)'
SUSPECT_CHARS='[*?[{\\]'
STEM='(^|[^[:alnum:]_])(run|prove|setup|lab)([^[:alnum:]_]|$)|[.]m?js'
ARG='[-A-Za-z0-9_./:=@%+]+'
SETUP='@PLUGIN_ROOT@/([A-Za-z0-9_][A-Za-z0-9_.-]*/)*setup[.]mjs'
PROVE='((@PLUGIN_ROOT@|[$][{]?[A-Za-z_]+[}]?)/)?([A-Za-z0-9_.][A-Za-z0-9_.-]*/)*prove[.]js'
CLOSED="^[[:space:]]*node[[:space:]]+(${SETUP}([[:space:]]+${ARG})*|${PROVE}([[:space:]]+${ARG})*[[:space:]]+--verify([[:space:]]+${ARG})*)[[:space:]]*\$"
CHAIN='[;&|`]|[$][(]|[<>][(]'

block() {
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): $1" >&2
  exit 2
}
hit() { view "$1" | grep -Eqi -- "$2"; }
runner_count() { view "$1" | grep -Eoi -- "$RUNNER" | wc -l | tr -d ' '; }
node_in() { view "$1" | grep -Eqi -- "$NODE_WORD"; }
suspect_word() {
  printf '%s\n' "$1" | grep -q -- "$SUSPECT_CHARS" || return 1
  view "$1" | grep -Eqi -- "$STEM"
}

if hit "$RAW" 'PROOF_LAB_KEY'; then
  block "the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file."
fi
if hit "$RAW" "$PROOF" && hit "$RAW" '--key([^[:alnum:]_-]|$)'; then
  block "pass the signing key with --key-file <path>, never --key <value>."
fi
RUN_PROG='run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.'
if { node_in "$CMD_D" || node_in "$CMD_U"; } && printf '%s\n%s\n' "$CMD_D" "$CMD_U" | grep -Eq -- "$SUSPECT_CHARS"; then
  block "a node command has a glob, brace or backslash in it; $RUN_PROG"
fi
if { node_in "$CMD_D" || node_in "$CMD_U"; } && printf '%s\n%s\n' "$CMD_D" "$CMD_U" | grep -Eq -- 'src/[^[:space:]]*[$]'; then
  block "a node command names its program in src/ with a variable; $RUN_PROG"
fi
if [ -n "$(printf '%s\n%s\n' "$CMD_U" "$CMD_D" | tr -s ' \t' '\n\n' | while IFS= read -r w; do suspect_word "$w" && echo hit; done)" ]; then
  block "a glob, brace or backslash in a word that names a runner or a script; $RUN_PROG"
fi
RAW_N=$(runner_count "$RAW")
[ "$RAW_N" = 0 ] && exit 0
# The closed form is judged on the command value, and the value must hold every runner name in the input.
if ! printf '%s' "$RAW" | grep -Eq -- "$CHAIN" \
  && [ "$(printf '%s' "$RAW" | grep -o '"command"[[:space:]]*:' | wc -l | tr -d ' ')" = 1 ] \
  && printf '%s' "$VALUE" | grep -Eq -- "$CLOSED" \
  && [ "$(runner_count "$VALUE")" = "$RAW_N" ]; then
  exit 0
fi
block "$RUN_PROG"
