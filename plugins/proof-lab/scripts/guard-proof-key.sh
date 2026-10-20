#!/bin/sh
# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# The rules are in docs/design/proof-lab-guard-v2.md (the design of record); guard-proof-key.ps1 has the same rules.
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner is blocked unless the command value is one closed form and no other
#      part of the input names a runner: `node .../setup.mjs ...`, or `node .../prove.js ... --verify`.
#   4. A node command with a glob, brace, backslash or a variable in a src/ path is blocked (it names the program at run time).
# Unreadable hook input is blocked (fail-closed).
INPUT=$(cat)
case "$(printf '%s' "$INPUT" | tr -d ' \t\r\n')" in
  \{*\}) ;;
  *) printf '%s\n' "BLOCKED: proof-lab guard error (the hook input is not one JSON object)" >&2; exit 2 ;;
esac
# RAW: the input with JSON escapes decoded (\" dropped, \n a chain, \t and \r spaces), a raw newline a chain, quotes
# dropped, and the sanctioned ${CLAUDE_PLUGIN_ROOT} written as ROOT so the closed form can match it.
RAW=$(printf '%s' "$INPUT" | tr '\n\r' ';;' | sed 's/\\"//g; s/\\n/;/g; s/\\[tr]/ /g; s/[$]{CLAUDE_PLUGIN_ROOT}/ROOT/g' | tr -d "\"'")
# Two views of a text: the shell view (characters the shell drops or expands are removed) and the path view (a
# backslash reads as a path separator). A name is searched in both, so neither view can hide it.
view() {
  printf '%s\n%s\n' "$(printf '%s' "$1" | tr -d '\\$*?[]{}()`')" "$(printf '%s' "$1" | tr '\\' '/')"
}
PROOF='PROOF_LAB|run-spec|(^|[^[:alnum:]_])prove|lab\.js|setup\.mjs'
RUNNER='run-spec|(^|[^[:alnum:]_-])prove(\.js)?([^[:alnum:]_.-]|$)|npm[[:space:]]+run[[:space:]]+prove([^[:alnum:]_.-]|$)|(^|[^[:alnum:]_-])lab(\.js)?[[:space:]]+run([^[:alnum:]_.-]|$)'
ARG='[-A-Za-z0-9_./:=@%+]+'
PROG='([$][{]?[A-Za-z_]+[}]?/)?([A-Za-z0-9_.][A-Za-z0-9_.-]*/)*'
CLOSED="^[[:space:]]*node[[:space:]]+${PROG}(setup[.]mjs([[:space:]]+${ARG})*|prove[.]js([[:space:]]+${ARG})*[[:space:]]+--verify([[:space:]]+${ARG})*)[[:space:]]*\$"
CHAIN='[;&|`]|[$][(]|[<>][(]'
GLOB_BAD='(^|[^[:alnum:]_])node[^;&|`]*[*?[{}\\]|(^|[^[:alnum:]_])node[^;&|`]*src/[^[:space:]]*[$]'

block() {
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): $1" >&2
  exit 2
}
hit() { view "$1" | grep -Eqi -- "$2"; }
runner_count() { view "$1" | grep -Eoi -- "$RUNNER" | wc -l | tr -d ' '; }

if hit "$RAW" 'PROOF_LAB_KEY'; then
  block "the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file."
fi
if hit "$RAW" "$PROOF" && hit "$RAW" '--key([^[:alnum:]_-]|$)'; then
  block "pass the signing key with --key-file <path>, never --key <value>."
fi
if printf '%s' "$RAW" | tr -d ',}' | grep -Eq -- "$GLOB_BAD"; then
  block "a node command names its program with a glob, brace, backslash or variable; run proof-lab through node \"\${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs\" --run."
fi
RAW_N=$(runner_count "$RAW")
[ "$RAW_N" = 0 ] && exit 0
# The command value is the text after the one `command:` key, cut at the next JSON separator. The closed form is
# judged on that value, and the value must hold every runner name in the input.
COMMAND=${RAW#*command:}
VALUE=$(printf '%s' "$COMMAND" | sed 's/[,}].*$//')
if ! printf '%s' "$RAW" | grep -Eq -- "$CHAIN" \
  && [ "$(printf '%s' "$RAW" | grep -o 'command:' | wc -l | tr -d ' ')" = 1 ] \
  && printf '%s' "$VALUE" | grep -Eq -- "$CLOSED" \
  && [ "$(runner_count "$VALUE")" = "$RAW_N" ]; then
  exit 0
fi
block "run proof-lab through node \"\${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs\" --run, which checks the pin and a clean checkout before the run."
