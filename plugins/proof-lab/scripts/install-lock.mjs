// One repair at a time. The lock is a folder that holds owner.json: a random token, the process id and the host name of the
// run that made it. It is made beside the lock with its owner file already in it and renamed into place, so a lock is never
// without its owner: a rename onto a lock with a file in it fails on every system (it replaces only an empty folder, which no
// run makes; an empty lock left by an older plugin is cleared like any lock that is not kept fresh).
// While the work runs, a worker thread of this run sets the lock's time every few seconds (beatMs), also while the work blocks
// the main thread (npm ci). A thread ends with its process, however that ends. So a lock is live while its time is fresh,
// whatever its process id has become since, on any host:
//   - gone: its process no longer runs on this host (cleared at once), or its time is older than staleMs;
//   - a gone lock is first renamed aside (a rename is atomic, so of two runs clearing it only one succeeds) and removed only
//     when what was moved is the lock that was judged gone; a lock that another run made in the meantime is put back.
// A run that finds a live lock waits for it to go, then looks again: the holder has usually finished the install. The work the
// lock guards is made safe on its own when two runs ever overlap (a laptop that slept through staleMs): the lock saves work.
import { randomUUID } from "node:crypto";
import { existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { hostname } from "node:os";
import { basename, dirname, join } from "node:path";
import { Worker } from "node:worker_threads";

const OWNER = "owner.json";
const WAIT_MS = 2000;
const BEAT_MS = 5000; // how often a holder sets its lock's time
const STALE_MS = 30_000; // a lock whose time is older than this is not kept by anyone
const TELL_MS = 10_000; // a run that waits this long says what it waits for
const TRIES = 25; // renames a virus scanner blocks for a moment, 200 ms apart
const pause = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

function readOwner(lock) {
  try {
    return JSON.parse(readFileSync(join(lock, OWNER), "utf8"));
  } catch {
    return null; // just made and not written yet, or written by a run that was killed in between
  }
}

// What identifies one lock folder: its file id and change time (a new folder at the same path has others) and its owner.
export function identify(lock) {
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

// An owner on this host whose process has ended is gone at once. Any other lock is gone when its time is stale: a holder keeps
// it fresh, so a process id that another program has since been given does not keep a lock alive.
function gone(seen, staleMs) {
  const owner = seen.owner;
  if (owner && owner.host === hostname() && Number.isInteger(owner.pid) && (owner.pid === process.pid || !running(owner.pid))) return true;
  return seen.ageMs > staleMs;
}

// The thread that keeps a held lock fresh. It stops when the lock is gone or no longer this run's; a time it cannot set for a
// moment (a virus scanner) is tried again on the next beat. It reads its modules with getBuiltinModule, which works whether
// node runs the code as a script or as a module (a thread inherits node's flags, such as --input-type=module).
const KEEP_FRESH = `
const { readFileSync, utimesSync } = process.getBuiltinModule("node:fs");
const { join } = process.getBuiltinModule("node:path");
const { workerData: { lock, token, beatMs } } = process.getBuiltinModule("node:worker_threads");
const beat = setInterval(() => {
  let owner = null;
  try {
    owner = JSON.parse(readFileSync(join(lock, "owner.json"), "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") clearInterval(beat);
    return;
  }
  if (owner.token !== token) return clearInterval(beat);
  try {
    const now = new Date();
    utimesSync(lock, now, now);
  } catch {}
}, beatMs);
`;

// Starts the thread; returns the function that stops it. A thread that cannot start leaves the lock to go stale, which the
// guarded work survives (see the top of this file).
function keepFresh(lock, token, beatMs) {
  try {
    const thread = new Worker(KEEP_FRESH, { eval: true, workerData: { lock, token, beatMs } });
    thread.on("error", () => {});
    thread.unref();
    return () => void thread.terminate().catch(() => {});
  } catch {
    return () => {};
  }
}

// Exported for the tests: the put-back path needs a lock that changes between the look and the rename.
export function clear(lock, seen, token) {
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
  // Not the lock that was judged: give it back to its owner. Removed only when a newer lock holds the path (its run has lost
  // the lock either way); a put-back that keeps failing on a free path leaves it aside, for removeAsides once it is old.
  for (let tries = 0; tries < TRIES; tries++) {
    try {
      renameSync(aside, lock);
      return;
    } catch {}
    if (existsSync(lock)) {
      rmSync(aside, { recursive: true, force: true });
      return;
    }
    pause(200);
  }
}

// Folders that a run killed between its rename and its remove (or before it renamed its new lock into place) left beside the lock.
function removeAsides(lock, staleMs) {
  const prefixes = [`${basename(lock)}.stale-`, `${basename(lock)}.new-`];
  for (const name of readdirSync(dirname(lock))) {
    if (!prefixes.some(prefix => name.startsWith(prefix))) continue;
    try {
      const info = lstatSync(join(dirname(lock), name)); // a link is not followed, and not removed: no run makes one here
      if (info.isDirectory() && Date.now() - info.mtimeMs > staleMs) rmSync(join(dirname(lock), name), { recursive: true, force: true });
    } catch {}
  }
}

// staleMs and beatMs are for the tests; a run uses the defaults.
export function withInstallLock(home, work, { staleMs = STALE_MS, beatMs = BEAT_MS } = {}) {
  const lock = `${home}.lock`;
  const token = randomUUID();
  const started = Date.now();
  const made = `${lock}.new-${token}`;
  try {
    take(lock, made, token, staleMs, started);
  } catch (error) {
    rmSync(made, { recursive: true, force: true });
    throw error;
  }
  const stop = keepFresh(lock, token, beatMs);
  try {
    removeAsides(lock, staleMs);
    return work();
  } finally {
    stop();
    // Only this run's own lock: if it was cleared as gone and another run holds the path now, that lock is left alone.
    if (readOwner(lock)?.token === token) rmSync(lock, { recursive: true, force: true });
  }
}

// This run's new lock, whole and with a fresh time on every look: a run that took the lock meanwhile removes one older than
// staleMs, and once it is in place its age is counted from that time. Returns false when the time could not be set (a
// virus scanner holding the folder for a moment, or the folder removed just now): the next look tries again.
function ready(made, token) {
  if (!existsSync(join(made, OWNER))) {
    mkdirSync(made, { recursive: true });
    writeFileSync(join(made, OWNER), JSON.stringify({ token, pid: process.pid, host: hostname() }));
  }
  try {
    const now = new Date();
    utimesSync(made, now, now);
    return true;
  } catch {
    return false;
  }
}

// Renames the new lock `made` into place once the path is free, clearing a lock whose owner is gone and waiting for a live one.
function take(lock, made, token, staleMs, started) {
  let told = false;
  let blocked = 0;
  for (;;) {
    const fresh = ready(made, token);
    if (!existsSync(lock)) {
      // Taken only with a fresh time, so the lock is not judged old the moment it is in place.
      if (!fresh) {
        if (++blocked >= TRIES) throw new Error(`could not set the time of ${made}`);
        pause(200);
        continue;
      }
      try {
        renameSync(made, lock);
        return;
      } catch (error) {
        if (!existsSync(lock)) {
          // The path is still free: a virus scanner holding a file for a moment, or a folder this run cannot write to.
          if (++blocked >= TRIES) throw error;
          pause(200);
          continue;
        }
      }
    }
    blocked = 0; // counted only while the path stays free
    let seen = null;
    try {
      seen = identify(lock);
    } catch {
      continue; // released between the look and the stat: try again at once
    }
    if (gone(seen, staleMs)) {
      clear(lock, seen, token);
      pause(200); // a rename that a virus scanner blocks for a moment is not tried again in a tight loop
    } else {
      if (!told && Date.now() - started > TELL_MS) {
        const where = seen.owner?.host && seen.owner.host !== hostname() ? ` on ${seen.owner.host}` : "";
        console.error(`waiting for another proof-lab install to finish (process ${seen.owner?.pid ?? "unknown"}${where})`);
        told = true;
      }
      pause(WAIT_MS);
    }
  }
}
