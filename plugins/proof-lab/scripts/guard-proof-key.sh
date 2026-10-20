#!/bin/sh
# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Three rules, the same in guard-proof-key.ps1:
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner (run-spec, prove, lab run, npm run prove) is blocked unless it is one of
#      two closed forms and chains nothing (no ; & | ` $( or a newline): `node .../setup.mjs ...` (which checks the
#      pin and a clean checkout before it starts the run), or `node .../prove.js ... --verify` (read only).
# Unreadable hook input is blocked (fail-closed).
INPUT=$(cat)
case "$(printf '%s' "$INPUT" | tr -d ' \t\r\n')" in
  \{*\}) ;;
  *) printf '%s\n' "BLOCKED: proof-lab guard error (the hook input is not one JSON object)" >&2; exit 2 ;;
esac
# Rule 1 reads the input with quotes and backslashes dropped, so PROOF_LAB_"KEY" and PROOF_LAB_\KEY match.
KEYCMD=$(printf '%s' "$INPUT" | tr -d "\"'\\\\")
# Rules 2 and 3 read the input with JSON escapes decoded: a JSON-escaped quote is dropped, an escaped backslash
# (a Windows path) and a lone backslash become /, and \t \n \r become spaces, so a tab splits the words.
CMD=$(printf '%s' "$INPUT" | tr '\n\r' '  ' | sed 's/\\"//g; s/\\\\/\//g; s/\\[tnr]/ /g; s/\\/\//g' | tr -d "\"'")
COMMAND=$(printf '%s' "$CMD" | sed 's/^.*command:[[:space:]]*//')
PROOF='PROOF_LAB|run-spec|\bprove|lab\.js|setup\.mjs'
RUNNER='run-spec|(^|[[:space:]/])prove(\.js)?([[:space:]]|$)|npm[[:space:]]+run[[:space:]]+prove|lab(\.js)?[[:space:]]+run'
ALLOW_SETUP='^[[:space:]]*node[[:space:]]+[^[:space:]]*setup\.mjs([[:space:]]|$)'
ALLOW_VERIFY='^[[:space:]]*node[[:space:]]+[^[:space:]]*prove\.js[[:space:]].*--verify'
# A newline arrives as the two characters \n in the JSON text. A backslash before n is a Windows path (C:\\new), not a newline.
CHAIN='[;&|`]|[$][(]|[^\\]\\[nr]'
if printf '%s' "$KEYCMD" | grep -qi 'PROOF_LAB_KEY'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file." >&2
  exit 2
fi
if printf '%s' "$CMD" | grep -Eqi -- "$PROOF" && printf '%s' "$CMD" | grep -Eqi -- '--key([^[:alnum:]_-]|$)'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): pass the signing key with --key-file <path>, never --key <value>." >&2
  exit 2
fi
if printf '%s' "$COMMAND" | grep -Eqi -- "$RUNNER" && ! { ! printf '%s' "$INPUT" | grep -Eq -- "$CHAIN" && { printf '%s' "$COMMAND" | grep -Eqi -- "$ALLOW_SETUP" || printf '%s' "$COMMAND" | grep -Eqi -- "$ALLOW_VERIFY"; }; }; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): run proof-lab through node \"\${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs\" --run, which checks the pin and a clean checkout before the run." >&2
  exit 2
fi
exit 0
