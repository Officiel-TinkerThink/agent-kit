// Linux: the Chromium download works on a minimal Ubuntu, but the browser cannot start without system libraries, and
// Playwright then reports only "browser has been closed". So the adapter starts the browser, and if that fails it
//   - installs the libraries (apt, through Playwright's install-deps) when the plugin runs as root on its own checkout and
//     root owns every file it would run, or
//   - refuses with the exact command, when the plugin runs as a normal user.
// Root never runs a file that a normal user can change: as root, on a checkout root does not own, the adapter does nothing.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, lstatSync, readdirSync } from "node:fs";
import { join } from "node:path";

const START = "import { chromium } from 'playwright'; const b = await chromium.launch({ headless: true }); await b.close();";
const PROBES_AFTER_INSTALL = 12; // apt allows one install at a time; another run may be installing, so look for about two minutes
const PAUSE_MS = 10_000;

// A path for a shell command line: in single quotes, so nothing in it is expanded when the user pastes the command.
export const shQuote = text => `'${String(text).replace(/'/g, "'\\''")}'`;

// True when root owns the folder and everything under it, none of it can be changed by group or others, and nothing is a link.
function rootOwnsTree(path) {
  const info = lstatSync(path);
  if (info.isSymbolicLink() || info.uid !== 0 || (info.mode & 0o022) !== 0) return false;
  return !info.isDirectory() || readdirSync(path).every(name => rootOwnsTree(join(path, name)));
}

// The calls that touch the machine are in `real`, so a test can replace them.
const real = {
  exists: existsSync,
  isRoot: () => process.getuid?.() === 0,
  // The files root would run: the checkout and its node_modules folder, and the whole of the two Playwright packages.
  trustedTree: home => {
    try {
      return [home, join(home, "node_modules")].every(p => { const i = lstatSync(p); return !i.isSymbolicLink() && i.uid === 0 && (i.mode & 0o022) === 0; })
        && ["playwright", "playwright-core"].every(name => rootOwnsTree(join(home, "node_modules", name)));
    } catch {
      return false;
    }
  },
  starts: home => spawnSync(process.execPath, ["--input-type=module", "-e", START], { cwd: home, stdio: "ignore", timeout: 60_000 }).status === 0,
  installDeps: (cli, home, timeout) => execFileSync(process.execPath, [cli, "install-deps", "chromium"], { cwd: home, stdio: ["ignore", process.stderr, process.stderr], timeout }),
  pause: ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms),
};

export function ensureBrowser(ctx, deps = real) {
  const cli = join(ctx.home, "node_modules", "playwright", "cli.js");
  if (!deps.exists(cli)) return; // not a Playwright checkout (a test stand-in): nothing to start
  const root = deps.isRoot();
  if (root && !(ctx.own && deps.trustedTree(ctx.home))) {
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

export default { name: "linux", npmNeedsShell: false, ensureBrowser };
