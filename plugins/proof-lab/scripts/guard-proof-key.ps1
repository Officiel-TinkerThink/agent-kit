# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Same rules as guard-proof-key.sh: a command that names PROOF_LAB_KEY is blocked; so is a proof-lab command that passes
# the key inline (--key <value>) instead of --key-file <path>, and a direct run of run-spec.js or `lab.js run`, which must
# go through `setup.mjs --run`. Quotes and backslashes are dropped before matching. Unreadable hook input is blocked (fail-closed).
$inputText = [Console]::In.ReadToEnd()
if ($inputText.Trim() -notmatch '^\{[\s\S]*\}$') {
  [Console]::Error.WriteLine('BLOCKED: proof-lab guard error (the hook input is not one JSON object)')
  exit 2
}
$cmd = $inputText -replace '["''\\]', ''
if ($cmd -match 'PROOF_LAB_KEY') {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file.')
  exit 2
}
if (($cmd -match 'PROOF_LAB_HOME|run-spec\.js|prove\.js|lab\.js') -and ($cmd -match '--key(\s|=|$)')) {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): pass the signing key with --key-file <path>, never --key <value>.')
  exit 2
}
if (($cmd -match 'run-spec\.js|lab\.js\s+run(\s|$)') -and ($cmd -notmatch 'setup\.mjs')) {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.')
  exit 2
}
exit 0
