# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# The rules are in docs/design/proof-lab-guard-v2.md (the design of record); guard-proof-key.sh has the same rules.
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner is blocked unless the command value is one closed form and no other
#      part of the input names a runner: `node .../setup.mjs ...`, or `node .../prove.js ... --verify`.
#   4. A node command with a glob, brace, backslash or a variable in a src/ path is blocked (it names the program at run time).
# Unreadable hook input is blocked (fail-closed).
$inputText = [Console]::In.ReadToEnd()
if ($inputText.Trim() -notmatch '^\{[\s\S]*\}$') {
  [Console]::Error.WriteLine('BLOCKED: proof-lab guard error (the hook input is not one JSON object)')
  exit 2
}
# $raw: JSON escapes decoded (\" dropped, \n a chain, \t and \r spaces), a raw newline a chain, quotes dropped, and
# the sanctioned ${CLAUDE_PLUGIN_ROOT} written as ROOT so the closed form can match it.
$raw = $inputText -replace '\r|\n', ';' -replace '\\"', '' -replace '\\n', ';' -replace '\\[tr]', ' ' -replace '["'']', ''
$raw = $raw -replace '[$]\{CLAUDE_PLUGIN_ROOT\}', 'ROOT'
# Two views of a text: the shell view (characters the shell drops or expands are removed) and the path view (a
# backslash reads as a path separator). A name is searched in both, so neither view can hide it.
function View([string]$s) {
  ($s -replace '[\\$*?\[\]{}()`]', '') + "`n" + ($s -replace '\\', '/')
}
function Hit([string]$s, [string]$pattern) {
  [regex]::IsMatch((View $s), $pattern, 'IgnoreCase')
}
$proof = 'PROOF_LAB|run-spec|(^|[^A-Za-z0-9_])prove|lab\.js|setup\.mjs'
$runner = 'run-spec|(^|[^A-Za-z0-9_-])prove(\.js)?([^A-Za-z0-9_.-]|$)|npm[ \t]+run[ \t]+prove([^A-Za-z0-9_.-]|$)|(^|[^A-Za-z0-9_-])lab(\.js)?[ \t]+run([^A-Za-z0-9_.-]|$)'
function RunnerCount([string]$s) {
  ([regex]::Matches((View $s), $runner, 'IgnoreCase')).Count
}
$arg = '[-A-Za-z0-9_./:=@%+]+'
$prog = '([$][{]?[A-Za-z_]+[}]?/)?([A-Za-z0-9_.][A-Za-z0-9_.-]*/)*'
$closed = "^\s*node\s+$prog(setup[.]mjs(\s+$arg)*|prove[.]js(\s+$arg)*\s+--verify(\s+$arg)*)\s*$"
$chain = '[;&|`]|[$][(]|[<>][(]'
$globBad = '(^|[^A-Za-z0-9_])node[^;&|`]*[*?\[{}\\]|(^|[^A-Za-z0-9_])node[^;&|`]*src/[^\s]*[$]'

function Block([string]$reason) {
  [Console]::Error.WriteLine("BLOCKED (intentional guard, not a hook failure): $reason")
  exit 2
}
if (Hit $raw 'PROOF_LAB_KEY') {
  Block 'the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file.'
}
if ((Hit $raw $proof) -and (Hit $raw '--key([^A-Za-z0-9_-]|$)')) {
  Block 'pass the signing key with --key-file <path>, never --key <value>.'
}
if ([regex]::IsMatch(($raw -replace '[,}]', ''), $globBad, 'IgnoreCase')) {
  Block 'a node command names its program with a glob, brace, backslash or variable; run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run.'
}
$rawN = RunnerCount $raw
if ($rawN -eq 0) { exit 0 }
# The command value is the text after the one `command:` key, cut at the next JSON separator. The closed form is
# judged on that value, and the value must hold every runner name in the input.
$command = $raw -replace '^.*?command:', ''
$value = $command -replace '[,}].*$', ''
$commandKeys = ([regex]::Matches($raw, 'command:')).Count
$isClosed = (-not [regex]::IsMatch($raw, $chain)) -and ($commandKeys -eq 1) -and
  [regex]::IsMatch($value, $closed, 'IgnoreCase') -and ((RunnerCount $value) -eq $rawN)
if ($isClosed) { exit 0 }
Block 'run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.'
