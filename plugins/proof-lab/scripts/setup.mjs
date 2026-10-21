#!/usr/bin/env node
// Checks that the proof-lab checkout is the one this plugin is pinned to, then installs its dependencies (npm ci).
// The checkout is PROOF_LAB_HOME when set. When it is not set, the plugin keeps its own checkout under ~/.proof-lab/checkouts/<pin>
// and fetches it from the proof-lab repository on first use (by commit hash, so git verifies what arrives).
// Exit 0: ready. Exit 2: refused, with the reason on stderr. --check-only checks and does not install.
// --run <args>: checks the same way, then runs src/run-spec.js with <args> and returns its exit code. Every proof run goes
// through this, so a run never starts on a checkout that does not match the pin.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PIN_FILE = join(PLUGIN, "proof-lab.pin");
const MIN_NODE = 24;
// The repository the pin is fetched from. PROOF_LAB_REPO replaces it (tests); the pin check holds for any source.
const DEFAULT_REPO = "https://github.com/Officiel-TinkerThink/proof-lab.git";
const sh = process.platform === "win32";
const STEP_TIMEOUT_MS = 10 * 60 * 1000; // one git or npm step; a stalled network ends in a refusal, not a hang
const BROWSER_TIMEOUT_MS = 30 * 60 * 1000; // the Chromium download is the one large step
const DEPS_DONE = ".proof-lab-installed"; // written inside node_modules after a whole install; a killed install lacks it
const STALE_TMP_MS = 60 * 60 * 1000; // an install folder this old belongs to a run that was killed
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

// Where the plugin keeps its own checkout when PROOF_LAB_HOME is not set: one folder per pin, so a new pin is a new checkout.
export function managedHome(env, pin) {
  return join(env.PROOF_LAB_DATA ?? join(homedir(), ".proof-lab"), "checkouts", pin);
}

// The repository address without any user:password part, for messages.
const shownRepo = repo => String(repo).replace(/^([a-z][a-z0-9+.-]*:\/\/)[^/]*@/i, "$1");

// Removes install folders that a killed run left beside the final path (the pid in the name is not reused by the next run).
function removeStaleTemps(home) {
  const parent = dirname(home);
  const prefix = `${basename(home)}.tmp-`;
  for (const name of readdirSync(parent)) {
    if (!name.startsWith(prefix)) continue;
    try {
      if (Date.now() - statSync(join(parent, name)).mtimeMs > STALE_TMP_MS) rmSync(join(parent, name), { recursive: true, force: true });
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

// One repair at a time: the lock is a folder (mkdir is atomic). A run that finds it held waits for it to go, then looks
// again, because the holder has usually finished the install. A lock older than a whole install belongs to a killed run.
function withInstallLock(home, work) {
  const lock = `${home}.lock`;
  const pause = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
  for (;;) {
    try {
      mkdirSync(lock);
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      try {
        if (Date.now() - statSync(lock).mtimeMs > STEP_TIMEOUT_MS + 60_000) rmSync(lock, { recursive: true, force: true });
      } catch {}
      pause(2000);
    }
    }
  try {
    work();
  } finally {
    rmSync(lock, { recursive: true, force: true });
  }
}

// The plugin's own checkout is installed the way the first install is (no lifecycle scripts) and marked when whole;
// npm ci empties node_modules first, so an install that was killed has no marker and is redone on the next call.
function installDependencies(home, own) {
  execFileSync("npm", own ? ["ci", "--ignore-scripts"] : ["ci"], { cwd: home, stdio: "inherit", shell: sh, timeout: STEP_TIMEOUT_MS });
  if (own) markInstalled(home);
}

function main(argv) {
  const runMode = argv[0] === "--run";
  const checkOnly = argv.includes("--check-only");
  try {
    const pinText = readFileSync(PIN_FILE, "utf8");
    if (!process.env.PROOF_LAB_HOME && !checkOnly) {
      const planned = preflight(process.env, pinText);
      if (!existsSync(planned.home)) provision(process.env, planned.pin, planned.home);
    }
    const { home, pin, receipts } = check(process.env, pinText);
    // The plugin's own checkout is rebuilt when its dependencies are gone; a checkout the user named is never touched on --run.
    const ownCheckout = !process.env.PROOF_LAB_HOME;
    const whole = () => existsSync(join(home, "node_modules", DEPS_DONE));
    if (ownCheckout && !checkOnly && !whole()) withInstallLock(home, () => { if (!whole()) installDependencies(home, true); });
    if (runMode) {
      if (!existsSync(join(home, "node_modules"))) refuse(`${home} has no node_modules: run node setup.mjs once (without --run) to install its dependencies`);
      const child = spawnSync(process.execPath, [join(home, "src", "run-spec.js"), ...argv.slice(1)], { cwd: home, stdio: "inherit" });
      return child.status ?? 2;
    }
    if (!checkOnly && !ownCheckout) installDependencies(home, false);
    console.log(`ready: proof-lab ${pin} at ${home}; receipts go to ${receipts}`);
    return 0;
  } catch (error) {
    console.error(`setup refused: ${error instanceof Refused ? error.message : `setup failed: ${error.message}`}`);
    return 2;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = main(process.argv.slice(2));
