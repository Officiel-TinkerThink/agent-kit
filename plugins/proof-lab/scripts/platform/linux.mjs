// Linux: the Chromium download works on a minimal Ubuntu, but the browser cannot start without system libraries, and
// Playwright then reports only "browser has been closed". So the adapter starts the browser once. If that fails it installs
// the libraries when the plugin already runs as root (a server or a container), and otherwise refuses with the exact command.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const MARK = ".proof-lab-browser-ok"; // inside node_modules: Chromium has started on this machine
const START = "import { chromium } from 'playwright'; const b = await chromium.launch({ headless: true }); await b.close();";

// The calls that touch the machine are in `real` so a test can replace them.
const real = {
  exists: existsSync,
  mark: path => writeFileSync(path, ""),
  isRoot: () => process.getuid?.() === 0,
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
    if (root) {
      try {
        console.error("Chromium cannot start: installing its system libraries (apt)");
        deps.installDeps(cli, ctx.home, ctx.timeoutMs);
      } catch {}
    }
    if (!root || !deps.starts(ctx.home)) {
      ctx.refuse(`Chromium cannot start on this machine, most likely because system libraries are missing. Install them (this uses apt) with: ${root ? "" : "sudo "}node "${cli}" install-deps chromium  then run this again`);
    }
  }
  if (ctx.own) deps.mark(mark);
}

export default { name: "linux", npmNeedsShell: false, ensureBrowser };
