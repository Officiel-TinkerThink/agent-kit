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

- One spec, directly: `node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec <spec.json> --key-file <key-file>` (add `--json` for machine output). This checks the pin and a clean checkout before every run. A guard blocks a direct call to `run-spec.js`.
- Several specs at once: repeat `--spec`, or add `--spec-dir <dir>` (every `.json` file of the folder). Everything after `--run` goes to proof-lab unchanged. See "Many specs at once" below.
- Or give the spec, or the batch, to the `proof-runner` agent, which returns only the verdicts.

## Many specs at once

- They run concurrently in one process: each spec has its own browser, its own app server on a free port, its own receipt and evidence file. A spec that cannot be read, or a run that stops, is an ERROR for that spec only. The results print in the order of the `--spec` flags, then a line of totals. The exit code is 1 if any spec FAILed, else 2 if any was ERROR, else 3 if any needs review, else 0.
- How many at once is decided by the machine: at most `min(2 x cores, 0.75 x memory / 1 GiB)`, and a governor holds a new run back while memory is short, the CPU is above 85% or the load is high. `--jobs N` lowers the ceiling (a larger number is cut to it). The ceiling is machine-wide: separate runs on one machine add up to it. In a Docker container the container's `--cpus` and `--memory` count, not the host's.
- `--share-browser N` (1 to 32, default 1 = one browser per run) is opt-in: up to N runs share one Chromium, each in its own browser context. It is about twice as fast and uses half to two thirds of the browser memory on short specs (measured on trivial specs), and it has costs: the runs share a failure domain (a browser that dies ends every run on it as ERROR, never FAIL or PASS) and the receipt's `next` text and the evidence say the browser was shared. Whether a shared browser is acceptable evidence for a release is for the validation owner to decide: use it only when the caller asks for it.
- Napkin math: 1,000 short specs take about 5 minutes with a browser each and about 2 minutes sharing, on 14 cores. That is measured on trivial specs, not on yours: run one of yours, note its peak Chromium memory and its time, then `jobs = min(2 x cores, 0.75 x memory / peak memory per run)`.
- A browser or a page that crashes during a run ends that run as ERROR (exit 2) within about a second. Run it again; do not read it as a failed check.
- The proof-lab job queue (`queue submit`, `queue status`) is not available through this plugin: `setup.mjs --run` starts `run-spec.js` only, so the queue would skip the pin and clean-checkout check. Use `--run` with several specs.

## Read the exit code

| Exit | Verdict | What it means | Say "done"? |
|---|---|---|---|
| 0 | PASS | Every check in the spec passed on this revision | Yes, for what the spec states |
| 1 | FAIL | A check failed | No. Fix the app or the spec and run again |
| 2 | ERROR | The run could not finish or could not be trusted | No. Look at the receipt's error |
| 3 | NEEDS-REVIEW | The checks passed, but the spec lists a claim only a human can judge. The receipt's verdict still reads PASS; the exit code is 3 | No. Hand it to a person |

## Receipts

Receipts go to `$PROOF_LAB_RECEIPTS`, or to `receipts/` in the proof-lab folder when that is not set. They are never committed.
