#!/bin/sh
# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Three rules, the same in guard-proof-key.ps1:
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner (run-spec, prove, lab run, npm run prove) is blocked unless it is one of
#      two closed forms and chains nothing (no ; & | ` $( <( >( or a newline): `node .../setup.mjs ...` (which checks
#      the pin and a clean checkout before it starts the run), or `node .../prove.js ... --verify` (read only).
# Unreadable hook input is blocked (fail-closed).
INPUT=$(cat)
case "$(printf '%s' "$INPUT" | tr -d ' \t\r\n')" in
  \{*\}) ;;
  *) printf '%s\n' "BLOCKED: proof-lab guard error (the hook input is not one JSON object)" >&2; exit 2 ;;
esac
# Rule 1 reads the input with quotes and backslashes dropped, so PROOF_LAB_"KEY" and PROOF_LAB_\KEY match.
KEYCMD=$(printf '%s' "$INPUT" | tr -d "\"'\\\\")
# Rules 2 and 3 read the input with the JSON escapes decoded, left to right: a JSON-escaped quote is dropped, a pair
# of backslashes (an escaped backslash, as in a Windows path) and a lone backslash become /, a \n escape becomes a
# ; so that it is a chain, and \t \r become spaces. A raw newline (not valid inside JSON strings) becomes a space.
CMD=$(printf '%s' "$INPUT" | tr '\n\r' '  ' | sed 's/\\"//g; s/\\\\/\//g; s/\\n/;/g; s/\\[tr]/ /g; s/\\/\//g' | tr -d "\"'")
# The command value follows the first "command:" key; the key is the first occurrence, so a later field cannot hide it.
COMMAND=${CMD#*command:}
PROOF='PROOF_LAB|run-spec|\bprove|lab\.js|setup\.mjs'
RUNNER='run-spec|(^|[^[:alnum:]_-])prove(\.js)?([^[:alnum:]_.-]|$)|npm[[:space:]]+run[[:space:]]+prove([^[:alnum:]_.-]|$)|(^|[^[:alnum:]_-])lab(\.js)?[[:space:]]+run([^[:alnum:]_.-]|$)'
ALLOW='^[[:space:]]*node[[:space:]]+([^[:space:]]*setup\.mjs([[:space:]]|$)|[^[:space:]]*prove\.js[[:space:]].*--verify)'
# A glob in the program path (node src/run-s*.js), or a variable in a src/ path (node src/$R.js), names no runner
# word, so it is refused here. A variable outside src/ is not covered (residual, see the design doc).
BAD_PROGRAM='^[[:space:]]*node[[:space:]]+[^[:space:]]*([*?[]|src/[^[:space:]]*[$])'
CHAIN='[;&|`]|[$][(]|[<>][(]'
if printf '%s' "$KEYCMD" | grep -qi 'PROOF_LAB_KEY'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file." >&2
  exit 2
fi
if printf '%s' "$CMD" | grep -Eqi -- "$PROOF" && printf '%s' "$CMD" | grep -Eqi -- '--key([^[:alnum:]_-]|$)'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): pass the signing key with --key-file <path>, never --key <value>." >&2
  exit 2
fi
if { printf '%s' "$CMD" | grep -Eqi -- "$RUNNER" || printf '%s' "$COMMAND" | grep -Eqi -- "$BAD_PROGRAM"; } && ! { ! printf '%s' "$CMD" | grep -Eq -- "$CHAIN" && printf '%s' "$COMMAND" | grep -Eqi -- "$ALLOW" && ! printf '%s' "$COMMAND" | grep -Eqi -- "$BAD_PROGRAM"; }; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): run proof-lab through node \"\${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs\" --run, which checks the pin and a clean checkout before the run." >&2
  exit 2
fi
exit 0
