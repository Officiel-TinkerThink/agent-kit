// Run by test_platform_adapters.py: prints one JSON line per check, {"name": ..., "ok": true|false, "detail": ...}.
import { forThisMachine } from "../../plugins/proof-lab/scripts/platform/index.mjs";
import { ensureBrowser } from "../../plugins/proof-lab/scripts/platform/linux.mjs";

const out = (name, ok, detail = "") => console.log(JSON.stringify({ name, ok: Boolean(ok), detail: String(detail) }));

for (const [platform, name, shell] of [["linux", "linux", false], ["win32", "win32", true], ["darwin", "darwin", false], ["freebsd", "generic", false], ["aix", "generic", false]]) {
  const adapter = forThisMachine(platform);
  out(`${platform}: the adapter is ${name}, npm ${shell ? "needs" : "does not need"} a shell`, adapter.name === name && adapter.npmNeedsShell === shell, JSON.stringify(adapter));
}
out("this machine gets an adapter", typeof forThisMachine().ensureBrowser === "function");

// The Linux adapter with every machine call replaced.
function scenario({ cliExists = true, marked = false, startsAfter = [false, true], root = false, installThrows = false, own = true }) {
  const calls = [];
  let n = 0;
  const deps = {
    exists: p => (p.endsWith("cli.js") ? cliExists : p.endsWith(".proof-lab-browser-ok") ? marked : false),
    mark: () => calls.push("mark"),
    isRoot: () => root,
    starts: () => { calls.push("starts"); return startsAfter[Math.min(n++, startsAfter.length - 1)]; },
    installDeps: () => { calls.push("installDeps"); if (installThrows) throw new Error("apt failed"); },
  };
  let refused = null;
  try {
    ensureBrowser({ home: "/h", own, refuse: m => { refused = m; throw new Error("refused"); }, timeoutMs: 1 }, deps);
  } catch (e) {
    if (e.message !== "refused") throw e;
  }
  return { calls, refused };
}

let r = scenario({ cliExists: false });
out("linux: a checkout without Playwright is left alone", r.calls.length === 0 && r.refused === null, JSON.stringify(r));
r = scenario({ marked: true });
out("linux: a marked own checkout does not start the browser again", r.calls.length === 0, JSON.stringify(r));
r = scenario({ startsAfter: [true] });
out("linux: a browser that starts is marked (own checkout)", r.refused === null && r.calls.join() === "starts,mark", JSON.stringify(r));
r = scenario({ startsAfter: [true], own: false });
out("linux: a user's own checkout is never marked", r.refused === null && r.calls.join() === "starts", JSON.stringify(r));
r = scenario({ startsAfter: [false] });
out("linux: not root and the browser cannot start: refused with sudo and the exact command", r.refused && r.refused.includes('sudo node "') && r.refused.includes("playwright") && r.refused.includes("install-deps chromium") && !r.calls.includes("installDeps"), JSON.stringify(r));
r = scenario({ root: true, startsAfter: [false, true] });
out("linux: root installs the libraries itself, then the browser starts and is marked", r.refused === null && r.calls.join() === "starts,installDeps,starts,mark", JSON.stringify(r));
r = scenario({ root: true, startsAfter: [false, false], installThrows: true });
out("linux: root, install fails: refused without sudo", r.refused && !r.refused.includes("sudo") && r.refused.includes("install-deps chromium"), JSON.stringify(r));
for (const platform of ["win32", "darwin", "freebsd"]) {
  let touched = false;
  forThisMachine(platform).ensureBrowser({ home: "/h", own: true, refuse: () => { touched = true; }, timeoutMs: 1 });
  out(`${platform}: the browser step prepares nothing`, !touched);
}
