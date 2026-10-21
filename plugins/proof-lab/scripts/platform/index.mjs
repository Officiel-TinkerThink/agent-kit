// The machine adapter. setup.mjs asks for "the adapter for this machine" and never looks at the operating system itself:
// each adapter in this folder answers the same questions for one operating system, so adding a system means adding a file.
//   name            the adapter's name (for messages and tests)
//   npmNeedsShell   whether npm must be started through a shell (npm is a .cmd file on Windows)
//   rootRisk        a warning when this run has more rights than the people who can change the checkout (root on a tree a
//                   normal user can change), or "". With a warning, setup skips the browser step.
//     ctx: { home, own }
//   ensureBrowser   makes sure Chromium can start; throws through ctx.refuse when it cannot
//     ctx: { home, own, refuse, timeoutMs }  home: the proof-lab folder; own: the plugin's own checkout; timeoutMs: one step
import darwin from "./darwin.mjs";
import linux from "./linux.mjs";
import { rootRisk } from "./posix.mjs";
import win32 from "./win32.mjs";

// Systems with nothing to prepare: npm starts directly and the downloaded browser starts as it is. They are POSIX systems
// (the BSDs, AIX, Solaris), so root is root there too.
const generic = { name: "generic", npmNeedsShell: false, rootRisk, ensureBrowser() {} };
const ADAPTERS = { darwin, linux, win32 };

export function forThisMachine(platform = process.platform) {
  return ADAPTERS[platform] ?? generic;
}
