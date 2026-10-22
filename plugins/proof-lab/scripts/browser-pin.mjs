// The browsers that Playwright downloads are not covered by the commit pin, and Playwright checks only their size. This
// module pins them too: browsers.sha256.json holds a digest of each folder that `playwright install chromium` makes, keyed by
// the archive's path from builds/ on (the same path on every mirror), one entry per build the pinned Playwright knows. The
// table is made by tests/linux/browser-digests.sh. Before the browser first starts, every installed folder is compared with
// its digest; a folder that does not match, or that has no digest, is refused. A folder is checked again whenever
// Playwright installs it again (its INSTALLATION_COMPLETE file is then new).
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, readlinkSync, renameSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, parse } from "node:path";

// Files that are written into a browser folder after the download, so they are not part of the archive: Playwright's own
// markers at the top, and the debug.log that Chrome writes beside its program when it runs (a log; nothing loads it).
const OWN_FILES = new Set(["INSTALLATION_COMPLETE", "DEPENDENCIES_VALIDATED"]);
const RUN_FILES = new Set(["debug.log"]);
const DONE = "INSTALLATION_COMPLETE";

// The folders and archives that `install chromium` uses on this machine, as Playwright itself reports them (--dry-run
// downloads nothing). Runs from the filesystem root, so no file inside the checkout can change how Node starts.
export function downloads(cli, env = process.env) {
  const p = spawnSync(process.execPath, [cli, "install", "--dry-run", "chromium"], { cwd: parse(cli).root, env, encoding: "utf8", timeout: 60_000 });
  if (p.status !== 0) throw new Error(`playwright install --dry-run failed: ${String(p.stderr?.trim() || p.stdout?.trim() || p.error?.message || `exit ${p.status}`).split("\n")[0]}`);
  const found = [];
  let dir = null;
  for (const line of p.stdout.split(/\r?\n/)) {
    const location = /^\s+Install location:\s+(.+?)\s*$/.exec(line);
    if (location) dir = location[1] === "<system>" ? null : location[1];
    const url = /^\s+Download url:\s+(\S+)/.exec(line);
    if (url && dir) {
      const at = url[1].lastIndexOf("/builds/");
      found.push({ dir, key: at === -1 ? url[1] : url[1].slice(at + 1), url: url[1] });
      dir = null;
    }
  }
  return found;
}

// One digest for a whole folder: every entry by its path from the folder, in a fixed order; a file by the SHA-256 of its
// bytes, a link by where it points. Modes are left out (they are not kept the same way on every file system).
export function treeDigest(root) {
  const all = createHash("sha256");
  const walk = rel => {
    for (const name of readdirSync(rel ? join(root, rel) : root).sort()) {
      if (!rel && OWN_FILES.has(name)) continue;
      const path = rel ? `${rel}/${name}` : name;
      const info = lstatSync(join(root, path));
      if (RUN_FILES.has(name) && info.isFile()) continue;
      if (info.isSymbolicLink()) {
        all.update(`L ${path} ${readlinkSync(join(root, path))}\n`);
      } else if (info.isDirectory()) {
        all.update(`D ${path}\n`);
        walk(path);
      } else {
        all.update(`F ${path} ${createHash("sha256").update(readFileSync(join(root, path))).digest("hex")}\n`);
      }
    }
  };
  walk("");
  return all.digest("hex");
}

function readRecord(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return {}; // none yet, or unreadable: every folder is checked
  }
}

// Checks every installed browser folder against `pins` ({ archive key: digest }). `record` is the file that remembers which
// folders were checked (null: check every time); the caller passes null when someone other than this run's user can
// change it. `othersCanChange(dir)` is the machine adapter's: true when this run has more rights than a user who can change
// the folder (root, and a normal user's folder), so it must not start a program from it. Throws through `refuse` when a
// folder must not be used, does not match or has no digest. A browser changed after its check without a new install is not
// hashed again: the pin is about the download, and whoever can change the folder could change it after any check.
export function verifyBrowsers({ cli, pins, record, refuse, othersCanChange = () => false, env = process.env }) {
  const seen = record ? readRecord(record) : {};
  let changed = false;
  for (const { dir, key } of downloads(cli, env)) {
    // Asked first: a folder not installed yet, under a folder that someone else can change, could be made there before a start.
    if (othersCanChange(dir)) refuse(`${dir} (or a folder above it) can be changed by a user with fewer rights than this run, which would then start a program that user can change. Install the browsers into a folder only this run's user can change (PLAYWRIGHT_BROWSERS_PATH), or run proof-lab as that user`);
    if (!existsSync(dir)) continue; // not installed: nothing of it can start
    const want = pins[key];
    if (!want) refuse(`the browser archive ${key} has no digest in browsers.sha256.json, so ${dir} cannot be checked: this plugin version does not know the Playwright build for this machine`);
    let done = null;
    try {
      done = statSync(join(dir, DONE)).mtimeMs;
    } catch {}
    const before = seen[dir];
    if (done !== null && before && before.key === key && before.digest === want && before.done === done) continue;
    let got;
    try {
      got = treeDigest(dir);
    } catch (error) {
      refuse(`could not read ${dir} to check it (${error.message})`);
    }
    if (got !== want) refuse(`${dir} does not match the digest this plugin pins for ${key}, so the download may have been changed. Download it again with: node "${cli}" install --force chromium  then run this again`);
    if (done !== null) {
      seen[dir] = { key, digest: want, done };
      changed = true;
    }
  }
  if (record && changed) {
    try {
      const tmp = `${record}.tmp-${process.pid}`;
      mkdirSync(dirname(record), { recursive: true });
      writeFileSync(tmp, `${JSON.stringify(seen, null, 1)}\n`);
      renameSync(tmp, record); // whole or not at all: a run that reads it meanwhile sees the old or the new record
    } catch {} // a record that cannot be written only means the next run checks again
  }
}
