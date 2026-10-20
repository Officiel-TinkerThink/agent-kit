#!/bin/sh
# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Three rules, the same in guard-proof-key.ps1:
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A direct run of run-spec.js, prove.js, `npm run prove` or `lab.js run` is blocked: every run goes through
#      `setup.mjs --run`, which checks the pin and a clean checkout first. The one exemption is `prove.js --verify`
#      (read only), and only when the command chains nothing (no ; & | ` $( or a newline) and runs no other runner.
# Unreadable hook input is blocked (fail-closed).
INPUT=$(cat)
case "$(printf '%s' "$INPUT" | tr -d ' \t\r\n')" in
  \{*\}) ;;
  *) printf '%s\n' "BLOCKED: proof-lab guard error (the hook input is not one JSON object)" >&2; exit 2 ;;
esac
# Rule 1 reads the command with quotes and backslashes dropped, so PROOF_LAB_"KEY" and PROOF_LAB_\KEY match.
KEYCMD=$(printf '%s' "$INPUT" | tr -d "\"'\\\\")
# Rules 2 and 3 read the command with JSON escapes (\t \n \r) and every other backslash turned into a space, so a tab
# or a Windows path separator still splits the words; quotes are dropped.
CMD=$(printf '%s' "$INPUT" | sed 's/\\[tnr]/ /g; s/\\/ /g' | tr -d "\"'")
PROOF='PROOF_LAB|run-spec|\bprove|lab\.js|setup\.mjs'
DIRECT_RUN='(^|[[:space:]/])run-spec(\.js)?([[:space:]]|$)|npm[[:space:]]+run[[:space:]]+prove([[:space:]]|$)|(^|[[:space:]/])lab(\.js)?[[:space:]]+run([[:space:]]|$)'
DIRECT_PROVE='(^|[[:space:]/])prove(\.js)?([[:space:]]|$)'
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
if printf '%s' "$CMD" | grep -Eqi -- "$DIRECT_RUN" || { printf '%s' "$CMD" | grep -Eqi -- "$DIRECT_PROVE" && { printf '%s' "$INPUT" | grep -Eq -- "$CHAIN" || ! printf '%s' "$CMD" | grep -Eqi -- 'prove\.js.*--verify'; }; }; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): run proof-lab through node \"\${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs\" --run, which checks the pin and a clean checkout before the run." >&2
  exit 2
fi
exit 0
