// One repair at a time. The lock is a folder (mkdir is atomic) that holds owner.json: a random token, the process id and the
// host name of the run that made it. A run removes only a lock that it owns, or one whose owner is gone:
//   - gone: the process no longer runs on this host, or the lock is older than the longest repair (maxAgeMs);
//   - a gone lock is first renamed aside (a rename is atomic, so of two runs clearing it only one succeeds) and removed only
//     when what was moved is the lock that was judged gone; a lock that another run made in the meantime is put back.
// A run that finds a live lock waits for it to go, then looks again: the holder has usually finished the install.
import { randomUUID } from "node:crypto";
import { mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { hostname } from "node:os";
import { basename, dirname, join } from "node:path";

const OWNER = "owner.json";
const WAIT_MS = 2000;
const pause = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

function readOwner(lock) {
  try {
    return JSON.parse(readFileSync(join(lock, OWNER), "utf8"));
  } catch {
    return null; // just made and not written yet, or written by a run that was killed in between
  }
}

// What identifies one lock folder: its file id and change time (a new folder at the same path has others) and its owner.
function identify(lock) {
  const info = statSync(lock);
  return { id: `${info.ino}:${info.mtimeMs}`, owner: readOwner(lock), ageMs: Date.now() - info.mtimeMs };
}

function running(pid) {
  try {
    process.kill(pid, 0); // signal 0 sends nothing: it only asks whether the process exists
    return true;
  } catch (error) {
    return error.code === "EPERM"; // it exists, but belongs to another user
  }
}

function gone(seen, maxAgeMs) {
  const owner = seen.owner;
  if (owner && owner.host === hostname() && Number.isInteger(owner.pid) && (owner.pid === process.pid || !running(owner.pid))) return true;
  return seen.ageMs > maxAgeMs;
}

function clear(lock, seen, token) {
  const aside = `${lock}.stale-${token}`;
  try {
    renameSync(lock, aside);
  } catch {
    return; // another run cleared it first
  }
  let moved = null;
  try {
    moved = identify(aside);
  } catch {}
  if (moved && moved.id === seen.id && moved.owner?.token === seen.owner?.token) {
    rmSync(aside, { recursive: true, force: true });
    return;
  }
  try {
    renameSync(aside, lock); // not the lock that was judged: give it back to its owner
  } catch {
    rmSync(aside, { recursive: true, force: true }); // a newer lock is in place; this one is no longer anyone's
  }
}

// Folders that a run killed between its rename and its remove left beside the lock.
function removeAsides(lock, maxAgeMs) {
  const prefix = `${basename(lock)}.stale-`;
  for (const name of readdirSync(dirname(lock))) {
    if (!name.startsWith(prefix)) continue;
    try {
      if (Date.now() - statSync(join(dirname(lock), name)).mtimeMs > maxAgeMs) rmSync(join(dirname(lock), name), { recursive: true, force: true });
    } catch {}
  }
}

export function withInstallLock(home, maxAgeMs, work) {
  const lock = `${home}.lock`;
  const token = randomUUID();
  for (;;) {
    try {
      mkdirSync(lock);
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      let seen = null;
      try {
        seen = identify(lock);
      } catch {
        continue; // released between mkdir and stat: try again at once
      }
      if (gone(seen, maxAgeMs)) {
        clear(lock, seen, token);
        pause(200); // a rename that a virus scanner blocks for a moment is not tried again in a tight loop
      } else {
        pause(WAIT_MS);
      }
      continue;
    }
    try {
      writeFileSync(join(lock, OWNER), JSON.stringify({ token, pid: process.pid, host: hostname() }));
    } catch (error) {
      rmSync(lock, { recursive: true, force: true });
      throw error;
    }
    break;
  }
  try {
    removeAsides(lock, maxAgeMs);
    return work();
  } finally {
    // Only this run's own lock: if it was cleared as gone and another run holds the path now, that lock is left alone.
    if (readOwner(lock)?.token === token) rmSync(lock, { recursive: true, force: true });
  }
}
