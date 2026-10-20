#!/bin/sh
# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Blocks a command that names PROOF_LAB_KEY (the signing key must not sit in the environment); a proof-lab command that
# passes the key inline (--key <value>) instead of --key-file <path>; and a direct run of run-spec.js or `lab.js run`,
# which must go through `setup.mjs --run` (it checks the pin and a clean checkout first). Unreadable hook input is blocked.
INPUT=$(cat)
case "$(printf '%s' "$INPUT" | tr -d ' \t\r\n')" in
  \{*\}) ;;
  *) printf '%s\n' "BLOCKED: proof-lab guard error (the hook input is not one JSON object)" >&2; exit 2 ;;
esac
# Quotes and backslashes are dropped before matching, so PROOF_LAB_"KEY" or --key "value" match like the plain form.
CMD=$(printf '%s' "$INPUT" | tr -d "\"'\\\\")
if printf '%s' "$CMD" | grep -qi 'PROOF_LAB_KEY'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file." >&2
  exit 2
fi
if printf '%s' "$CMD" | grep -qi 'PROOF_LAB_HOME\|run-spec\.js\|prove\.js\|lab\.js' && printf '%s' "$CMD" | grep -Eq -- '--key([[:space:]=]|$)'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): pass the signing key with --key-file <path>, never --key <value>." >&2
  exit 2
fi
if printf '%s' "$CMD" | grep -Eqi 'run-spec\.js|lab\.js[[:space:]]+run([[:space:]]|$)' && ! printf '%s' "$CMD" | grep -qi 'setup\.mjs'; then
  printf '%s\n' "BLOCKED (intentional guard, not a hook failure): run proof-lab through node \"\${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs\" --run, which checks the pin and a clean checkout before the run." >&2
  exit 2
fi
exit 0
