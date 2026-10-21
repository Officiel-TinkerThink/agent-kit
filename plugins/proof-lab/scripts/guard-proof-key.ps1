# PreToolUse hook (Bash), registered by the proof-lab plugin. Exit 2 blocks the call; the reason goes to stderr.
# The rules are in docs/design/proof-lab-guard-v2.md (the design of record); guard-proof-key.sh has the same rules.
#   1. A command that names PROOF_LAB_KEY is blocked: the signing key must not sit in the environment.
#   2. A proof-lab command that passes --key (any case) is blocked: the key goes in a file, --key-file <path>.
#   3. A command that names a proof runner is blocked unless the command value is one closed form and no other
#      part of the input names a runner: `node ${CLAUDE_PLUGIN_ROOT}/.../setup.mjs ...`, or `node .../prove.js ... --verify`.
#   4. A node command, or a word that names a runner or a script, with a glob, brace or backslash is blocked.
# Unreadable hook input is blocked (fail-closed).
$inputText = [Console]::In.ReadToEnd()
if ($inputText.Trim() -notmatch '^\{[\s\S]*\}$') {
  [Console]::Error.WriteLine('BLOCKED: proof-lab guard error (the hook input is not one JSON object)')
  exit 2
}
# $rawW: the input as written, newlines as chains, nothing rewritten; the closed form is judged on it.
# $rawU: $rawW with ${CLAUDE_PLUGIN_ROOT} written as @PLUGIN_ROOT@, so the brace rule does not block it.
# $raw: $rawU with the JSON escapes decoded (\" dropped, \n a chain, \t and \r spaces). Decoding only adds chains.
$rawW = $inputText -replace '\r|\n', ';'
$rawU = $rawW -replace '[$]\{CLAUDE_PLUGIN_ROOT\}', '@PLUGIN_ROOT@'
$raw = $rawU -replace '\\"', '' -replace '\\n', ';' -replace '\\[tr]', ' '
# The command value: the text after the first "command" key and its colon (case-sensitive). $cmdD decoded, $cmdU as
# written with \" dropped; both cut at the JSON string end.
$cmdD = ($raw -creplace '^.*?"command"\s*:', '') -replace '"\s*[,}].*$', ''
$cmdU = (($rawU -replace '\\"', '') -creplace '^.*?"command"\s*:', '') -replace '"\s*[,}].*$', ''
# $cmdW: the command string exactly as written in JSON (\" kept, nothing rewritten), cut at its closing quote.
$cmdW = ($rawW -creplace '^.*?"command"\s*:\s*"', '') -replace '(?<!\\)".*$', ''
# $value: the closed-form candidate, quotes dropped, cut at the next JSON separator.
$value = ($cmdD -replace '["'']', '') -replace '[,}].*$', ''
# Two views of a text: the shell view (characters the shell drops or expands, quotes too) and the path view (a
# backslash reads as a path separator). A name is searched in both, so neither view can hide it.
function View([string]$s) {
  ($s -replace '[\\$*?\[\]{}()`"'']', '') + "`n" + ($s -replace '\\', '/')
}
function Hit([string]$s, [string]$pattern) {
  [regex]::IsMatch((View $s), $pattern, 'IgnoreCase')
}
$proof = 'PROOF_LAB|run-spec|(^|[^A-Za-z0-9_])prove|lab\.js|setup\.mjs'
$runner = 'run-spec|(^|[^A-Za-z0-9_-])prove(\.js)?([^A-Za-z0-9_.-]|$)|npm[ \t]+run[ \t]+prove([^A-Za-z0-9_.-]|$)|(^|[^A-Za-z0-9_-])lab(\.js)?[ \t]+run([^A-Za-z0-9_.-]|$)|(^|[^A-Za-z0-9_-])setup[.]mjs[ \t]+--run([^A-Za-z0-9_.-]|$)'
$nodeWord = '(^|[^A-Za-z0-9_])node([^A-Za-z0-9_]|$)'
$suspectChars = '[*?\[{\\]'
$stem = '(^|[^A-Za-z0-9_])(run|prove|setup|lab)([^A-Za-z0-9_]|$)|[.]m?js'
function RunnerCount([string]$s) {
  ([regex]::Matches((View $s), $runner, 'IgnoreCase')).Count
}
function NodeIn([string]$s) {
  [regex]::IsMatch((View $s), $nodeWord, 'IgnoreCase')
}
$arg = '[-A-Za-z0-9_./:=@%+]+'
# The closed form is an allow-list on $cmdW: the program path is bare or in one pair of double quotes (\" in JSON), and
# every argument is plain text. A single quote, any other quote, a typed or joined marker fails the match, because the
# text is matched as written (review cycles 7 to 9 found four ways around a match on rewritten or quote-stripped text).
$q = '\\"'
$setupPath = '[$][{]CLAUDE_PLUGIN_ROOT[}]/([A-Za-z0-9_][A-Za-z0-9_.-]*/)*setup[.]mjs'
# A variable prefix is accepted only inside the quoted path: unquoted, the shell word-splits its value (review cycle 11,
# security F1), so the bare prove path is plain segments only.
$proveBare = '([A-Za-z0-9_.][A-Za-z0-9_.-]*/)*prove[.]js'
$provePath = '([$][{]?[A-Za-z_]+[}]?/)?([A-Za-z0-9_.][A-Za-z0-9_.-]*/)*prove[.]js'
# Case-sensitive on purpose: prove.js reads --verify case-sensitively, so the guard must not accept --VERIFY.
# Separators are space and tab only, the characters bash splits words on (.NET \s also matches Unicode spaces such as
# U+00A0, which bash keeps inside a word; review cycle 10, security F1).
$sp = '[ \t]'
$closed = '^' + $sp + '*node' + $sp + '+((' + $q + $setupPath + $q + '|' + $setupPath + ')(' + $sp + '+' + $arg + ')*|(' + $q + $provePath + $q + '|' + $proveBare + ')(' + $sp + '+' + $arg + ')*' + $sp + '+--verify(' + $sp + '+' + $arg + ')*)' + $sp + '*$'
$chain = '[;&|`]|[$][(]|[<>][(]'

function Block([string]$reason) {
  [Console]::Error.WriteLine("BLOCKED (intentional guard, not a hook failure): $reason")
  exit 2
}
$runProg = 'run proof-lab through node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run, which checks the pin and a clean checkout before the run.'
if (Hit $raw 'PROOF_LAB_KEY') {
  Block 'the signing key must not be set in the environment (PROOF_LAB_KEY). Pass it with --key-file <path> to a 0600 file.'
}
if ((Hit $raw $proof) -and (Hit $raw '--key([^A-Za-z0-9_-]|$)')) {
  Block 'pass the signing key with --key-file <path>, never --key <value>.'
}
$both = "$cmdD`n$cmdU"
if (((NodeIn $cmdD) -or (NodeIn $cmdU)) -and [regex]::IsMatch($both, $suspectChars)) {
  Block "a node command has a glob, brace or backslash in it; $runProg"
}
if (((NodeIn $cmdD) -or (NodeIn $cmdU)) -and [regex]::IsMatch($both, 'src/[^\s]*[$]')) {
  Block "a node command names its program in src/ with a variable; $runProg"
}
$suspectWords = @(("$cmdU $cmdD" -split '\s+') | Where-Object { $_ -match $suspectChars -and [regex]::IsMatch((View $_), $stem, 'IgnoreCase') })
if ($suspectWords.Count -gt 0) {
  Block "a glob, brace or backslash in a word that names a runner or a script; $runProg"
}
$rawN = RunnerCount $raw
if ($rawN -eq 0) { exit 0 }
$commandKeys = ([regex]::Matches($raw, '"command"\s*:')).Count
$isClosed = (-not [regex]::IsMatch($raw, $chain)) -and ($commandKeys -eq 1) -and
  [regex]::IsMatch($cmdW, $closed) -and ((RunnerCount $value) -eq $rawN)
if ($isClosed) { exit 0 }
Block $runProg
