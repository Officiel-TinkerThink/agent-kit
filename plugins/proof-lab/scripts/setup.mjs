#!/usr/bin/env node
// Checks that the proof-lab checkout is the one this plugin is pinned to, then installs its dependencies (npm ci).
// The checkout is PROOF_LAB_HOME when set. When it is not set, the plugin keeps its own checkout under ~/.proof-lab/checkouts/<pin>
// and fetches it from the proof-lab repository on first use (by commit hash, so git verifies what arrives).
// Exit 0: ready. Exit 2: refused, with the reason on stderr. --check-only checks and does not install.
// --run <args>: checks the same way, then runs src/run-spec.js with <args> and returns its exit code. Every proof run goes
// through this, so a run never starts on a checkout that does not match the pin.
import { execFileSync, spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { verifyBrowsers } from "./browser-pin.mjs";
import { withInstallLock } from "./install-lock.mjs";
import { forThisMachine } from "./platform/index.mjs";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PIN_FILE = join(PLUGIN, "proof-lab.pin");
const BROWSER_PINS = join(PLUGIN, "browsers.sha256.json");
const MIN_NODE = 24;
// The repository the pin is fetched from. PROOF_LAB_REPO replaces it (tests); the pin check holds for any source.
const DEFAULT_REPO = "https://github.com/Officiel-TinkerThink/proof-lab.git";
const machine = forThisMachine(); // the adapter for the operating system this runs on; no other code looks at the system
const sh = machine.npmNeedsShell;
const STEP_TIMEOUT_MS = 10 * 60 * 1000; // one git or npm step; a stalled network ends in a refusal, not a hang
const BROWSER_TIMEOUT_MS = 30 * 60 * 1000; // the Chromium download is the one large step
const DEPS_DONE = ".proof-lab-installed"; // written inside node_modules after a whole install; a killed install lacks it
const STALE_TMP_MS = 60 * 60 * 1000; // an install or dependency folder this old belongs to a run that was killed
const firstLine = text => String(text).split("\n")[0].trim();

class Refused extends Error {}
const refuse = message => {
  throw new Refused(message);
};

// The pin is the first line that is not blank and not a comment: one full commit hash.
function readPin(text) {
  const line = text.split(/\r?\n/).map(s => s.trim()).find(s => s !== "" && !s.startsWith("#"));
  if (!/^[0-9a-f]{40}$/.test(line ?? "")) refuse(`${PIN_FILE} must hold one full 40-character commit hash`);
  return line;
}

function git(home, args) {
  try {
    return execFileSync("git", ["-C", home, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch {
    return refuse(`${home} is not a git checkout (git ${args[0]} failed)`);
  }
}

function proofLabName(home) {
  try {
    return JSON.parse(readFileSync(join(home, "package.json"), "utf8")).name;
  } catch {
    return undefined;
  }
}

const dataFolder = env => env.PROOF_LAB_DATA ?? join(homedir(), ".proof-lab");

// Where the plugin keeps its own checkout when PROOF_LAB_HOME is not set: one folder per pin, so a new pin is a new checkout.
export function managedHome(env, pin) {
  return join(dataFolder(env), "checkouts", pin);
}

// The repository address without any user:password part, for messages.
const shownRepo = repo => String(repo).replace(/^([a-z][a-z0-9+.-]*:\/\/)[^/]*@/i, "$1");

// Removes install and dependency folders that a killed run left beside the final path (the pid in the name is not reused by
// the next run; a dependency folder has a random name). An old folder is renamed first and removed under its new name, so a
// run that was only suspended finds its folder gone as a whole, never half removed (a removal can stop part way on Windows),
// and fails instead of moving it in; a folder that cannot be renamed (its files still open) is left. A removal that stops part
// way keeps the prefix, so a later run finishes it.
function removeStaleTemps(home) {
  const parent = dirname(home);
  const prefixes = [`${basename(home)}.tmp-`, `${basename(home)}.deps-`];
  let names = [];
  try {
    names = readdirSync(parent);
  } catch {}
  for (const name of names) {
    if (!prefixes.some(prefix => name.startsWith(prefix))) continue;
    try {
      if (Date.now() - statSync(join(parent, name)).mtimeMs <= STALE_TMP_MS) continue;
      const doomed = join(parent, `${basename(home)}.deps-${randomUUID()}`);
      renameSync(join(parent, name), doomed);
      rmSync(doomed, { recursive: true, force: true });
    } catch {}
  }
}

// Renames tmp to home. On Windows a scanner can hold a file for a moment, so a failed rename is tried again a few times.
function moveIntoPlace(tmp, home) {
  for (let attempt = 1; ; attempt++) {
    try {
      return renameSync(tmp, home);
    } catch (error) {
      if (existsSync(home)) return; // another run finished first: use its checkout
      if (attempt >= 4) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500 * attempt);
    }
  }
}

// Fetches the pinned commit into a temporary folder, installs dependencies and the browser there, then renames it into place,
// so a failed or interrupted install never leaves a half-made checkout at the final path.
export function provision(env, pin, home) {
  const repo = env.PROOF_LAB_REPO ?? DEFAULT_REPO;
  const tmp = `${home}.tmp-${process.pid}`;
  mkdirSync(dirname(home), { recursive: true });
  removeStaleTemps(home);
  rmSync(tmp, { recursive: true, force: true });
  mkdirSync(tmp);
  try {
    const run = (cmd, args, cwd, timeout = STEP_TIMEOUT_MS) => execFileSync(cmd, args, { cwd, stdio: ["ignore", process.stderr, process.stderr], shell: sh && cmd === "npm", timeout });
    console.error(`setting up proof-lab ${pin} in ${home} (first use only)`);
    run("git", ["init", "-q"], tmp);
    run("git", ["remote", "add", "origin", repo], tmp);
    run("git", ["fetch", "-q", "--depth", "1", "origin", pin], tmp);
    run("git", ["-c", "advice.detachedHead=false", "checkout", "-q", "--detach", pin], tmp);
    if (git(tmp, ["rev-parse", "HEAD"]).trim() !== pin) refuse(`the fetched commit is not ${pin}`);
    run("npm", ["ci", "--ignore-scripts"], tmp);
    const playwright = join(tmp, "node_modules", "playwright", "cli.js");
    if (existsSync(playwright)) run(process.execPath, [playwright, "install", "chromium"], tmp, BROWSER_TIMEOUT_MS);
    markInstalled(tmp);
    moveIntoPlace(tmp, home);
  } catch (error) {
    if (error instanceof Refused) throw error;
    refuse(`could not set up proof-lab in ${home} (${firstLine(error.message)}): check the network and that ${shownRepo(repo)} is reachable, or set PROOF_LAB_HOME to a checkout at the pin`);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

// The checks that need nothing from the checkout. They run before anything is fetched, so a refusal costs no install.
// Returns the pin and the folder the checkout is (or will be) in.
function preflight(env, pinText) {
  const major = Number(process.versions.node.split(".")[0]);
  if (major < MIN_NODE) refuse(`Node ${MIN_NODE} or later is required; this is ${process.versions.node}`);
  const pin = readPin(pinText);
  const home = env.PROOF_LAB_HOME || managedHome(env, pin);
  if (!isAbsolute(home)) refuse(`${env.PROOF_LAB_HOME ? "PROOF_LAB_HOME" : "PROOF_LAB_DATA"} must be an absolute path`);
  return { pin, home };
}

// Every check the plugin makes before it trusts a checkout. Throws Refused with the reason.
export function check(env, pinText) {
  const { pin, home } = preflight(env, pinText);
  if (!existsSync(home) || proofLabName(home) !== "proof-lab") refuse(`${home} is not a proof-lab checkout (no package.json named proof-lab)${env.PROOF_LAB_HOME ? "" : ": run node setup.mjs once (without --check-only) to fetch it"}`);
  const head = git(home, ["rev-parse", "HEAD"]).trim();
  if (head !== pin) refuse(`the checkout is at ${head}, this plugin is pinned to ${pin}: check out ${pin} in ${home}, or change the pin in a pull request`);
  if (git(home, ["status", "--porcelain"]).trim() !== "") refuse(`${home} has uncommitted changes: commit or stash them first, so the receipts match one revision`);
  return { home, pin, receipts: env.PROOF_LAB_RECEIPTS ?? join(home, "receipts") };
}

function markInstalled(folder) {
  mkdirSync(join(folder, "node_modules"), { recursive: true });
  writeFileSync(join(folder, "node_modules", DEPS_DONE), "");
}

// A checkout the user named is installed in place, as the user would.
function installDependencies(home) {
  execFileSync("npm", ["ci"], { cwd: home, stdio: "inherit", shell: sh, timeout: STEP_TIMEOUT_MS });
}

// Moves from to to, trying again when a virus scanner holds a file for a moment. Returns false when from is gone or to is
// there already (another run moved first), so the caller uses what is in place.
function move(from, to) {
  for (let attempt = 1; ; attempt++) {
    try {
      renameSync(from, to);
      return true;
    } catch (error) {
      if (!existsSync(from) || existsSync(to)) return false;
      if (attempt >= 4) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500 * attempt);
    }
  }
}

// The plugin's own checkout is repaired beside it and moved in whole: npm ci (no lifecycle scripts, as on the first install)
// runs in a folder of its own with a copy of the checkout's regular tracked files, and the node_modules it makes, marked when
// whole, replaces the checkout's: the old one is moved aside into that folder, the new one in, and the old one back if that
// fails (if even that fails, the old one goes with the folder: it was not whole, or no repair would run). An install that is
// killed leaves the checkout as it was, or, killed between the two renames, with no node_modules, which the next run repairs;
// the folder it leaves is removed by removeStaleTemps. Two installs that ever overlap (a laptop that slept through the lock's
// time) give one whole install, never a mix.
function installOwn(home, whole) {
  const deps = `${home}.deps-${randomUUID()}`;
  const old = join(deps, "node_modules-old");
  const modules = join(home, "node_modules");
  const realHome = realpathSync(home);
  try {
    // An entry is "<mode> <object> <stage>\t<name>". Links and submodules are not copied; a name git would never write
    // (absolute, or leading out of the folder), or a file reached through a link that leaves the checkout, stops the repair
    // rather than writing outside the folder or reading outside the checkout.
    for (const entry of git(home, ["ls-files", "-s", "-z"]).split("\0").filter(Boolean)) {
      const name = entry.slice(entry.indexOf("\t") + 1);
      if (!/^100(644|755) /.test(entry)) continue;
      const from = join(home, name);
      const to = resolve(deps, name);
      if (isAbsolute(name) || !to.startsWith(deps + sep) || !realpathSync(from).startsWith(realHome + sep)) throw new Error(`proof-lab: a tracked file name leads outside the checkout: ${JSON.stringify(name)}`);
      mkdirSync(dirname(to), { recursive: true });
      copyFileSync(from, to);
    }
    execFileSync("npm", ["ci", "--ignore-scripts"], { cwd: deps, stdio: "inherit", shell: sh, timeout: STEP_TIMEOUT_MS });
    markInstalled(deps);
    if (whole()) return; // another run put a whole install in place meanwhile
    const aside = existsSync(modules) && move(modules, old);
    try {
      move(join(deps, "node_modules"), modules);
    } catch (error) {
      if (aside) move(old, modules);
      throw error;
    }
  } finally {
    // A folder that cannot be removed now (a virus scanner) is removed by a later run; it never fails a finished repair.
    try {
      rmSync(deps, { recursive: true, force: true, maxRetries: 4 });
    } catch {}
  }
}

function main(argv) {
  const runMode = argv[0] === "--run";
  const checkOnly = argv.includes("--check-only");
  try {
    const pinText = readFileSync(PIN_FILE, "utf8");
    // Root on a checkout a normal user can change: warned before anything runs from it (a checkout still to be fetched is
    // judged by the folders above it), not refused, and the browser step does not run from it. Asked again after each step
    // that changes the checkout; the same warning is printed once.
    let warned = "";
    const rootRisk = at => {
      const risk = checkOnly ? "" : machine.rootRisk({ home: at });
      if (risk && risk !== warned) console.error(`warning: ${(warned = risk)}`);
      return risk;
    };
    // Before check(): it runs git in the checkout. A named checkout that is not there is refused by check(), not warned.
    const planned = preflight(process.env, pinText);
    if (!process.env.PROOF_LAB_HOME || existsSync(planned.home)) rootRisk(planned.home);
    if (!process.env.PROOF_LAB_HOME && !checkOnly && !existsSync(planned.home)) provision(process.env, planned.pin, planned.home);
    const { home, pin, receipts } = check(process.env, pinText);
    // The plugin's own checkout is rebuilt when its dependencies are gone; a checkout the user named is never touched on --run.
    const ownCheckout = !process.env.PROOF_LAB_HOME;
    rootRisk(home);
    // Receipts sent elsewhere, into a folder that a user with fewer rights can change: that user then decides, with a link,
    // where this run writes its receipt files. Warned like the checkout.
    if (!checkOnly && process.env.PROOF_LAB_RECEIPTS && machine.othersCanChange(resolve(home, receipts))) console.error(`warning: PROOF_LAB_RECEIPTS names ${receipts}, which a user with fewer rights than this run can change, so a link there can send this run's receipt files elsewhere. Point it at a folder only this run's user can change.`);
    const whole = () => existsSync(join(home, "node_modules", DEPS_DONE));
    // The lock saves a second download while one repair runs; installOwn is whole on its own if two ever overlap. Folders a
    // killed run left are removed by any later run, also one that finds the checkout whole (a running repair's folder is young:
    // each of its steps is shorter than the age).
    if (ownCheckout && !checkOnly) removeStaleTemps(home);
    if (ownCheckout && !checkOnly && !whole()) withInstallLock(home, () => { if (!whole()) installOwn(home, whole); });
    // The downloaded browser is checked against its pinned digest before anything starts it.
    const browserStep = () => {
      if (checkOnly || rootRisk(home)) return;
      const cli = join(home, "node_modules", "playwright", "cli.js");
      const data = dataFolder(process.env);
      const record = isAbsolute(data) ? join(data, "browsers-checked.json") : null;
      const { othersCanChange } = machine;
      if (existsSync(cli)) verifyBrowsers({ cli, pins: JSON.parse(readFileSync(BROWSER_PINS, "utf8")).digests, record: record && !othersCanChange(record) ? record : null, refuse, othersCanChange });
      machine.ensureBrowser({ home, own: ownCheckout, refuse, timeoutMs: STEP_TIMEOUT_MS });
    };
    if (runMode) {
      if (!existsSync(join(home, "node_modules"))) refuse(`${home} has no node_modules: run node setup.mjs once (without --run) to install its dependencies`);
      browserStep();
      const child = spawnSync(process.execPath, [join(home, "src", "run-spec.js"), ...argv.slice(1)], { cwd: home, stdio: "inherit" });
      return child.status ?? 2;
    }
    if (!checkOnly && !ownCheckout) installDependencies(home);
    browserStep();
    console.log(`ready: proof-lab ${pin} at ${home}; receipts go to ${receipts}`);
    return 0;
  } catch (error) {
    console.error(`setup refused: ${error instanceof Refused ? error.message : `setup failed: ${error.message}`}`);
    return 2;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = main(process.argv.slice(2));
