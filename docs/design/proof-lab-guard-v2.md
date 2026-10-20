# Design: the proof-lab guard, v2

Status: decided by the product owner on 2026-10-20. This supersedes the rule text of decision 6 in `docs/design/proof-lab-plugin.md`. The rules below are the design of record; `guard-proof-key.sh` and `guard-proof-key.ps1` implement them, and `tests/proof-lab/test_guard_proof_key.py` checks them on both twins.

## Why v2

The v1 guard judged a text view of the hook input. Five bypasses were found in review cycles 1 to 5 (review-backlog items 15 to 19). Each came from one gap: the text the guard matched was not the text the shell runs. Examples: an option token (`--import=…/setup.mjs`) passed as the program, a `description` field carrying `command:` hid the real command, a backslash was decoded to `/` so `run\-spec` read as `run/-spec`, and a glob or brace in an unanchored position escaped the program check. v2 removes the mismatch instead of adding one more pattern.

## Rules

Each input is one hook JSON object. The guard reads the command value of the `command:` key and the whole input.

1. **Key in the environment.** A `PROOF_LAB_KEY` name in either view (below) is blocked.
2. **Key inline.** A proof-lab name (`PROOF_LAB`, `run-spec`, `prove`, `lab.js`, `setup.mjs`) plus `--key` (not `--key-file`, `--key=` is blocked) in either view is blocked.
3. **Runner.** If either view names a runner (`run-spec`, `prove`, `npm run prove`, `lab run`), the call is allowed only when all of these hold:
   - the input has exactly one `command:` key;
   - nothing in the input is chained (`; & | ` $( <( >(`, a newline, or the JSON `\n` escape);
   - the command value, cut at the next JSON separator (`,` or `}`), is one closed form: `node [prefix/]setup.mjs <args>`, or `node [prefix/]prove.js <args> --verify <args>`. The prefix is `${CLAUDE_PLUGIN_ROOT}/` or `$NAME/` followed by plain path segments. Args are plain: `[-A-Za-z0-9_./:=@%+]`. The first token after `node` is never an option;
   - the command value holds every runner name the input names, so no runner sits in another JSON field.
   Otherwise the call is blocked.
4. **Program at run time.** A node command with a glob (`*?[`), a brace (`{}`), a backslash, or a `$` after `src/` anywhere in its words is blocked, whether or not it is chained.

Views. The shell view drops `\ $ * ? [ ] { } ( )` and backtick, and a runner name is searched in it. The path view reads each backslash as `/`. A name in either view counts. Quotes and the JSON escapes `\"`, `\n`, `\t`, `\r` are decoded first; a raw newline is a chain.

## Decisions

- **Windows paths are refused.** A backslash path (`node D:\core\…\prove.js --verify`) is not a closed form and names a runner, so it is blocked. Use forward slashes; Git Bash accepts them. This removes the escape ambiguity at its source.
- **The sanctioned plugin root is `${CLAUDE_PLUGIN_ROOT}`.** It is rewritten to `ROOT` before the checks, so the closed form matches it and the brace rule does not block it.
- **Unknown field order is fail-closed.** A `description` containing `command:` makes the count two, so the closed form fails; a runner in that field then blocks the call.
- **Spellings.** `prove.mjs` and `prove-all.js` are not runner names (a runner is `prove` or `prove.js`). Recorded as a residual.

## Residuals (documented, not checked by the guard)

- A variable outside `src/` (`node $HOME/x/$R.js`) is not refused (review-backlog item 5); the pin check still covers every run through `setup.mjs`.
- `$'...'` quoting and `\uXXXX` escapes in the hook input (backlog items 6, 7).
- A proof-lab CLI short alias or prefix of `--key` (backlog item 8).
- Hook field order is unverified (backlog item 12); v2 is correct for every order, at the cost of over-blocking when `command:` appears twice.

## Tests

`tests/proof-lab/test_guard_proof_key.py` covers, on the POSIX guard, the PowerShell twin and the router:

- blocked: the v1 cases, plus `node --import=…/setup.mjs …` (option as program), `cd x && node src/run-s*.js` and `node --no-warnings src/run-s*.js` (glob after another word), `node src/run-{spec,}.js` (brace), `node src/run\-spec.js` (backslash), Windows backslash paths, and a `description` field that carries `command:` before a runner `command`;
- allowed: the closed forms with `${CLAUDE_PLUGIN_ROOT}` and `$PROOF_LAB_HOME/src/lab.js doctor`, `setup.mjs --check-only` after `cd`, and an unrelated command.
