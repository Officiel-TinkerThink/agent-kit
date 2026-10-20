# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Three rules, the same as guard-proof-key.sh:
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A direct run of run-spec.js, prove.js, `npm run prove` or `lab.js run` is blocked: every run goes through
#      `setup.mjs --run`, which checks the pin and a clean checkout first. The one exemption is `prove.js --verify`
#      (read only), and only when the command chains nothing (no ; & | ` $( or a newline).
# Unreadable hook input is blocked (fail-closed).
$inputText = [Console]::In.ReadToEnd()
if ($inputText.Trim() -notmatch '^\{[\s\S]*\}$') {
  [Console]::Error.WriteLine('BLOCKED: proof-lab guard error (the hook input is not one JSON object)')
  exit 2
}
# Quotes and backslashes are dropped before matching, so PROOF_LAB_"KEY" or --key "value" match like the plain form.
$cmd = $inputText -replace '["''\\]', ''
$proof = 'PROOF_LAB|run-spec|\bprove|lab\.js|setup\.mjs'
$direct = 'run-spec\.js|prove\.js|npm\s+run\s+prove|lab\.js\s+run'
# The raw input is checked for chaining: a newline arrives as the two characters \n in the JSON text.
$chain = '[;&|`]|\$\(|\\n|\\r'
if ($cmd -match 'PROOF_LAB_KEY') {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file.')
  exit 2
}
if (($cmd -match $proof) -and ($cmd -match '--key(\s|=|$)')) {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): pass the signing key with --key-file <path>, never --key <value>.')
  exit 2
}
if ($cmd -match $direct) {
  $exempt = (-not ($inputText -match $chain)) -and ($cmd -match 'prove\.js.*--verify')
  if (-not $exempt) {
    [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.')
    exit 2
  }
}
exit 0
