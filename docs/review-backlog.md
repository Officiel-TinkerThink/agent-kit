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
