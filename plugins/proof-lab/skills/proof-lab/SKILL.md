---
name: proof-lab
description: "Prove that a feature works in the real app: write a spec, run it, read the signed receipt. Sets up its own proof-lab checkout on first use (or uses PROOF_LAB_HOME). Use when a change must be shown to work in the app, not only in unit tests."
argument-hint: "<spec.json>"
allowed-tools: Bash, Read
---

# proof-lab

Proof-lab runs a spec against the app and writes a signed receipt. A feature is done only on exit 0 (PASS with no open claims), and only for what the spec states.

## Before the first run

1. Nothing to set up. On the first run, `setup.mjs` fetches proof-lab at the commit in `proof-lab.pin` into `~/.proof-lab`, installs its dependencies and Chromium (a few minutes, network needed). To use your own checkout instead, set `PROOF_LAB_HOME` to it (absolute path, at the pinned commit, no uncommitted changes).
2. Run the setup once if you want it ready before the first run: `node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs"`. It refuses a checkout that does not match the pin.
3. Check the environment: `node "<proof-lab folder>/src/lab.js" doctor` (the folder is `$PROOF_LAB_HOME`, or the one `setup.mjs` prints).
4. The signing key is a file with mode 0600. Pass it with `--key-file <path>`. Never set `PROOF_LAB_KEY` and never pass `--key`; a guard blocks both.

## Write the spec

The format is in `SPECS.md` in the proof-lab folder. A spec needs at least one assertion, or the validator refuses it.

## Run

- Directly: `node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec <spec.json> --key-file <key-file>` (add `--json` for machine output). This checks the pin and a clean checkout before every run. A guard blocks a direct call to `run-spec.js`.
- Or give the spec to the `proof-runner` agent, which returns only the verdict.

## Read the exit code

| Exit | Verdict | What it means | Say "done"? |
|---|---|---|---|
| 0 | PASS | Every check in the spec passed on this revision | Yes, for what the spec states |
| 1 | FAIL | A check failed | No. Fix the app or the spec and run again |
| 2 | ERROR | The run could not finish or could not be trusted | No. Look at the receipt's error |
| 3 | NEEDS-REVIEW | The checks passed, but the spec lists a claim only a human can judge. The receipt's verdict still reads PASS; the exit code is 3 | No. Hand it to a person |

## Receipts

Receipts go to `$PROOF_LAB_RECEIPTS`, or to `receipts/` in the proof-lab folder when that is not set. They are never committed.
