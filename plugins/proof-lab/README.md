# proof-lab

Prove that a feature works in the real app: write a spec, run it in a headless browser, read the signed receipt. The plugin holds the skill, the `proof-runner` agent and a guard that keeps the signing key out of the environment and off the command line. The runner itself is the separate [proof-lab](https://github.com/Officiel-TinkerThink/proof-lab) repository, pinned to one commit in `proof-lab.pin`.

```
/plugin install proof-lab@agent-kit
```

## What you need

| | Windows | Ubuntu / Linux | macOS |
|---|---|---|---|
| Node | 24 or later | 24 or later | 24 or later |
| git | yes (Claude Code on Windows already needs Git Bash) | yes | yes |
| Network | first run only | first run only | first run only |
| Browser libraries | nothing extra | see below | nothing extra |

Nothing else. On the first run `setup.mjs` fetches the pinned proof-lab commit into `~/.proof-lab/checkouts/<commit>`, installs its dependencies (`npm ci --ignore-scripts`) and Chromium, then runs the spec. Later runs reuse that folder. To use your own checkout instead, set `PROOF_LAB_HOME` to it (it must be at the pinned commit, with no uncommitted changes).

## Ubuntu / Linux

Chromium needs system libraries that a minimal Ubuntu (a server, a container) does not have. The plugin starts the browser and tells you if it cannot:

- **As root** (a container, or a root shell) on the plugin's own checkout: the plugin installs the libraries itself with `apt`, but only when root owns the checkout and the Playwright packages and nobody else can write to them. On a checkout you named with `PROOF_LAB_HOME`, or one root does not own, the browser step does nothing as root and warns, so that step never runs a file a normal user can change. (If you run `setup.mjs` as root, its `npm ci` and the spec run as root from whichever checkout it uses, the one you named with `PROOF_LAB_HOME` or the one under `PROOF_LAB_DATA`: point root only at trees you trust.)
- **As a normal user:** it refuses once and prints the exact command, which looks like `sudo node '<proof-lab folder>/node_modules/playwright/cli.js' install-deps chromium` (the path is in single quotes, so it can be pasted as it is). Run it, then run the plugin again. The plugin starts the browser on every run (about a second), so a browser that breaks later is noticed too.

Check it on a clean Ubuntu 24.04 container (from a Linux shell or WSL with Docker; needs the network): `sh tests/linux/proof-lab-e2e.sh`. It runs the whole proof-lab demo as a normal user and as root, and checks that root does nothing in the browser step on a checkout a normal user owns.

## How it adapts to the machine

`scripts/setup.mjs` does not look at the operating system. It asks `scripts/platform/index.mjs` for the adapter that matches the machine it runs on (`linux.mjs`, `win32.mjs`, `darwin.mjs`, or a no-op for any other system). An adapter answers the same questions for its system: how npm is started, and whether the browser can start. Supporting a new system means adding one file there. A test fails if any other JavaScript file in `scripts/` names an operating system (the shell entry point `run.sh` and the guard scripts are the existing per-system routers).

## The browser is pinned too

Playwright checks only the size of the browser it downloads. The plugin compares every browser folder it uses with `browsers.sha256.json` (a digest per build: Linux x64 and arm64, macOS x64 and arm64, Windows x64) before the browser first starts, and again whenever Playwright installs it again. A folder that does not match is refused with the command that downloads it afresh. A browser that you installed yourself for the same Playwright version is the same download, so it passes. As root, browsers in a folder that a normal user can change are refused.

## Limits

- As root on a checkout a normal user can change, the plugin warns and goes on: `npm ci` and the spec run as root from that checkout, and the browser step (the check above and the system libraries) is skipped. Run it as the checkout's owner instead. The same warning is given when `PROOF_LAB_RECEIPTS` names a folder a normal user can change.
- The guard checks the Bash command an agent types. It does not parse code run by an interpreter. See `docs/design/proof-lab-guard-v2.md`.
