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

Chromium needs system libraries that a minimal Ubuntu (a server, a container) does not have. The plugin starts the browser once and tells you if it cannot:

- **As root** (a container, or `sudo` from a root shell): the plugin installs the libraries itself with `apt`.
- **As a normal user:** it refuses once and prints the exact command, which looks like `sudo node "<proof-lab folder>/node_modules/playwright/cli.js" install-deps chromium`. Run it, then run the plugin again.

Check it on a clean Ubuntu 24.04 container (from a Linux shell or WSL with Docker; needs the network): `sh tests/linux/proof-lab-e2e.sh`. It runs the whole proof-lab demo as a normal user and as root.

## How it adapts to the machine

`scripts/setup.mjs` does not look at the operating system. It asks `scripts/platform/index.mjs` for the adapter that matches the machine it runs on (`linux.mjs`, `win32.mjs`, `darwin.mjs`, or a no-op for any other system). An adapter answers the same questions for its system: how npm is started, and whether the browser can start. Supporting a new system means adding one file there. A test fails if any other file names an operating system.

## Limits

- The Chromium download comes from Playwright's own servers; the commit pin does not cover it.
- The guard checks the Bash command an agent types. It does not parse code run by an interpreter. See `docs/design/proof-lab-guard-v2.md`.
