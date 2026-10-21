// Makes the content of plugins/proof-lab/browsers.sha256.json (printed on stdout; progress goes to stderr).
// Run by tests/linux/browser-digests.sh inside the Ubuntu container: on Linux the links inside the macOS app bundles are made
// as links, so every build's digest is the one a real machine of that kind gets.
// Usage: node browser_digests.mjs <proof-lab checkout with node_modules> <empty scratch folder>
// For each build the pinned Playwright knows, it installs `chromium` for that build (PLAYWRIGHT_HOST_PLATFORM_OVERRIDE) into
// its own folder and takes the digest of every folder made. It then checks that every host platform Playwright maps to a
// build is covered, so a table that misses one fails here and not on a user's machine.
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { downloads, treeDigest } from "../../plugins/proof-lab/scripts/browser-pin.mjs";

const [home, scratch] = process.argv.slice(2);
const cli = join(home, "node_modules", "playwright", "cli.js");
const BUILDS = ["ubuntu24.04-x64", "ubuntu24.04-arm64", "mac15", "mac15-arm64", "win64"];
const HOSTS = ["ubuntu22.04-x64", "ubuntu24.04-x64", "ubuntu26.04-x64", "ubuntu22.04-arm64", "ubuntu24.04-arm64", "ubuntu26.04-arm64", "debian12-x64", "debian12-arm64", "debian13-x64", "debian13-arm64", "mac14", "mac14-arm64", "mac15", "mac15-arm64", "mac26", "mac26-arm64", "win64"];
const envFor = (build, browsers) => ({ ...process.env, PLAYWRIGHT_HOST_PLATFORM_OVERRIDE: build, PLAYWRIGHT_BROWSERS_PATH: browsers });
// On a real Windows machine `install chromium` also installs winldd (Playwright adds it when the system itself is Windows,
// which an override does not change). `install winldd` is refused, so its archive (one program, no links) is fetched and
// unpacked here; the dry run still names it, which gives its folder, its path and its URL.
const EXTRA = { win64: ["winldd"] };
const namesFor = build => ["chromium", ...(EXTRA[build] ?? [])];
const run = (cmd, args) => {
  const p = spawnSync(cmd, args, { stdio: ["ignore", process.stderr, process.stderr] });
  if (p.status !== 0) throw new Error(`${cmd} ${args.join(" ")} failed`);
};

const digests = {};
for (const build of BUILDS) {
  const browsers = join(scratch, build);
  mkdirSync(browsers, { recursive: true });
  console.error(`== ${build}`);
  const p = spawnSync(process.execPath, [cli, "install", "chromium"], { env: envFor(build, browsers), stdio: ["ignore", process.stderr, process.stderr] });
  if (p.status !== 0) throw new Error(`install for ${build} failed`);
  for (const { dir, url } of EXTRA[build] ? downloads(cli, envFor(build, browsers), EXTRA[build]) : []) {
    run("curl", ["-fsSL", "-o", `${dir}.zip`, url]);
    run("python3", ["-m", "zipfile", "-e", `${dir}.zip`, dir]);
    rmSync(`${dir}.zip`);
  }
  for (const { dir, key } of downloads(cli, envFor(build, browsers), namesFor(build))) {
    const digest = treeDigest(dir);
    if (digests[key] && digests[key] !== digest) throw new Error(`${key}: two different digests`);
    digests[key] = digest;
    console.error(`${key} ${digest}`);
  }
}
const missing = HOSTS.flatMap(host => downloads(cli, envFor(host, join(scratch, "dry")), namesFor(host)).map(d => d.key)).filter(key => !digests[key]);
if (missing.length) throw new Error(`not covered: ${[...new Set(missing)].join(", ")}`);
const version = JSON.parse(readFileSync(join(home, "node_modules", "playwright-core", "package.json"), "utf8")).version;
const sorted = Object.fromEntries(Object.entries(digests).sort(([a], [b]) => (a < b ? -1 : 1)));
console.log(JSON.stringify({ about: "Digests of the browser folders that `playwright install chromium` makes, keyed by archive path. Made by tests/linux/browser-digests.sh; read by scripts/browser-pin.mjs.", playwright: version, digests: sorted }, null, 2));
