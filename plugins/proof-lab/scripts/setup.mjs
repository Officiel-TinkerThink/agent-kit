#!/usr/bin/env node
// Checks that the proof-lab checkout is the one this plugin is pinned to, then installs its dependencies (npm ci).
// The checkout is PROOF_LAB_HOME when set. When it is not set, the plugin keeps its own checkout under ~/.proof-lab/checkouts/<pin>
// and fetches it from the proof-lab repository on first use (by commit hash, so git verifies what arrives).
// Exit 0: ready. Exit 2: refused, with the reason on stderr. --check-only checks and does not install.
// --run <args>: checks the same way, then runs src/run-spec.js with <args> and returns its exit code. Every proof run goes
// through this, so a run never starts on a checkout that does not match the pin.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PIN_FILE = join(PLUGIN, "proof-lab.pin");
const MIN_NODE = 24;
// The repository the pin is fetched from. PROOF_LAB_REPO replaces it (tests); the pin check holds for any source.
const DEFAULT_REPO = "https://github.com/Officiel-TinkerThink/proof-lab.git";
const sh = process.platform === "win32";
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

// Fetches the pinned commit into a temporary folder, installs dependencies and the browser there, then renames it into place,
// so a failed or interrupted install never leaves a half-made checkout at the final path.
export function provision(env, pin, home) {
  const repo = env.PROOF_LAB_REPO ?? DEFAULT_REPO;
  const tmp = `${home}.tmp-${process.pid}`;
  mkdirSync(dirname(home), { recursive: true });
  rmSync(tmp, { recursive: true, force: true });
  mkdirSync(tmp);
  try {
    const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, stdio: ["ignore", process.stderr, process.stderr], shell: sh && cmd === "npm" });
    console.error(`setting up proof-lab ${pin} in ${home} (first use only)`);
    run("git", ["init", "-q"], tmp);
    run("git", ["remote", "add", "origin", repo], tmp);
    run("git", ["fetch", "-q", "--depth", "1", "origin", pin], tmp);
    run("git", ["-c", "advice.detachedHead=false", "checkout", "-q", "--detach", pin], tmp);
    if (git(tmp, ["rev-parse", "HEAD"]).trim() !== pin) refuse(`the fetched commit is not ${pin}`);
    run("npm", ["ci", "--ignore-scripts"], tmp);
    const playwright = join(tmp, "node_modules", "playwright", "cli.js");
    if (existsSync(playwright)) run(process.execPath, [playwright, "install", "chromium"], tmp);
    try {
      renameSync(tmp, home);
    } catch (error) {
      if (!existsSync(home)) throw error; // another run finished first: use its checkout
    }
  } catch (error) {
    if (error instanceof Refused) throw error;
    refuse(`could not set up proof-lab in ${home} (${firstLine(error.message)}): check the network and that ${repo} is reachable, or set PROOF_LAB_HOME to a checkout at the pin`);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

// Every check the plugin makes before it trusts a checkout. Throws Refused with the reason.
export function check(env, pinText) {
  const major = Number(process.versions.node.split(".")[0]);
  if (major < MIN_NODE) refuse(`Node ${MIN_NODE} or later is required; this is ${process.versions.node}`);
  const pin = readPin(pinText);
  const home = env.PROOF_LAB_HOME || managedHome(env, pin);
  if (!isAbsolute(home)) refuse("PROOF_LAB_HOME must be an absolute path");
  if (!existsSync(home) || proofLabName(home) !== "proof-lab") refuse(`${home} is not a proof-lab checkout (no package.json named proof-lab)${env.PROOF_LAB_HOME ? "" : ": run node setup.mjs once (without --check-only) to fetch it"}`);
  const head = git(home, ["rev-parse", "HEAD"]).trim();
  if (head !== pin) refuse(`the checkout is at ${head}, this plugin is pinned to ${pin}: check out ${pin} in ${home}, or change the pin in a pull request`);
  if (git(home, ["status", "--porcelain"]).trim() !== "") refuse(`${home} has uncommitted changes: commit or stash them first, so the receipts match one revision`);
  return { home, pin, receipts: env.PROOF_LAB_RECEIPTS ?? join(home, "receipts") };
}

function main(argv) {
  const runMode = argv[0] === "--run";
  const checkOnly = argv.includes("--check-only");
  try {
    const pinText = readFileSync(PIN_FILE, "utf8");
    if (!process.env.PROOF_LAB_HOME && !checkOnly) {
      const pin = readPin(pinText);
      const home = managedHome(process.env, pin);
      if (!existsSync(home)) provision(process.env, pin, home);
    }
    const { home, pin, receipts } = check(process.env, pinText);
    if (runMode) {
      if (!existsSync(join(home, "node_modules"))) refuse(`${home} has no node_modules: run node setup.mjs once (without --run) to install its dependencies`);
      const child = spawnSync(process.execPath, [join(home, "src", "run-spec.js"), ...argv.slice(1)], { cwd: home, stdio: "inherit" });
      return child.status ?? 2;
    }
    if (!checkOnly && process.env.PROOF_LAB_HOME) execFileSync("npm", ["ci"], { cwd: home, stdio: "inherit", shell: sh });
    console.log(`ready: proof-lab ${pin} at ${home}; receipts go to ${receipts}`);
    return 0;
  } catch (error) {
    console.error(`setup refused: ${error instanceof Refused ? error.message : `setup failed: ${error.message}`}`);
    return 2;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = main(process.argv.slice(2));
