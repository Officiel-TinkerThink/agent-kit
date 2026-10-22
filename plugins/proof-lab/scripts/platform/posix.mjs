// What the POSIX systems share (Linux, macOS, the BSDs): user ids, and the rule that root runs only files that root alone
// can change. A file a normal user can change, run as root, gives that user root.
import { lstatSync, readdirSync, readlinkSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";

export const isRoot = () => process.getuid?.() === 0;

const present = path => {
  try {
    lstatSync(path);
    return true;
  } catch {
    return false;
  }
};

// True when root owns the path and everything under it and none of it can be changed by group or others. `skip` names
// entries of the top folder that are left out. A link is refused, unless `within` is given and the link points inside that
// folder; what it points at is then checked where it lies in the tree.
function rootOwnsTree(path, skip = [], within = null) {
  const info = lstatSync(path);
  if (info.isSymbolicLink()) {
    const rel = within === null ? ".." : relative(within, resolve(dirname(path), readlinkSync(path)));
    return info.uid === 0 && !rel.startsWith("..") && !isAbsolute(rel);
  }
  if (info.uid !== 0 || (info.mode & 0o022) !== 0) return false;
  return !info.isDirectory() || readdirSync(path).filter(name => !skip.includes(name)).every(name => rootOwnsTree(join(path, name), [], within));
}

const above = path => {
  const all = [];
  for (let dir = dirname(path); ; dir = dirname(dir)) {
    all.push(dir);
    if (dirname(dir) === dir) return all;
  }
};

// True when nobody but root can swap `path` for another one between the check and the use: every folder above it, both as
// written and with its links resolved, is root's and closed to group and others, and every link on the way is root's (a
// link can be replaced only by whoever can change the folder it is in, which is checked too; on macOS /var is such a link).
// Folders not made yet are left out: root makes them, under a folder that passed.
function rootOwnsAncestors(path) {
  const real = realpathSync(above(path).find(present));
  return [...above(path), real, ...above(real)].every(dir => {
    let info;
    try {
      info = lstatSync(dir);
    } catch (error) {
      if (error.code === "ENOENT") return true;
      throw error;
    }
    return info.uid === 0 && (info.isSymbolicLink() || (info.mode & 0o022) === 0);
  });
}

// The files root would run or write in a checkout: the checkout with its .git (git reads its config) and its receipts (a
// link there would send root's writes elsewhere), every folder above it, and all of node_modules. node_modules/.bin holds
// links that nothing here runs. A checkout not fetched yet, or a node_modules not installed yet, is made by root itself, so
// only what exists counts. Asked afresh each time: setup asks before it fetches or repairs and the browser step after.
export function trustedTree(home) {
  try {
    if (!present(home)) return rootOwnsAncestors(home);
    const modules = join(home, "node_modules");
    return rootOwnsAncestors(home) && rootOwnsTree(home, ["node_modules"]) && (!present(modules) || rootOwnsTree(modules, [".bin"]));
  } catch {
    return false;
  }
}

// The warning for a run as root on a checkout that a normal user can change, or "" when there is nothing to warn about.
// It warns and does not refuse: a container that runs as root on a mounted project folder is a normal way to use this.
export function rootRisk(ctx, deps = { isRoot, trustedTree }) {
  if (!deps.isRoot() || deps.trustedTree(ctx.home)) return "";
  return `running as root on ${ctx.home}, which a normal user can change (root does not own all of it, or a folder above it): npm ci and the spec run as root from it, and the browser step is skipped (no check of the downloaded browser, no system libraries). Run proof-lab as the user who owns that checkout, or point it at a checkout that only root can change.`;
}

// True when this run is root and a normal user can change `path` or a folder above it: root must then not start a program
// from it, nor trust what it reads there. Links inside `path` are allowed when they point inside it (a macOS app bundle is
// made of them). A path not made yet counts by the folders above it.
export function othersCanChange(path, deps = { isRoot }) {
  if (!deps.isRoot()) return false;
  try {
    return !(rootOwnsAncestors(path) && (!present(path) || rootOwnsTree(path, [], path)));
  } catch {
    return true;
  }
}
