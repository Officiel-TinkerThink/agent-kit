// What the POSIX systems share (Linux, macOS, the BSDs): user ids, and the rule that root runs only files that root alone
// can change. A file a normal user can change, run as root, gives that user root.
import { lstatSync, readdirSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";

export const isRoot = () => process.getuid?.() === 0;

// True when root owns the path and everything under it, none of it can be changed by group or others, and nothing is a link.
// `skip` names entries of the top folder that are left out.
function rootOwnsTree(path, skip = []) {
  const info = lstatSync(path);
  if (info.isSymbolicLink() || info.uid !== 0 || (info.mode & 0o022) !== 0) return false;
  return !info.isDirectory() || readdirSync(path).filter(name => !skip.includes(name)).every(name => rootOwnsTree(join(path, name)));
}

// True when every folder above `path`, up to /, is owned by root and cannot be changed by group or others, so nobody can
// swap the checkout for another one between the check and the use.
function rootOwnsAncestors(path) {
  for (let dir = dirname(path); ; dir = dirname(dir)) {
    const info = lstatSync(dir);
    if (info.uid !== 0 || (info.mode & 0o022) !== 0) return false;
    if (dirname(dir) === dir) return true;
  }
}

// The files root would run from a checkout: the checkout with its .git (git reads its config), every folder above it, and all
// of node_modules. node_modules/.bin holds links that nothing here runs; receipts are written, not run. The path must contain
// no link. The answer is kept per folder: setup asks before its repair and the browser step asks again after it.
const trusted = new Map();
export function trustedTree(home) {
  if (!trusted.has(home)) {
    let answer = false;
    try {
      answer = realpathSync(home) === home && rootOwnsAncestors(home) && rootOwnsTree(home, ["node_modules", "receipts"]) && rootOwnsTree(join(home, "node_modules"), [".bin"]);
    } catch {}
    trusted.set(home, answer);
  }
  return trusted.get(home);
}

// The warning for a run as root on a checkout that a normal user can change, or "" when there is nothing to warn about.
// It warns and does not refuse: a container that runs as root on a mounted project folder is a normal way to use this.
export function rootRisk(ctx, deps = { isRoot, trustedTree }) {
  if (!deps.isRoot() || deps.trustedTree(ctx.home)) return "";
  return `running as root on ${ctx.home}, which root does not own or which a normal user can change: npm ci and the spec run as root from it, and the browser step is skipped (no check of the downloaded browser, no system libraries). Run proof-lab as the user who owns that checkout, or point it at a checkout that only root can change.`;
}
