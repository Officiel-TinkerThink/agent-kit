# Review backlog: proof-lab plugin

Deferred findings and open items from the review-fix cycles on `feat/proof-lab-plugin`. Each entry has its reason and a decision. A deferred finding is documented here, never dropped. Dated 2026-10-20.

## Verified and closed

- **Guard rule 3 bypasses** (cycles 1–3): closed by the closed-form rule (`docs/design/proof-lab-plugin.md`, decision 6). Covered by `tests/proof-lab/test_guard_proof_key.py` cases; the last green run is recorded in the close-out.
- **Stale plugin count in CHANGELOG** (guidance, cycle 2 Notes): fixed. Line 3 now names the six plugins.
- **Stale plugin counts in CONTRIBUTING** (guidance, cycle 2): fixed. Seven files carry the version (six `plugin.json`, one marketplace file).
- **Simplicity suggestions** (cycles 1–3): applied (merged closed-form pattern; `-notmatch`; first-occurrence `command:` extraction).

## Open: needs the maintainer or a fact outside this repo

1. **Hook timeout 30 s instead of 10 s** (spec review, cycle 2, F4). Decision: keep 30 s. A PowerShell cold start on Windows can exceed 10 s, so the guard would time out and the harness's handling of a timed-out hook is unknown. Unverified: how Claude Code treats a timed-out PreToolUse hook (allow or block). Owner: confirm against the hook schema.
2. **Version keys on a new plugin** (guidance, cycle 1, escalated). The new plugin carries `0.3.0`, the kit's shared version, because the changelog test requires one shared version. `CONTRIBUTING.md` says the maintainer sets versions at release. Recommendation: keep `0.3.0`; the maintainer confirms at the release step. Alternative: the new plugin waits for the next release and the test allows a missing version. Owner: maintainer.
3. **Commit bodies 1a2a61f and 7740590 not read** (history digest, cycle 1). Their rationale for the `.mjs` exemption in `test_launcher.py` is unverified. Decision: the exemption stands on its own (Node is the same on every OS). Owner: read the commits if the exemption is ever questioned.
4. **Setup symlink and drive-letter path detection** (defect, cycle 1, unclear). `setup.mjs` compares the checkout path by string. A symlink or a differently-cased drive letter could in theory point at a different checkout. Unverified and low risk: the pin is a commit hash, and the clean-tree and HEAD checks run on that checkout. Owner: decide whether to resolve paths with `fs.realpath` before comparing.

## Open: residual limits of the guard (documented, fail-closed or out of rule)

5. **Variable outside `src/`** (security, cycle 3). A run through a variable in a path that is not under `src/` (for example `node $HOME/x/$R.js`) is not refused. Covered by the bounded `src/` rule only. Decision: accept; the pin check still covers every run that goes through `setup.mjs`.
6. **JSON `\uXXXX` escapes in the hook input** (security, cycle 3, unclear). If the hook serialiser encodes an ASCII letter as `\u`, the lexical rules do not see it. Unverified: the serialiser is outside this repo. Owner: confirm the hook input format.
7. **ANSI-C quoting `$'...'`** (security, cycle 1 and 2, unclear). A shell escape can spell `PROOF_LAB_KEY` or `--key` past rules 1 and 2. Out of the documented rules; the scope contract excludes rare quoting shapes. Decision: accept and record.
8. **Short alias or prefix form of `--key`** (security, cycle 2, unclear). Whether `prove.js` or `run-spec.js` accepts `-k` or a unique prefix is not in this repo. Owner: check proof-lab's CLI; if it does, add the form to rule 2.
9. **`\b` word boundary on BSD grep** (security, cycle 2, unclear). The `\bprove` pattern relies on GNU-style `\b`. Git Bash on Windows and Linux use GNU grep. Owner: check on macOS if the plugin is used there.
10. **Chain in an unrelated field of the hook input** (defect, cycle 2). The closed form fails when any field of the input contains a chain character, so a verify call can be refused by an unrelated `description`. Fail-closed over-block. Decision: accept.
11. **Runner named inside a closed form's arguments** (spec, cycle 2 and 3). `node setup.mjs --run --spec run-spec.json` is allowed by decision. `setup.mjs` is the sanctioned path. Decision recorded in decision 6.
12. **Hook input path and pipe characters** (defect, cycle 1). Not verified against the real hook payload. The tests build the JSON themselves. Owner: verify with one real hook call.

## Open: outside this diff

13. **`docs/design/proof-lab-plugin.md` "Open items"** (design doc). Adding a git remote to proof-lab and deciding whether `proof-runner` should run through `verification-runner` remain open, as the design states.
14. **`run.sh` router and `lib.sh` in the proof-lab plugin**: identical to the kit copies (`tests/agent-guards/test_launcher.py` enforces it). Reviewed by the test, not by a reviewer on this diff.

## Open at the review cap (cycle 4 delta, 2026-10-20)

Resolved by the v2 guard (`docs/design/proof-lab-guard-v2.md`): items 15 to 19 are covered by new cases in `tests/proof-lab/test_guard_proof_key.py`, which passes on the POSIX guard, the PowerShell twin and the router (151 checks, 0 failures). The review of the v2 change is the next cycle.

Previously: cap reached, not done, after five review cycles. Each finding below was confirmed by reading `plugins/proof-lab/scripts/guard-proof-key.sh` and `.ps1`. None is fixed on the branch. All are in scope under decision 6 (guard bypasses of the documented rules). Each one lets a proof runner start without `setup.mjs`'s pin and clean-tree check.

15. **Closed form accepts an option token as the program** (security, medium, confidence 90). `node --import=<path>/setup.mjs src/run-spec.js --spec s.json` matches ALLOW (`[^[:space:]]*setup\.mjs` on the option token). The runner runs as the entry point. Fix direction: the program is the first token after `node`, must not start with `-`, and its basename must be exactly `setup.mjs` or `prove.js`.
16. **Command value taken from the first `command:` text anywhere** (spec medium, defect medium, security medium, confidence 50 to 60). `COMMAND=${CMD#*command:}` (sh:22) and `-replace '^.*?command:'` (ps1:21) read a `description` field that contains `command:` placed earlier. Reachable only if the harness writes `description` before `command`, which backlog item 12 leaves unverified. Fix direction: require exactly one `command:` in the input, and fail closed otherwise.
17. **Glob and variable refusal anchored at the start of the command** (defect, medium, confidence 90). `BAD_PROGRAM` (sh:28, ps1:27) begins `^ *node`, so `cd proof && node src/run-s*.js --spec s.json` is allowed. Fix direction: test every `node` invocation in the whole input, not only the first word.
18. **Backslash decoded to `/` hides a runner or flag name** (defect, medium, confidence 80; security, medium, confidence 80). The decoding `s/\\/\//g` (sh:20, ps1:19) turns `run\-spec` into `run/-spec`. The shell then runs `run-spec`. The same blind spot covers `--key`. Fix direction: keep the path-friendly view for the closed form, and also test a second view with backslashes and braces removed the way the shell removes them. Block when either view names a runner or a `--key` outside the closed form.
19. **Brace expansion** (defect, medium, confidence 65, unverified). `node src/run-{spec,}.js` contains no runner word and no glob character, so it passes. Bash expands it to `run-spec.js`. Whether the Bash tool expands braces is outside this repo. Fix direction: block `{` and `}` in any `node` program token.

These are residuals of the same design, not patches: the guard judges text with patterns, and each cycle found a new way for the text the guard sees to differ from what the shell runs. A fix needs a parsed command (the program token and its arguments) or a design that accepts only one fixed command shape. Decide that on the next pass, not as another pattern.

## Deferred from review cycles 7 to 9 (2026-10-21)

Fixed in cycles 7 to 9 (commits 97ecdfc, e74e833, 7447015): the `"command"` key match, the last-word glob on POSIX, parent segments in the setup path, the literal `ROOT` and `@PLUGIN_ROOT@` markers, quote-joined markers, the single-quoted placeholder, and the decoded-text word check. Each has a case in `tests/proof-lab/test_guard_proof_key.py`.

20. **Duplicate `"command"` key hides a glob from the node checks** (history, cycle 7, F1; validator CONFIRMED at confidence 50). `{"command":"ls","command":"node src/run-s*.js …"}` is allowed: rule 4 reads only the first value, and `run-s*.js` names no runner. Reachable only if the harness writes a duplicate key (item 12). Fix direction: when the `"command"` key count is not 1, run the rule 4 checks on the whole input, or refuse the input. Severity medium; deferred because the validator confidence is below the finding floor.
21. **POSIX cut ignores the colon after `"command"`** (defect, cycle 7, F2, low). Fixed in the cycle 9 redesign: both twins cut after the first `"command"` key followed by a colon (sh `cut_cmd` with awk's leftmost `match`). Test: "description equal to the word command".
22. **`$` in a later argument after `src/`** (spec, cycle 7 and 8, unclear). `node src/lab.js doctor $X` is allowed; rule 4's `$` after `src/` is read as the program token only, which matches the block message. Decision (product owner): the rule names the program; the spec text should say so on the next edit.
23. **Forward-slash drive paths for `prove.js --verify`** (spec, cycle 7 and 8, unclear). `node D:/core/x/prove.js --verify` is refused (the segment class has no `:`). Decision: keep refused (fail-closed); a relative path or `$PROOF_LAB_HOME/src/prove.js` works. The "Use forward slashes" sentence in the v2 decisions should say "relative".
24. **`..` in the `prove.js` path** (security, cycle 8 and 9, out of scope). `${CLAUDE_PLUGIN_ROOT}/../x/prove.js --verify` matches the prove form. Decision: accept; `--verify` is read-only and any plain path is allowed by rule 3.
25. **Key exposure without the key's name** (security, cycle 8, out of scope). `env`, `printenv` or reading the `--key-file` path names neither `PROOF_LAB_KEY` nor `--key`. Outside the guard's rules; the key file's 0600 mode is the control.
26. **`setup.mjs` with a flag before `--run`** (security, cycle 8, out of scope). Not a bypass: `setup.mjs` reads `argv[0]` only for `--run` (setup.mjs:59, per the cycle 7 security review), so a later `--run` does not start a run.
27. **Duplicate helper** (simplicity, cycle 7, F1; CONFIRMED at 50, low). `NodeIn`/`node_in` repeat `Hit`/`hit` with a fixed pattern. Note only.
28. **POSIX guard speed under Git Bash on Windows** (gate timing, cycle 7). One call takes about 8 s (about 60 process starts at about 0.13 s each); views are now built once. Production on Windows uses the PowerShell twin (`run.sh`), so this affects the test run, not the hook. The test runner runs 4 cases at a time and allows 180 s per POSIX call; a single-awk rewrite would cut it further at the cost of re-hardening the rules.

## Deferred from review cycles 12 to 16 and real use (2026-10-21)

Fixed in this run (commits 4c14277, db57376, 5cb9b90, 7da2d0f, 2bca6a2): the skill frontmatter that did not parse (found by `claude plugin validate`), the plugin's absolute root as the agent types it, quoted arguments, the trailing newline Claude Code appends (it refused every run on the PowerShell twin), the root taken from the script's own location only, the literal placeholder no longer a closed form, interior raw newlines and carriage returns as chains. Found by running a demo spec through the real `proof-lab:proof-runner` agent in a `claude -p --plugin-dir` session and by capturing the real hook input. The last review (cycle 16) of the last fix has no in-scope finding of medium or higher.

29. **Trailing non-ASCII whitespace** (defect, cycle 16, F1, low, confidence 50). PowerShell `TrimEnd()` trims U+00A0 and other Unicode spaces; the POSIX loop's `[[:space:]]` depends on the locale. Fail-closed only: the security review traced that trimmed bytes sit after the closing `}` and never reach the command. Claude Code does not send them. Fix direction if needed: both twins trim the same explicit ASCII set. **Fixed: both twins trim the same explicit ASCII set (space, tab, CR, LF, VT, FF), in the trim and in the shape check. Test: "trailing no-break space".**
30. **`(` and `)` dropped by the shell view** (security, cycle 16, out of scope, pre-existing). A letter before `)` joins the next word, so the node word boundary can be missed and the node glob check skipped; a glob word with no runner stem is then not flagged. Fix direction: keep `(` and `)` as word boundaries in the shell view. **Fixed: ( and ) become spaces in the shell view on both twins. Test: "a)node src/*".**
31. **PowerShell splits words on .NET `\s`** (security, cycle 16, out of scope, pre-existing). The suspect-word split and the `src/…$` check treat NBSP, NEL, VT and FF as separators; bash does not. The POSIX twin splits on space and tab only. Fix direction: split on `[ \t]` in the PowerShell twin. **Fixed: the PowerShell twin splits words and the src/ check on space and tab only, and so does the POSIX src/ check.**
32. **The JSON escape `\r` decoded to a space** (security, cycle 16, out of scope). Bash keeps a CR inside a word. No bypass traced: the closed form is matched on the as-written text, where `\r` fails the argument class.
33. **A `$` in the install path** (security, cycle 16, unclear, confidence 25). The quoted root form would let bash expand a `$NAME` in the plugin's own install path. The user, not the model, controls the install path. Fix direction: refuse a root that contains `$` or a backtick. **Fixed: a root that contains $, a backtick, a double quote or a backslash is not a closed-form root on either twin (only nothing matches then).**
34. **Unbalanced variable prefix on `prove.js`** (defect and spec, cycle 12 and 13, unclear). `"$NAME}/src/prove.js" --verify` is accepted inside the quoted path; read-only, low. **Fixed: the prefix is $NAME/ or ${NAME}/ only, on both twins. Test: the unbalanced form is blocked.**
35. **The guard test exits 0 when `sh` or `powershell.exe` is missing** (defect, cycle 12, unclear, pre-existing). The skip message is printed, but a run that checked nothing for that path still passes. **Decision: keep. A machine without PowerShell (Linux or macOS CI) must still run the POSIX and router checks, so the missing path is reported as a skip, not a failure.**
