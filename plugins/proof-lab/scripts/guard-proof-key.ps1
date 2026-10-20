# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# Three rules, the same as guard-proof-key.sh:
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner (run-spec, prove, lab run, npm run prove) is blocked unless it is one of
#      two closed forms and chains nothing (no ; & | ` $( or a newline): `node .../setup.mjs ...` (which checks the
#      pin and a clean checkout before it starts the run), or `node .../prove.js ... --verify` (read only).
# Unreadable hook input is blocked (fail-closed).
$inputText = [Console]::In.ReadToEnd()
if ($inputText.Trim() -notmatch '^\{[\s\S]*\}$') {
  [Console]::Error.WriteLine('BLOCKED: proof-lab guard error (the hook input is not one JSON object)')
  exit 2
}
# Rule 1 reads the input with quotes and backslashes dropped, so PROOF_LAB_"KEY" and PROOF_LAB_\KEY match.
$keyCmd = $inputText -replace '["''\\]', ''
# Rules 2 and 3 read the input with JSON escapes decoded: a JSON-escaped quote is dropped, an escaped backslash
# (a Windows path) and a lone backslash become /, and \t \n \r become spaces, so a tab splits the words.
$cmd = $inputText -replace '\r|\n', ' ' -replace '\\"', '' -replace '\\\\', '/' -replace '\\[tnr]', ' ' -replace '\\', '/' -replace '["'']', ''
$command = $cmd -replace '(?s)^.*command:\s*', ''
$proof = 'PROOF_LAB|run-spec|\bprove|lab\.js|setup\.mjs'
$runner = 'run-spec|(^|[\s/])prove(\.js)?(\s|$)|npm\s+run\s+prove|lab(\.js)?\s+run'
$allowSetup = '^\s*node\s+\S*setup\.mjs(\s|$)'
$allowVerify = '^\s*node\s+\S*prove\.js\s.*--verify'
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
$closedForm = (-not ($inputText -match $chain)) -and (($command -match $allowSetup) -or ($command -match $allowVerify))
if (($command -match $runner) -and (-not $closedForm)) {
  [Console]::Error.WriteLine('BLOCKED (intentional guard, not a hook failure): run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.')
  exit 2
}
exit 0
