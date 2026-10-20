# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Three rules, the same as guard-proof-key.sh:
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A direct run of run-spec.js, prove.js, `npm run prove` or `lab.js run` is blocked: every run goes through
#      `setup.mjs --run`, which checks the pin and a clean checkout first. The one exemption is `prove.js --verify`
#      (read only), and only when the command chains nothing (no ; & | ` $( or a newline) and runs no other runner.
# Unreadable hook input is blocked (fail-closed).
$inputText = [Console]::In.ReadToEnd()
if ($inputText.Trim() -notmatch '^\{[\s\S]*\}$') {
  [Console]::Error.WriteLine('BLOCKED: proof-lab guard error (the hook input is not one JSON object)')
  exit 2
}
# Rule 1 reads the command with quotes and backslashes dropped, so PROOF_LAB_"KEY" and PROOF_LAB_\KEY match.
$keyCmd = $inputText -replace '["''\\]', ''
# Rules 2 and 3 read the command with JSON escapes (\t \n \r) and every other backslash turned into a space, so a tab
# or a Windows path separator still splits the words; quotes are dropped.
$cmd = $inputText -replace '\\[tnr]', ' ' -replace '\\', ' ' -replace '["'']', ''
$proof = 'PROOF_LAB|run-spec|\bprove|lab\.js|setup\.mjs'
$directRun = '(^|[\s/])run-spec(\.js)?(\s|$)|npm\s+run\s+prove(\s|$)|(^|[\s/])lab(\.js)?\s+run(\s|$)'
$directProve = '(^|[\s/])prove(\.js)?(\s|$)'
# A newline arrives as the two characters \n in the JSON text. A backslash before n is a Windows path (C:\\new), not a newline.
$chain = '[;&|`]|\$\(|[^\\]\\[nr]'
if ($keyCmd -match 'PROOF_LAB_KEY') {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file.')
  exit 2
}
if (($cmd -match $proof) -and ($cmd -match '--key([^\w-]|$)')) {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): pass the signing key with --key-file <path>, never --key <value>.')
  exit 2
}
if (($cmd -match $directRun) -or (($cmd -match $directProve) -and (($inputText -match $chain) -or ($cmd -notmatch 'prove\.js.*--verify')))) {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.')
  exit 2
}
exit 0
