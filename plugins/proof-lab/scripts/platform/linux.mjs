// Linux: the Chromium download works on a minimal Ubuntu, but the browser cannot start without system libraries, and
// Playwright then reports only "browser has been closed". So the adapter starts the browser, and if that fails it
//   - installs the libraries (apt, through Playwright's install-deps) when the plugin runs as root on its own checkout and
//     root owns every file it would run, or
//   - refuses with the exact command, when the plugin runs as a normal user.
// In this browser step root never runs a file that a normal user can change: as root, on a checkout root does not own, the
// adapter does nothing. setup.mjs also warns, through rootRisk, that its npm ci and the spec run as root from that checkout.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, parse } from "node:path";
import { pathToFileURL } from "node:url";
import { isRoot, othersCanChange, rootRisk, trustedTree } from "./posix.mjs";

// The probe imports Playwright by absolute path (argument 1) and runs from the filesystem root, so Node never looks at
// files directly inside the checkout (a package.json there could change what a bare "playwright" import means).
const START = "const { chromium } = await import(process.argv[1]); const b = await chromium.launch({ headless: true }); await b.close();";
const PROBES_AFTER_INSTALL = 12; // apt allows one install at a time; another run may be installing, so look for about two minutes
const PAUSE_MS = 10_000;

// A path for a shell command line: in single quotes, so nothing in it is expanded when the user pastes the command.
export const shQuote = text => `'${String(text).replace(/'/g, "'\\''")}'`;

// The calls that touch the machine are in `real`, so a test can replace them.
const real = {
  exists: existsSync,
  isRoot,
  trustedTree,
  starts: home => {
    const entry = pathToFileURL(join(home, "node_modules", "playwright", "index.mjs")).href;
    return spawnSync(process.execPath, ["--input-type=module", "-e", START, entry], { cwd: parse(home).root, stdio: "ignore", timeout: 60_000 }).status === 0;
  },
  installDeps: (cli, home, timeout) => execFileSync(process.execPath, [cli, "install-deps", "chromium"], { cwd: parse(home).root, stdio: ["ignore", process.stderr, process.stderr], timeout }),
  pause: ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms),
};

export function ensureBrowser(ctx, deps = real) {
  const cli = join(ctx.home, "node_modules", "playwright", "cli.js");
  if (!deps.exists(cli)) return; // not a Playwright checkout (a test stand-in): nothing to start
  const root = deps.isRoot();
  if (root && !ctx.own) {
    console.error(`Running as root on a checkout named with PROOF_LAB_HOME: the plugin starts Chromium and installs its system libraries only on its own checkout. If Chromium fails to start, install them with: node ${shQuote(cli)} install-deps chromium`);
    return;
  }
  if (root && !deps.trustedTree(ctx.home)) {
    console.error("Running as root on a checkout that root does not own: the browser step is skipped, so no file a normal user can change runs as root. If Chromium fails to start, install its libraries from a checkout you trust.");
    return;
  }
  if (deps.starts(ctx.home)) return;
  let up = false;
  if (root) {
    try {
      console.error("Chromium cannot start: installing its system libraries (apt)");
      deps.installDeps(cli, ctx.home, ctx.timeoutMs);
    } catch {}
    up = deps.starts(ctx.home);
    for (let attempt = 1; attempt < PROBES_AFTER_INSTALL && !up; attempt++) {
      deps.pause(PAUSE_MS);
      up = deps.starts(ctx.home);
    }
  }
  if (!up) {
    const fix = `${root ? "" : "sudo "}node ${shQuote(cli)} install-deps chromium`;
    ctx.refuse(`Chromium cannot start on this machine, most likely because system libraries are missing. Install them (this uses apt) with: ${fix}  then run this again. If the browser itself is missing, install it with: node ${shQuote(cli)} install chromium`);
  }
}

export default { name: "linux", npmNeedsShell: false, rootRisk, othersCanChange, ensureBrowser };
