# Design: the proof-lab guard, v2

Status: decided by the product owner on 2026-10-20. This supersedes the rule text of decision 6 in `docs/design/proof-lab-plugin.md`. The rules below are the design of record; `guard-proof-key.sh` and `guard-proof-key.ps1` implement them, and `tests/proof-lab/test_guard_proof_key.py` checks them on both twins.

## Why v2

The v1 guard judged a text view of the hook input. Five bypasses were found in review cycles 1 to 5 (review-backlog items 15 to 19). Each came from one gap: the text the guard matched was not the text the shell runs. Examples: an option token (`--import=…/setup.mjs`) passed as the program, a `description` field carrying `command:` hid the real command, a backslash was decoded to `/` so `run\-spec` read as `run/-spec`, and a glob or brace in an unanchored position escaped the program check. v2 removes the mismatch instead of adding one more pattern. Review of the v2 change (cycle 6) found the same gap in three more places: `node` matched in the raw text (`no\de`, `\node`, `NODE`), the closed form matched in a case the consumer does not accept (`--VERIFY`), and the setup path was not pinned to the plugin root. The rules below close those too.

## Rules

Each input is one hook JSON object. The guard reads the command value of the `command:` key (case-sensitive) and the whole input.

1. **Key in the environment.** A `PROOF_LAB_KEY` name in either view (below) is blocked.
2. **Key inline.** A proof-lab name (`PROOF_LAB`, `run-spec`, `prove`, `lab.js`, `setup.mjs`) plus `--key` (not `--key-file`; `--key=` is blocked) in either view is blocked.
3. **Runner.** If either view names a runner (`run-spec`, `prove`, `npm run prove`, `lab run`, or `setup.mjs --run`), the call is allowed only when all of these hold:
   - the input has exactly one `command:` key;
   - nothing in the input is chained (`; & | ` $( <( >(`, or the JSON `\n` escape, which is a newline in the command);
   - the command string exactly as written in the JSON (nothing rewritten, decoded or quote-stripped) is one closed form:
     - `node ${CLAUDE_PLUGIN_ROOT}/<path>/setup.mjs <args>`: the plugin's own setup, the only path that runs the pin check; the root is the plugin's own absolute root as Claude Code substitutes it (below), not the literal placeholder; or
     - `node [<prefix>/]<path>/prove.js <args> --verify <args>`: read-only, so any plain path is accepted (the prefix is `${CLAUDE_PLUGIN_ROOT}/` or `$NAME/`, and only inside the quoted path, because the shell word-splits an unquoted variable; review cycle 11, security F1);
     - the program path is bare or in one pair of double quotes around the whole path; no other quote is accepted;
     - args are plain, `[-A-Za-z0-9_./:=@%+~]`, bare or in one pair of double quotes; the first token after `node` is never an option;
     - the match is case-sensitive, because `prove.js` reads `--verify` case-sensitively;
   - the command value holds every runner name the input names, so no runner sits in another JSON field.
   Otherwise the call is blocked.
4. **Node command, and runner or script words.** Two checks, both on the command value and in both texts (as written and decoded):
   - a node command (a whole word `node` in the shell view) with a glob (`*?[`), a brace (`{}`), or a backslash is blocked, and so is a `$` after `src/`;
   - a word with a glob, brace or backslash that names a runner stem (`run`, `prove`, `setup`, `lab`) or a script (`.js`, `.mjs`) is blocked, with or without `node`.
   `ls node_modules/*` is not a node command (`node` must be a whole word), and `cat src/*.py` is allowed.

Views. The shell view drops `\ $ * ? [ ] { } ( )`, backtick and quotes, and a runner name is searched in it. The path view reads each backslash as `/`. A name in either view counts. The JSON escapes `\"`, `\n`, `\t`, `\r` are decoded first; a decoded `\n` is a chain. Claude Code ends the hook input with a newline, and treating it as a chain refused every sanctioned run on the PowerShell twin (found in real use, 2026-10-21), so trailing whitespace is dropped first. Any other raw newline or carriage return is a chain (fails closed): valid JSON has neither inside a string, and the guard does not trust its input to be valid. A carriage return is not a separator to bash, which keeps it inside a word, so reading it as a space would let `k.txt<CR>--verify` pass as a `--verify` run (review cycles 14 and 15). Decoding only adds chains, so chains are judged on the decoded text.

## Decisions

- **Windows paths are refused.** A backslash path (`node D:\core\…\prove.js --verify`) names a runner and is not a closed form, so it is blocked. Use forward slashes; Git Bash accepts them.
- **The closed form is an allow-list on the command as written.** Review cycles 7 to 9 found four ways to build the sanctioned path from text the guard had rewritten or quote-stripped: a literal `ROOT/`, a typed marker, a marker joined from quoted pieces, and a single-quoted placeholder (which the shell does not expand). The cause was one mechanism: the closed form was judged on a text that differs from the one the shell runs. The closed form is now matched on the JSON command string itself, with the literal `${CLAUDE_PLUGIN_ROOT}` and at most one pair of double quotes around the program path, so none of those shapes can match. Over-blocks accepted, because each one is a spelling the allow-list does not need: `node "${CLAUDE_PLUGIN_ROOT}"/scripts/setup.mjs` (quotes around the placeholder only; quote the whole path) and a tab between words (the JSON writes it as `\t`; use spaces). Separators are space and tab only, the characters bash splits words on, so a Unicode space such as U+00A0 never separates `--verify` (review cycle 10, security F1).
- **The plugin's own absolute root is accepted (found in real use, 2026-10-21).** Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` in agent and skill text before the agent reads it, with forward slashes on Windows, and exports the same root to hook processes ([plugin components](https://code.claude.com/docs/en/plugins/components#reference-plugin-paths-and-store-data)). So the `proof-runner` agent types the absolute path, and the agent quotes its arguments. A headless run through the agent was refused by the guard for both reasons, and for a chain the agent's own instructions caused. The setup form accepts only the exact root, taken from the guard script's own location (never from the environment, so no outside value can widen it), with at least two path segments, as a regex-escaped prefix followed by `/`; unquoted only when the shell cannot split it. The literal `${CLAUDE_PLUGIN_ROOT}` is refused: the shell would expand it from an environment the guard does not read, and unset it gives `/scripts/setup.mjs` (review cycles 13 and 14, security). The refusal message prints the exact root, so an agent that copies it gets the accepted form. Arguments may be quoted. The agent file says to run the command alone; `setup.mjs` itself refuses an unset `PROOF_LAB_HOME`.
- **The placeholder rewrite serves rule 4 only.** `${CLAUDE_PLUGIN_ROOT}` is rewritten to `@PLUGIN_ROOT@` in the texts that rules 1, 2 and 4 read, so the brace rule does not block it. A typed `@PLUGIN_ROOT@` is plain text there and never reaches the closed form.
- **`setup.mjs` must be the plugin's own.** A relative or other `setup.mjs` path is refused, because only the plugin's setup runs the pin check. Each directory segment after the placeholder starts with a letter, digit or underscore, so `${CLAUDE_PLUGIN_ROOT}/../x/setup.mjs` is refused (review cycle 7, security F1, confirmed).
- **Unknown field order is fail-closed.** The command value starts after the first `"command"` key followed by a colon, on both twins, so a `description` whose value is `command` or contains `command:` is not the key. A duplicate `"command":` key is counted, and the closed form fails then. Known gap: a duplicate key hides a glob from the node checks (review cycle 7, history F1, confirmed at 50; backlog item 20).
- **Spellings.** `prove.mjs` and `prove-all.js` are not runner names (a runner is `prove` or `prove.js`).
- **Over-block accepted.** A `grep` for the word `node` with a `*` in another word is blocked by rule 4. Fail-closed; the Glob tool lists files instead.

## Residuals (documented, not checked by the guard)

- The guard checks the Bash command the agent types. It does not parse code run by an interpreter: `node -e "…"` with the runner name built at run time is not caught. Arbitrary code can run with or without this guard, so the guard protects the documented route, not against deliberate code execution.
- A variable outside `src/` (`node $HOME/x/$R.js`) is not refused (review-backlog item 5); the pin check still covers every run through `setup.mjs`.
- `$'...'` quoting and `\uXXXX` escapes in the hook input (backlog items 6, 7).
- A proof-lab CLI short alias or prefix of `--key` (backlog item 8).
- Hook field order is unverified (backlog item 12); v2 is correct for every order, at the cost of over-blocking when `command:` appears twice.
- A brace that builds a runner name from parts with no run, prove, setup, lab or script word (for example `./src/{ru,n}`-style fragments with no `.js`) is not caught; the `.js` and stem words cover the forms found in review.
- The same holds for a glob or extglob group whose letters carry no stem word (`npm run pro*`, `!(…)`): it runs only if the filesystem has a match, and the final security review (7e4539b) found nothing else in scope.

## Tests

`tests/proof-lab/test_guard_proof_key.py` covers, on the POSIX guard, the PowerShell twin and the router:

- blocked: the v1 cases; `node --import=…/setup.mjs …` (option as program); `cd x && node src/run-s*.js` and `node --no-warnings src/run-s*.js` (glob after another word); `node src/run-{spec,}.js` (brace); `node src/run\-spec.js` (backslash); the node word in other cases or spelled with a backslash (`NODE`, `n\ode`, `\node`); a runner or script word with a glob or brace and no node word; `--VERIFY`; a relative or other `setup.mjs --run`; Windows backslash paths; and a `description` field that carries `command:` before a runner `command`;
- allowed: the closed forms with `${CLAUDE_PLUGIN_ROOT}` and `$PROOF_LAB_HOME/src/lab.js doctor`; `setup.mjs --check-only` after `cd`; `ls node_modules/*`, `cat src/*.py`, `grep -rn foo src/`; a sanctioned run with `Command:` in the description; a `node` word that appears only in a description; and an unrelated command.
- The Chromium download that `setup.mjs` starts (`playwright install chromium`) comes from Playwright's own CDN, and the pin does not cover it. Whether Playwright verifies an archive checksum could not be confirmed from the source (research found no check, but only through summaries). The manual setup trusted the same download.
- The install lock `<home>.lock` has no owner check: a lock older than 11 minutes is cleared, and two runs that clear the same stale lock at the same moment could both install (needs a killed earlier run and a close interleaving). A repair that outlives the lock (laptop sleep, an npm child that survives the timeout) has the same effect.
