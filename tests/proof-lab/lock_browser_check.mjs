// Run by test_lock_and_browsers.py: prints one JSON line per check, {"name": ..., "ok": true|false, "detail": ...}.
// The install lock (owner token, gone owners, put-back) and the browser digest check, each on temporary folders.
import { spawn, spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, symlinkSync, utimesSync, writeFileSync } from "node:fs";
import { hostname, tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { downloads, treeDigest, verifyBrowsers } from "../../plugins/proof-lab/scripts/browser-pin.mjs";
import { clear, identify, withInstallLock } from "../../plugins/proof-lab/scripts/install-lock.mjs";
import { othersCanChange, rootRisk } from "../../plugins/proof-lab/scripts/platform/posix.mjs";

const out = (name, ok, detail = "") => console.log(JSON.stringify({ name, ok: Boolean(ok), detail: String(detail) }));
const base = mkdtempSync(join(tmpdir(), "pl-lock-"));
let n = 0;
const fresh = () => {
  const home = join(base, `h${n++}`);
  mkdirSync(home);
  return { home, lock: `${home}.lock` };
};
const hold = (lock, owner) => {
  mkdirSync(lock);
  if (owner) writeFileSync(join(lock, "owner.json"), JSON.stringify(owner));
};
const LONG = { staleMs: 60_000 }; // a lock this young is live by its time alone
const pause = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
const timed = fn => {
  const t = Date.now();
  const value = fn();
  return { value, ms: Date.now() - t };
};
const until = (ok, ms = 20_000) => {
  const end = Date.now() + ms;
  while (!ok() && Date.now() < end) pause(50);
  return ok();
};
// A process that removes the lock after `ms`, and is its live owner until then.
const remover = (lock, ms) => spawn(process.execPath, ["-e", `setTimeout(() => require("fs").rmSync(${JSON.stringify(lock)}, { recursive: true, force: true }), ${ms})`], { stdio: "ignore" });
// Another run that holds the lock for `ms` the way setup does, keeping it fresh.
const LOCK_MODULE = new URL("../../plugins/proof-lab/scripts/install-lock.mjs", import.meta.url).href;
const FRESH = { staleMs: 3000, beatMs: 200 };
const holder = (home, ms) => spawn(process.execPath, ["--input-type=module", "-e", `import { withInstallLock } from ${JSON.stringify(LOCK_MODULE)}; withInstallLock(${JSON.stringify(home)}, () => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ${ms}), ${JSON.stringify(FRESH)});`], { stdio: "ignore" });
const ownerOf = lock => {
  try {
    return JSON.parse(readFileSync(join(lock, "owner.json"), "utf8"));
  } catch {
    return null;
  }
};

try {
  // --- the install lock
  let { home, lock } = fresh();
  let during = null;
  let r = withInstallLock(home, () => {
    during = JSON.parse(readFileSync(join(lock, "owner.json"), "utf8"));
    return 7;
  });
  out("lock: the work runs under a lock that names this run, and the lock is gone after", r === 7 && during.pid === process.pid && during.host === hostname() && typeof during.token === "string" && !existsSync(lock), JSON.stringify(during));

  ({ home, lock } = fresh());
  const dead = spawnSync(process.execPath, ["-e", "0"]).pid;
  hold(lock, { token: "t-dead", pid: dead, host: hostname() });
  let t = timed(() => withInstallLock(home, () => "ran"));
  out("lock: a lock whose process has ended on this host is cleared at once", t.value === "ran" && t.ms < 1500 && !existsSync(lock), `${t.ms} ms`);

  ({ home, lock } = fresh());
  hold(lock, { token: "t-same-pid", pid: process.pid, host: hostname() });
  t = timed(() => withInstallLock(home, () => "ran"));
  out("lock: a lock with this process's id but another token (a reused id) is cleared at once", t.value === "ran" && t.ms < 1500, `${t.ms} ms`);

  ({ home, lock } = fresh());
  let child = remover(lock, 2500);
  hold(lock, { token: "t-live", pid: child.pid, host: hostname() });
  t = timed(() => withInstallLock(home, () => "ran", LONG));
  out("lock: a fresh lock whose process still runs is waited for, not cleared", t.value === "ran" && t.ms >= 2000, `${t.ms} ms`);

  // The process id now belongs to a program that is not proof-lab: it runs, but nobody keeps the lock fresh.
  ({ home, lock } = fresh());
  child = remover(lock, 60_000);
  hold(lock, { token: "t-reused", pid: child.pid, host: hostname() });
  utimesSync(lock, 1_000_000_000, 1_000_000_000);
  t = timed(() => withInstallLock(home, () => "ran"));
  out("lock: a stale lock whose process id runs another program is cleared at once, with no wait", t.value === "ran" && t.ms < 1500, `${t.ms} ms`);
  child.kill();

  ({ home, lock } = fresh());
  child = remover(lock, 2500);
  hold(lock, { token: "t-elsewhere", pid: 1, host: `${hostname()}-other` });
  t = timed(() => withInstallLock(home, () => "ran", LONG));
  out("lock: a fresh lock from another host is waited for", t.value === "ran" && t.ms >= 2000, `${t.ms} ms`);
  child.kill();

  ({ home, lock } = fresh());
  hold(lock, { token: "t-old", pid: 1, host: `${hostname()}-other` });
  utimesSync(lock, 1_000_000_000, 1_000_000_000);
  t = timed(() => withInstallLock(home, () => "ran"));
  out("lock: a stale lock from another host is cleared", t.value === "ran" && t.ms < 1500, `${t.ms} ms`);

  // A real holder: its thread keeps the lock fresh past staleMs, so the next run waits for it, and then takes a young lock.
  ({ home, lock } = fresh());
  child = holder(home, 5000);
  until(() => ownerOf(lock) !== null);
  t = timed(() => withInstallLock(home, () => identify(lock).ageMs, FRESH));
  out("lock: a holder keeps its lock fresh while it works: the next run waits past staleMs, then takes a young lock", t.ms >= FRESH.staleMs && t.value < FRESH.staleMs, `waited ${t.ms} ms, age ${t.value} ms`);
  child.kill();

  // A holder that is killed: its thread ends with it, so nobody keeps the lock fresh any more.
  ({ home, lock } = fresh());
  child = holder(home, 60_000);
  until(() => ownerOf(lock) !== null);
  const first = statSync(lock).mtimeMs;
  const beating = until(() => statSync(lock).mtimeMs > first, 10_000);
  child.kill("SIGKILL");
  until(() => child.exitCode !== null || child.signalCode !== null, 5000);
  const after = statSync(lock).mtimeMs;
  pause(1500);
  out("lock: a killed holder's lock stops being kept fresh", beating && statSync(lock).mtimeMs === after, `kept fresh before: ${beating}`);
  t = timed(() => withInstallLock(home, () => "ran"));
  out("lock: and the next run clears it at once", t.value === "ran" && t.ms < 1500, `${t.ms} ms`);

  ({ home, lock } = fresh());
  withInstallLock(home, () => {
    rmSync(lock, { recursive: true, force: true }); // cleared as gone meanwhile, and taken by another run
    hold(lock, { token: "t-other", pid: process.pid, host: hostname() });
  });
  let owner = existsSync(lock) ? JSON.parse(readFileSync(join(lock, "owner.json"), "utf8")).token : null;
  out("lock: a run never removes a lock that another run holds by then", owner === "t-other", String(owner));
  rmSync(lock, { recursive: true, force: true });

  ({ home, lock } = fresh());
  hold(lock, { token: "t-judged", pid: 1, host: hostname() });
  const judged = identify(lock);
  rmSync(lock, { recursive: true, force: true }); // between the look and the rename another run cleared it and took the path
  hold(lock, { token: "t-new", pid: process.pid, host: hostname() });
  clear(lock, judged, "t-clearer");
  owner = existsSync(lock) ? JSON.parse(readFileSync(join(lock, "owner.json"), "utf8")).token : null;
  out("lock: a lock that changed between the look and the rename is put back, not removed", owner === "t-new" && !existsSync(`${lock}.stale-t-clearer`), String(owner));
  rmSync(lock, { recursive: true, force: true });

  ({ home, lock } = fresh());
  hold(lock, { token: "t-judged", pid: 1, host: hostname() });
  clear(lock, identify(lock), "t-clearer");
  out("lock: the lock that was judged gone is removed", !existsSync(lock) && !existsSync(`${lock}.stale-t-clearer`));

  // An empty lock (an older plugin, between its mkdir and its owner file) is waited for: the new lock is not renamed over it.
  ({ home, lock } = fresh());
  child = remover(lock, 2500);
  hold(lock, null);
  t = timed(() => withInstallLock(home, () => JSON.parse(readFileSync(join(lock, "owner.json"), "utf8")).pid, LONG));
  out("lock: an empty lock is waited for, not replaced, and the lock this run takes already names it", t.value === process.pid && t.ms >= 2000, `${t.ms} ms`);
  child.kill();

  ({ home, lock } = fresh());
  for (const name of ["stale-left", "new-left"]) {
    mkdirSync(`${lock}.${name}`);
    utimesSync(`${lock}.${name}`, 1_000_000_000, 1_000_000_000);
  }
  mkdirSync(`${lock}.stale-young`);
  withInstallLock(home, () => {});
  out("lock: an old folder that a killed run left beside the lock is removed, a young one is kept", !existsSync(`${lock}.stale-left`) && !existsSync(`${lock}.new-left`) && existsSync(`${lock}.stale-young`));
  out("lock: no new-lock folder is left beside the lock after a run", !readdirSync(dirname(lock)).some(name => name.startsWith(`${basename(lock)}.new-`)));

  // --- the root warning (the machine calls replaced)
  out("root warning: none for a normal user", rootRisk({ home: "/h" }, { isRoot: () => false, trustedTree: () => false }) === "");
  out("root warning: none for root on a checkout only root can change", rootRisk({ home: "/h" }, { isRoot: () => true, trustedTree: () => true }) === "");
  const warning = rootRisk({ home: "/h/lab" }, { isRoot: () => true, trustedTree: () => false });
  out("root warning: root on a checkout a normal user can change is warned, naming the checkout and what runs as root", warning.includes("/h/lab") && warning.includes("npm ci and the spec run as root") && warning.includes("browser step is skipped"), warning);
  out("others can change: never for a normal user", othersCanChange("/anything", { isRoot: () => false }) === false);
  // The real file checks, where this runs as root (the Ubuntu container): a tree under /root, which only root can change.
  if (process.getuid?.() === 0) {
    const top = mkdtempSync("/root/pl-trust-");
    try {
      const tree = join(top, "browser");
      mkdirSync(join(tree, "bin"), { recursive: true });
      writeFileSync(join(tree, "bin", "chrome"), "x");
      out("root: a root-only folder is not changeable by others", othersCanChange(tree) === false);
      out("root: a folder not made yet under a root-only folder is not either", othersCanChange(join(top, "later", "x")) === false);
      symlinkSync("bin/chrome", join(tree, "inside"));
      out("root: a link that points inside the folder is allowed", othersCanChange(tree) === false);
      symlinkSync("/tmp", join(tree, "outside"));
      out("root: a link that points outside the folder is not", othersCanChange(tree) === true);
      rmSync(join(tree, "outside"));
      // bin/dots is "self/../../escape": read as text it stays inside the tree (tree/escape), but the system follows self to
      // bin first, goes up twice from there and leaves the tree (top/escape).
      symlinkSync(".", join(tree, "bin", "self"));
      symlinkSync("self/../../escape", join(tree, "bin", "dots"));
      out("root: a link inside the folder that leaves it through \"..\" after a link is not allowed", othersCanChange(tree) === true);
      rmSync(join(tree, "bin", "dots"));
      out("root: a link to the folder it is in is allowed", othersCanChange(tree) === false);
      rmSync(join(tree, "bin", "self"));
      // The browser folder itself is a link, in a root-only folder, to a folder that holds a file others can write.
      const target = join(top, "target");
      mkdirSync(target);
      writeFileSync(join(target, "chrome"), "x");
      symlinkSync(target, join(top, "pointer"));
      out("root: a browser folder that is a link to a root-only folder is allowed", othersCanChange(join(top, "pointer")) === false);
      chmodSync(join(target, "chrome"), 0o666);
      out("root: a browser folder that is a link is judged where it leads (a file there others can write)", othersCanChange(join(top, "pointer")) === true);
      out("root: a relative path is not judged and counts as changeable", othersCanChange("relative/browser") === true);
      symlinkSync(tree, join(top, "alias"));
      out("root: a root-owned link above the path, in a root-only folder, is allowed (macOS /var)", othersCanChange(join(top, "alias", "bin")) === false);
      symlinkSync("/tmp", join(top, "open"));
      out("root: a link above the path that leads into a folder others can change is not", othersCanChange(join(top, "open", "x")) === true);
      const shared = join(top, "shared");
      mkdirSync(shared, { mode: 0o777 });
      chmodSync(shared, 0o777);
      out("root: a folder not made yet under a folder others can write is changeable", othersCanChange(join(shared, "x")) === true);
      // A root-owned link whose target goes through a second link that sits in a folder others can write: that user can
      // repoint the second link, so the path is changeable even though both ends are root's.
      symlinkSync(tree, join(shared, "relay"));
      symlinkSync(join(shared, "relay"), join(top, "chain"));
      out("root: a link chain through a folder others can write is changeable", othersCanChange(join(top, "chain", "bin")) === true);
      const deep = join(top, "deep");
      mkdirSync(deep);
      symlinkSync(shared, join(deep, "via"));
      out("root: a path that passes through a folder others can write between two links is changeable", othersCanChange(join(deep, "via", "relay", "bin")) === true);
      // A relative target "s/../t": the system follows s first and then goes up from where s leads (into shared), while a
      // lexical reading would stay in top, where a root-only t also exists.
      mkdirSync(join(shared, "sub"));
      mkdirSync(join(shared, "t"));
      mkdirSync(join(top, "t"));
      symlinkSync(join(shared, "sub"), join(top, "s"));
      symlinkSync("s/../t", join(top, "dotted"));
      out("root: a \"..\" after a link in a link target is followed the way the system does", othersCanChange(join(top, "dotted", "x")) === true);
      chmodSync(join(tree, "bin", "chrome"), 0o666);
      out("root: a file in the folder that others can write makes it changeable", othersCanChange(tree) === true);
    } finally {
      rmSync(top, { recursive: true, force: true });
    }
  }

  // --- the browser digest check
  const browsers = join(base, "browsers");
  const shell = join(browsers, "shell-1");
  const chrome = join(browsers, "chrome-1");
  mkdirSync(join(shell, "bin"), { recursive: true });
  writeFileSync(join(shell, "bin", "shell"), "shell bytes");
  writeFileSync(join(shell, "INSTALLATION_COMPLETE"), "");
  const d0 = treeDigest(shell);
  writeFileSync(join(shell, "DEPENDENCIES_VALIDATED"), "");
  writeFileSync(join(shell, "INSTALLATION_COMPLETE"), "rewritten");
  out("digest: Playwright's own marker files are left out", treeDigest(shell) === d0);
  writeFileSync(join(shell, "bin", "INSTALLATION_COMPLETE"), "");
  out("digest: a file with a marker's name deeper in the folder is counted", treeDigest(shell) !== d0);
  rmSync(join(shell, "bin", "INSTALLATION_COMPLETE"));
  writeFileSync(join(shell, "bin", "debug.log"), "written by the browser when it ran");
  out("digest: the debug.log that the browser writes beside its program is left out", treeDigest(shell) === d0);
  rmSync(join(shell, "bin", "debug.log"));
  mkdirSync(join(shell, "bin", "debug.log"));
  out("digest: a folder named debug.log is counted (only the log file is left out)", treeDigest(shell) !== d0);
  rmSync(join(shell, "bin", "debug.log"), { recursive: true });
  writeFileSync(join(shell, "bin", "shell"), "shell bytez");
  out("digest: a changed byte changes the digest", treeDigest(shell) !== d0);
  writeFileSync(join(shell, "bin", "shell"), "shell bytes");
  mkdirSync(join(shell, "empty"));
  out("digest: an added folder changes the digest", treeDigest(shell) !== d0);
  rmSync(join(shell, "empty"), { recursive: true });
  let linked = true;
  try {
    symlinkSync("bin/shell", join(shell, "link"));
  } catch {
    linked = false; // making a link needs a right that this machine does not give
  }
  if (linked) {
    const withLink = treeDigest(shell);
    rmSync(join(shell, "link"));
    symlinkSync("bin/other", join(shell, "link"));
    out("digest: a link counts by where it points", treeDigest(shell) !== withLink && withLink !== d0);
    rmSync(join(shell, "link"));
  }
  out("digest: the same folder gives the same digest", treeDigest(shell) === d0);

  // A stand-in for playwright/cli.js: prints what `install --dry-run chromium` prints, for the folders above.
  const dry = [
    "Chrome for Testing 1 (playwright chromium v1)",
    `  Install location:    ${chrome}`,
    "  Download url:        https://cdn.example/builds/cft/1/x64/chrome.zip",
    "",
    "FFmpeg (playwright ffmpeg v1)",
    `  Install location:    ${join(browsers, "ffmpeg-1")}`,
    "  Download url:        https://cdn.example/dbazure/download/playwright/builds/ffmpeg/1/ffmpeg.zip",
    "  Download fallback 1: https://mirror.example/builds/ffmpeg/1/ffmpeg.zip",
    "",
    "Chrome Headless Shell 1 (playwright chromium-headless-shell v1)",
    `  Install location:    ${shell}`,
    "  Download url:        https://cdn.example/builds/cft/1/x64/shell.zip",
    "",
    "System thing",
    "  Install location:    <system>",
    "",
  ].join("\n");
  const cli = join(base, "cli.js");
  writeFileSync(cli, `if (process.env.FAKE_FAIL) { console.error("broken"); process.exit(1); }\nprocess.stdout.write(${JSON.stringify(dry)});\n`);
  const listed = downloads(cli);
  out("downloads: each folder with its archive path from builds/ on, fallbacks and <system> left out", JSON.stringify(listed) === JSON.stringify([
    { dir: chrome, key: "builds/cft/1/x64/chrome.zip", url: "https://cdn.example/builds/cft/1/x64/chrome.zip" },
    { dir: join(browsers, "ffmpeg-1"), key: "builds/ffmpeg/1/ffmpeg.zip", url: "https://cdn.example/dbazure/download/playwright/builds/ffmpeg/1/ffmpeg.zip" },
    { dir: shell, key: "builds/cft/1/x64/shell.zip", url: "https://cdn.example/builds/cft/1/x64/shell.zip" },
  ]), JSON.stringify(listed));
  let threw = null;
  try {
    downloads(cli, { ...process.env, FAKE_FAIL: "1" });
  } catch (error) {
    threw = error.message;
  }
  out("downloads: a dry run that fails is an error, not an empty list", threw && threw.includes("broken"), String(threw));

  const refusal = fn => {
    try {
      fn();
      return null;
    } catch (error) {
      return error.message;
    }
  };
  const refuse = m => {
    throw new Error(m);
  };
  const record = join(base, "data", "checked.json");
  const pins = { "builds/cft/1/x64/shell.zip": d0 };
  out("verify: an installed folder that matches its digest passes; folders not installed are skipped", refusal(() => verifyBrowsers({ cli, pins, record, refuse })) === null && existsSync(record));
  writeFileSync(join(shell, "bin", "shell"), "changed later, marker kept");
  out("verify: a folder already checked since its last install is not hashed again", refusal(() => verifyBrowsers({ cli, pins, record, refuse })) === null);
  utimesSync(join(shell, "INSTALLATION_COMPLETE"), new Date(), new Date(Date.now() + 5000));
  let m = refusal(() => verifyBrowsers({ cli, pins, record, refuse }));
  out("verify: a folder installed again is checked again, and a mismatch is refused with the reinstall command", m && m.includes("does not match") && m.includes("install --force chromium"), String(m));
  writeFileSync(join(shell, "bin", "shell"), "shell bytes");
  const passes = refusal(() => verifyBrowsers({ cli, pins, record, refuse })) === null;
  writeFileSync(join(shell, "bin", "shell"), "changed after the check");
  m = refusal(() => verifyBrowsers({ cli, pins, record: null, refuse }));
  out("verify: without a record every call checks", passes && m && m.includes("does not match"), String(m));
  writeFileSync(join(shell, "bin", "shell"), "shell bytes");
  rmSync(join(shell, "INSTALLATION_COMPLETE"));
  writeFileSync(join(shell, "bin", "shell"), "no marker, changed");
  m = refusal(() => verifyBrowsers({ cli, pins, record, refuse }));
  out("verify: a folder without Playwright's marker is checked on every call", m && m.includes("does not match"), String(m));
  writeFileSync(join(shell, "bin", "shell"), "shell bytes");
  mkdirSync(chrome);
  m = refusal(() => verifyBrowsers({ cli, pins, record, refuse }));
  out("verify: an installed folder with no pinned digest is refused", m && m.includes("builds/cft/1/x64/chrome.zip") && m.includes("no digest"), String(m));
  rmSync(chrome, { recursive: true });
  m = refusal(() => verifyBrowsers({ cli, pins, record: null, refuse, othersCanChange: dir => dir === shell }));
  out("verify: a browser folder that a user with fewer rights can change is refused before it is used", m && m.includes(shell) && m.includes("fewer rights"), String(m));
  m = refusal(() => verifyBrowsers({ cli, pins, record: null, refuse, othersCanChange: dir => dir === chrome }));
  out("verify: so is one not installed yet (it could be made there before a start)", m && m.includes(chrome) && m.includes("fewer rights"), String(m));
} finally {
  rmSync(base, { recursive: true, force: true });
}
