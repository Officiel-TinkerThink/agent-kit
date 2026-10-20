# Design: the proof-lab plugin

Status: accepted for implementation on branch `feat/proof-lab-plugin`. Owner decisions are recorded here; anything the owner has not decided is marked **Recommended** and was decided by the implementer.

## Goal

Ship proof-lab as a plugin of agent-kit, so that an agent can prove that a feature works in the real app and report a signed receipt, without the agent-kit and proof-lab code being merged into one repository.

## Decisions

1. **Two repositories, one plugin.** proof-lab stays its own repository, with its own tests and history. The plugin in agent-kit holds only the skill, the agent, the hook, the setup script and a pin file. It does not copy proof-lab's source. *Why:* each repository is tested on its own; a change in one never runs the other's suite. A copy would drift and would make every agent-kit change run the proof-lab suite.
2. **The pin is a commit, not a tag.** proof-lab has no git remote, so a tag cannot be fetched. `plugins/proof-lab/proof-lab.pin` holds the full commit hash the plugin was tested against. Bumping the pin is a deliberate change in its own pull request. *Recommended*; when a remote exists, the pin can name a tag.
3. **proof-lab is found through `PROOF_LAB_HOME`.** The environment variable is required; there is no default path, so the plugin never guesses where proof-lab is. *Why:* a guessed path would run an unknown checkout.
4. **The setup script refuses a mismatched checkout.** It checks that `git -C $PROOF_LAB_HOME rev-parse HEAD` equals the pin, that the working tree is clean, and that Node is 24 or later, before it runs `npm ci` in the checkout. A mismatch is an error with the two hashes, not a warning. Every proof run goes through `setup.mjs --run`, which repeats the same checks before it starts `run-spec.js`, and the guard blocks a direct `run-spec.js` call, so a run never starts on an unpinned or dirty checkout. *Why:* a receipt is evidence only for the code that produced it.
5. **Receipts stay in proof-lab's checkout.** The default is `$PROOF_LAB_HOME/receipts` (proof-lab already gitignores it). `PROOF_LAB_RECEIPTS` overrides it. The plugin never writes receipts into agent-kit.
6. **The guard blocks key misuse on Bash.** The rules are superseded by `docs/design/proof-lab-guard-v2.md` (the design of record, decided after review cycle 5); the text below is the v1 record. A `PreToolUse` hook on the `Bash` tool applies three rules. (1) Any command that names `PROOF_LAB_KEY` (case-insensitive) is blocked. (2) Any command that names a proof-lab runner (`run-spec`, `prove`, `lab.js`, `setup.mjs`, `PROOF_LAB`) and passes `--key` (as `--key`, `--key=` or at the end of the line, case-insensitive) is blocked; `--key-file` is allowed. (3) Any command that names a proof runner (`run-spec`, `prove`, `npm run prove`, `lab run`) is blocked unless it is one of two closed forms and chains nothing: `node .../setup.mjs ...` (setup checks the pin and a clean checkout before it starts the run), or `node .../prove.js ... --verify` (read only). The closed forms are matched on the command's own program (the first word after `node`), so a runner named after `;`, `&&`, `sh -c` or inside another argument is blocked. This is a bounded rule: a new spelling of a runner cannot pass, because only the two closed forms pass. Rules 2 and 3 read the input with JSON escapes decoded, left to right: a JSON-escaped quote is dropped, a pair of backslashes and a lone backslash become `/` (so `D:\core\src\prove.js` keeps `prove` as a word and `C:\\new` is not a newline), a `\n` escape becomes `;` so that it counts as a chain, and `\t` and `\r` become spaces. Rule 1 reads the input with quotes and backslashes dropped, so `PROOF_LAB_\KEY` still matches. The runner test runs on the whole decoded input, so a runner in any field blocks. The closed form is judged on the command value: its program is the first word after `node`, taken from the first `command:` key. A chain in any field of the input (`;`, `&`, `|`, a backtick, `$(`, `<(`, `>(`, a newline) fails the closed form; this over-blocks in rare cases and fails closed. A glob in the program path (`node src/run-s*.js`) is refused. Decision on an open point: a runner named inside a closed form's own arguments (`node .../setup.mjs --run --spec run-spec.json`) is allowed, because `setup.mjs` is the sanctioned path and runs the pin check itself. A glob in the program path (`node src/run-s*.js`), and a variable in a `src/` path (`node src/$R.js`, `node src/${R}.js`), are refused: they name the runner at run time. A variable outside `src/` is not covered; that residual is recorded in `docs/review-backlog.md` (item 5), and the sanctioned `node "$PROOF_LAB_HOME/src/lab.js" doctor` stays allowed. A block is exit 2 with the reason on stderr. *Why:* proof-lab refuses `PROOF_LAB_KEY` itself; the hook stops the attempt earlier and tells the agent why. The guard exists as `guard-proof-key.sh` and `guard-proof-key.ps1` with the same rules. The hook calls `scripts/run.sh`, which is the kit's own router and `scripts/lib.sh`, byte-identical to agent-guards' copies (a test enforces it): Windows runs the `.ps1`, other systems the `.sh`, and each call appends its audit line to the kit data folder. The router fails closed (exit 2) when its interpreter or script is missing. The agent-kit purity test requires a `.ps1` twin for every `.sh`. An unreadable hook input is blocked (fail-closed), so a broken guard is visible rather than silent.
7. **One agent: `proof-runner`.** It runs exactly one spec, through `node setup.mjs --run`, which checks the pin and a clean checkout and then starts `run-spec.js`; it returns the verdict, the failing checks and the receipt path. It does not write specs and does not edit files. Model `claude-haiku-5-5`, tools `Bash, Read, Grep, Glob`. *Why:* the same one-command, verdict-only pattern as `verification-runner`.
8. **One skill: `proof-lab`.** It says when to prove a feature, how to write a spec (pointing at `SPECS.md` in proof-lab), how to run it through the agent, and how to read the exit codes. A feature is "done" only on exit 0 (PASS with no open claims); exit 3 means "do not say done".
9. **Exit codes are the contract.** 0 pass, 1 a check or gate says no, 2 cannot tell, 3 needs a human to judge. These are proof-lab's own codes: exit 3 is defined in `src/run-spec.js:28` (`exitCodeOf`, line 29) and `src/status.js:21`. `src/lab.js:2` documents only 0, 1 and 2. The skill copies the codes verbatim. Exit 3 is a receipt whose checks passed but which lists an open claim; its verdict string is still PASS.
10. **Version.** The changelog test requires every plugin and the marketplace to carry one version, the kit's shared version (`0.3.0`, released 2026-10-20). The new plugin carries it. Per `CONTRIBUTING.md`, the maintainer sets versions at release; the changelog line goes under `## [Unreleased]`, in `Added`.

## Layout

```
plugins/proof-lab/
  .claude-plugin/plugin.json      name, description, version 0.3.0 (the kit's shared version)
  skills/proof-lab/SKILL.md       when and how to prove a feature
  agents/proof-runner.md          Haiku agent: runs one spec, returns the verdict
  hooks/hooks.json                PreToolUse on Bash -> run.sh guard-proof-key
  scripts/run.sh                  router: Windows runs the .ps1, other systems the .sh
  scripts/lib.sh                  the kit's shared shell helpers (identical copy)
  scripts/guard-proof-key.sh      guard (POSIX sh)
  scripts/guard-proof-key.ps1     guard (PowerShell, same rules)
  scripts/setup.mjs               checks Node, PROOF_LAB_HOME, the pin; runs npm ci
  proof-lab.pin                   the proof-lab commit this plugin was tested against
```

`.claude-plugin/marketplace.json` gets one entry: `"source": "./plugins/proof-lab"`.

`setup.mjs` is Node, not a shell script, because proof-lab already needs Node 24. The guard must run even where Node is absent, so it is `sh`.

`proof-lab.pin` holds one full commit hash on its first non-comment line. Current value: `a1b5d62d347849149876967f09107fd1584207b1` (proof-lab, `npm test` runs every test file).

## Tests (agent-kit side)

New folder `tests/proof-lab/`, run by `python tests/run_all.py`:

- `test_manifest.py`: `plugin.json` parses and names the plugin; the marketplace entry exists and points at the folder; the skill has frontmatter with `name` and `description`; the agent's `model` is `claude-haiku-5-5`; `hooks.json` parses and names the guard script.
- `test_guard_proof_key.py`: pipes hook JSON through three paths (the POSIX guard, the PowerShell twin, and the router the hook calls) and checks the three rules in decision 6: blocks `PROOF_LAB_KEY=...`, `export PROOF_LAB_KEY`, `prove ... --key <value>` (also `--KEY`, `--key=`, and the `setup.mjs --run` and `npm run prove` forms), and direct `run-spec.js` or `prove.js` calls, including a direct call chained after a `setup.mjs` call; allows `--key-file` forms, `prove.js ... --verify`, and unrelated commands; blocks unparseable input; exits 2 with a reason on stderr when it blocks. Skipped with a message when `sh` is not on PATH.
- `test_setup_pin.py`: builds a temporary git checkout (with a `.gitignore` for `node_modules/`); a matching pin passes; a mismatched pin is refused with both hashes; a dirty tree is refused; a missing `PROOF_LAB_HOME` is refused; `--run` passes arguments through and returns the run's exit code; `--run` refuses a mismatched, a dirty, or a checkout without `node_modules` before it runs. `npm ci` is replaced by a flag in tests so no install runs.
- `tests/agent-guards/test_launcher.py` (shared): `run.sh` and `lib.sh` are byte-identical in every plugin that ships scripts. A Node `.mjs` script needs no router: it runs the same on every OS, so the skill-command rule skips lines that name a `.mjs` file. This exemption is accepted; the test docstring carries the same note.

## Pin-bump checklist

Bumping `proof-lab.pin` is its own pull request. Before it merges:

1. The new commit passes proof-lab's `npm test` (0 fail) and the demo verdicts above.
2. `plugins/proof-lab/scripts/setup.mjs` still starts the runner at `src/run-spec.js`. If proof-lab renames or moves it, change the path in `setup.mjs`.
3. The guard rules in `guard-proof-key.sh` and `guard-proof-key.ps1` still name the runners that exist (`run-spec`, `prove`, `lab.js`, `setup.mjs`). Change both twins together and the BLOCKED/ALLOWED cases in `test_guard_proof_key.py`.
4. The skill (`SKILL.md`) and the agent (`proof-runner.md`) name `setup.mjs --run` and the exit codes as proof-lab defines them. `test_manifest.py` checks the `setup.mjs --run` wording.
5. The changelog line under `[Unreleased]` names the new pin.

## Tests (proof-lab side)

- `package.json` `test` script runs every test file (`node --test test/*.test.mjs`), not only `test/run.test.mjs`. The gate is the full run.

## Verification before merge

1. `python tests/run_all.py` in agent-kit: all pass.
2. `npm test` in proof-lab: all pass, 0 fail.
3. The demo, run through the plugin's setup with the pinned commit: verdicts match the earlier demo run (PASS, FAIL, NEEDS-REVIEW, ERROR, chain VALID, tamper INVALID).
4. A review of each pull request (defect and security reviewers), with the root cause fixed for every finding that holds.

## Out of scope

- Vendoring proof-lab's source into agent-kit.
- Old receipts on disk that hold full paths in the signed `screenshot` field (they stay as they are).
- Windows directory sync (recorded in proof-lab's `SECURITY-BACKLOG.md`, S3.7).

## Open items to revisit

- Add a git remote to proof-lab, then the setup can clone the pin instead of requiring a local checkout.
- Decide whether `proof-runner` should run through `verification-runner` instead of its own agent file.
