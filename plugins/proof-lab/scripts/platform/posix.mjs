// What the POSIX systems share (Linux, macOS, the BSDs): user ids, and the rule that root runs only files that root alone
// can change. A file a normal user can change, run as root, gives that user root.
import { lstatSync, readdirSync, readlinkSync } from "node:fs";
import { dirname, isAbsolute, join, relative } from "node:path";

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
// entries of the top folder that are left out. A link is refused, unless `within` is given and the link leads, as the
// system follows it, inside that folder through folders only root can change; what it leads to is then checked where it
// lies in the tree.
function rootOwnsTree(path, skip = [], within = null) {
  const info = lstatSync(path);
  if (info.isSymbolicLink()) {
    if (within === null) return false;
    const folders = [];
    const rel = relative(walk(within, []), walk(path, folders));
    return !rel.startsWith("..") && !isAbsolute(rel) && folders.every(closed);
  }
  if (info.uid !== 0 || (info.mode & 0o022) !== 0) return false;
  return !info.isDirectory() || readdirSync(path).filter(name => !skip.includes(name)).every(name => rootOwnsTree(join(path, name), [], within));
}

const MAX_LINKS = 40; // the system gives up on longer chains too

// Where `path` leads, with every real folder the system passes through on the way pushed onto `folders`: links are followed
// the way the system follows them, so the folder that holds each link on the way, and every folder its target leads
// through, are in the list. A relative link target is walked from the link's folder, part by part like the rest (so a ".."
// after a link goes up from where that link leads, as the system does). A part not made yet is followed as written.
function walk(path, folders, links = { n: 0 }, from = "/") {
  let at = isAbsolute(path) ? "/" : from;
  for (const name of path.split("/").filter(Boolean)) {
    if (name === ".") continue;
    if (name === "..") {
      at = dirname(at); // `at` is a real folder, so this is its real parent
      continue;
    }
    folders.push(at);
    const next = join(at, name);
    let info = null;
    try {
      info = lstatSync(next);
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    if (info?.isSymbolicLink()) {
      if (++links.n > MAX_LINKS) throw new Error(`too many links on the way to ${path}`);
      at = walk(readlinkSync(next), folders, links, at);
    } else {
      at = next;
    }
  }
  return at;
}

// True when nobody but root can swap `path` for another one between the check and the use: every real folder the system
// passes through to reach it is root's and closed to group and others. A link on the way can then be replaced only by root
// (it can be replaced only by whoever can change the folder it is in; on macOS /var is such a link). Folders not made yet
// are left out: root makes them, under a folder that passed.
function rootOwnsAncestors(path) {
  const folders = [];
  folders.push(walk(dirname(path), folders));
  return folders.every(closed);
}

// True when a real folder the walk passed is root's and closed to group and others, or is not made yet.
function closed(dir) {
  let info;
  try {
    info = lstatSync(dir);
  } catch (error) {
    if (error.code === "ENOENT") return true;
    throw error;
  }
  return info.uid === 0 && (info.mode & 0o022) === 0;
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
// from it, nor trust what it reads there. `path` itself may be a link: it is judged where it really leads, with every folder
// on the way. Links inside it are allowed when they lead inside it (a macOS app bundle is made of them). A path not made yet
// counts by the folders above it. A relative path is not judged: it counts as changeable.
export function othersCanChange(path, deps = { isRoot }) {
  if (!deps.isRoot()) return false;
  if (!isAbsolute(path)) return true;
  try {
    const folders = [];
    const real = walk(path, folders);
    return !(folders.every(closed) && (!present(real) || rootOwnsTree(real, [], real)));
  } catch {
    return true;
  }
}
