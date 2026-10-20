#!/usr/bin/env node
// Checks that PROOF_LAB_HOME is the proof-lab checkout this plugin is pinned to, then installs its dependencies (npm ci).
// Exit 0: ready. Exit 2: refused, with the reason on stderr. --check-only checks and does not install.
// --run <args>: checks the same way, then runs src/run-spec.js with <args> and returns its exit code. Every proof run goes
// through this, so a run never starts on a checkout that does not match the pin.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PIN_FILE = join(PLUGIN, "proof-lab.pin");
const MIN_NODE = 24;

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

// Every check the plugin makes before it trusts a checkout. Throws Refused with the reason.
export function check(env, pinText) {
  const major = Number(process.versions.node.split(".")[0]);
  if (major < MIN_NODE) refuse(`Node ${MIN_NODE} or later is required; this is ${process.versions.node}`);
  const home = env.PROOF_LAB_HOME;
  if (!home) refuse("PROOF_LAB_HOME is not set: point it at a proof-lab checkout");
  if (!isAbsolute(home)) refuse("PROOF_LAB_HOME must be an absolute path");
  if (!existsSync(home) || proofLabName(home) !== "proof-lab") refuse(`${home} is not a proof-lab checkout (no package.json named proof-lab)`);
  const pin = readPin(pinText);
  const head = git(home, ["rev-parse", "HEAD"]).trim();
  if (head !== pin) refuse(`the checkout is at ${head}, this plugin is pinned to ${pin}: check out ${pin} in ${home}, or change the pin in a pull request`);
  if (git(home, ["status", "--porcelain"]).trim() !== "") refuse(`${home} has uncommitted changes: commit or stash them first, so the receipts match one revision`);
  return { home, pin, receipts: env.PROOF_LAB_RECEIPTS ?? join(home, "receipts") };
}

function main(argv) {
  const runMode = argv[0] === "--run";
  const checkOnly = argv.includes("--check-only");
  try {
    const { home, pin, receipts } = check(process.env, readFileSync(PIN_FILE, "utf8"));
    if (runMode) {
      const child = spawnSync(process.execPath, [join(home, "src", "run-spec.js"), ...argv.slice(1)], { cwd: home, stdio: "inherit" });
      return child.status ?? 2;
    }
    if (!checkOnly) execFileSync("npm", ["ci"], { cwd: home, stdio: "inherit", shell: process.platform === "win32" });
    console.log(`ready: proof-lab ${pin} at ${home}; receipts go to ${receipts}`);
    return 0;
  } catch (error) {
    console.error(`setup refused: ${error instanceof Refused ? error.message : `setup failed: ${error.message}`}`);
    return 2;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = main(process.argv.slice(2));
