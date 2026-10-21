// Linux: the Chromium download works on a minimal Ubuntu, but the browser cannot start without system libraries, and
// Playwright then reports only "browser has been closed". So the adapter starts the browser once. If that fails it installs
// the libraries when the plugin already runs as root (a server or a container) on its own checkout and root owns the files it
// would run, and otherwise refuses with the exact command. Root never runs a file that a normal user can change.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const MARK = ".proof-lab-browser-ok"; // inside node_modules: Chromium has started on this machine
const START = "import { chromium } from 'playwright'; const b = await chromium.launch({ headless: true }); await b.close();";

// A path for a shell command line: in single quotes, so nothing in it is expanded when the user pastes the command.
const shQuote = text => `'${String(text).replace(/'/g, `'\''`)}'`;

// The calls that touch the machine are in `real` so a test can replace them.
const real = {
  exists: existsSync,
  mark: path => writeFileSync(path, ""),
  isRoot: () => process.getuid?.() === 0,
  // True when root owns the checkout and the file, and neither can be changed by group or others.
  rootOwns: (cli, home) => {
    const fileInfo = statSync(cli);
    return fileInfo.uid === 0 && (fileInfo.mode & 0o022) === 0 && statSync(home).uid === 0;
  },
  pause: ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms),
  starts: home => spawnSync(process.execPath, ["--input-type=module", "-e", START], { cwd: home, stdio: "ignore", timeout: 60_000 }).status === 0,
  installDeps: (cli, home, timeout) => execFileSync(process.execPath, [cli, "install-deps", "chromium"], { cwd: home, stdio: ["ignore", process.stderr, process.stderr], timeout }),
};

export function ensureBrowser(ctx, deps = real) {
  const cli = join(ctx.home, "node_modules", "playwright", "cli.js");
  if (!deps.exists(cli)) return; // not a Playwright checkout (a test stand-in): nothing to start
  const mark = join(ctx.home, "node_modules", MARK);
  if (ctx.own && deps.exists(mark)) return;
  if (!deps.starts(ctx.home)) {
    const root = deps.isRoot();
    const mayInstall = root && ctx.own && deps.rootOwns(cli, ctx.home);
    let up = false;
    if (mayInstall) {
      try {
        console.error("Chromium cannot start: installing its system libraries (apt)");
        deps.installDeps(cli, ctx.home, ctx.timeoutMs);
      } catch {}
      // Another run may be installing at the same moment (apt allows one at a time): look twice more before giving up.
      up = deps.starts(ctx.home);
      for (let attempt = 0; attempt < 2 && !up; attempt++) {
        deps.pause(5000);
        up = deps.starts(ctx.home);
      }
    }
    if (!up) {
      const fix = `${root ? "" : "sudo "}node ${shQuote(cli)} install-deps chromium`;
      ctx.refuse(`Chromium cannot start on this machine, most likely because system libraries are missing. Install them (this uses apt) with: ${fix}  then run this again. If the browser itself is missing, install it with: node ${shQuote(cli)} install chromium`);
    }
  }
  if (ctx.own) deps.mark(mark);
}

export default { name: "linux", npmNeedsShell: false, ensureBrowser };
