// Run by test_platform_adapters.py: prints one JSON line per check, {"name": ..., "ok": true|false, "detail": ...}.
import { spawnSync } from "node:child_process";
import { forThisMachine } from "../../plugins/proof-lab/scripts/platform/index.mjs";
import { ensureBrowser, shQuote } from "../../plugins/proof-lab/scripts/platform/linux.mjs";

const out = (name, ok, detail = "") => console.log(JSON.stringify({ name, ok: Boolean(ok), detail: String(detail) }));

for (const [platform, name, shell] of [["linux", "linux", false], ["win32", "win32", true], ["darwin", "darwin", false], ["freebsd", "generic", false], ["aix", "generic", false]]) {
  const adapter = forThisMachine(platform);
  out(`${platform}: the adapter is ${name}, npm ${shell ? "needs" : "does not need"} a shell`, adapter.name === name && adapter.npmNeedsShell === shell, JSON.stringify(adapter));
}
out("this machine gets an adapter", typeof forThisMachine().ensureBrowser === "function");

// The Linux adapter with every machine call replaced. Every call is recorded in order.
function scenario({ cliExists = true, startsAfter = [false, true], root = false, installThrows = false, own = true, trusted = true }) {
  const calls = [];
  let n = 0;
  const deps = {
    exists: p => p.endsWith("cli.js") && cliExists,
    isRoot: () => root,
    trustedTree: () => { calls.push("trustedTree"); return trusted; },
    starts: () => { calls.push("starts"); return startsAfter[Math.min(n++, startsAfter.length - 1)]; },
    installDeps: () => { calls.push("installDeps"); if (installThrows) throw new Error("apt failed"); },
    pause: () => calls.push("pause"),
  };
  let refused = null;
  const log = console.error;
  console.error = () => {};
  try {
    ensureBrowser({ home: "/h", own, refuse: m => { refused = m; throw new Error("refused"); }, timeoutMs: 1 }, deps);
  } catch (e) {
    if (e.message !== "refused") throw e;
  } finally {
    console.error = log;
  }
  return { calls, refused };
}
const pauses = r => r.calls.filter(c => c === "pause").length;

let r = scenario({ cliExists: false });
out("linux: a checkout without Playwright is left alone", r.calls.length === 0 && r.refused === null, JSON.stringify(r));
r = scenario({ startsAfter: [true] });
out("linux: a normal user whose browser starts: one probe, nothing else", r.refused === null && r.calls.join() === "starts", JSON.stringify(r));
r = scenario({ startsAfter: [true], own: false });
out("linux: a normal user's own checkout is probed the same way", r.refused === null && r.calls.join() === "starts", JSON.stringify(r));
r = scenario({ startsAfter: [false] });
out("linux: a normal user whose browser cannot start: refused with sudo and the exact command, nothing installed", r.refused && r.refused.includes("sudo node '") && r.refused.includes("install-deps chromium") && !r.calls.includes("installDeps"), JSON.stringify(r));
r = scenario({ root: true, startsAfter: [false, true] });
out("linux: root on its own root-owned checkout installs the libraries, then the browser starts", r.refused === null && r.calls.join() === "trustedTree,starts,installDeps,starts", JSON.stringify(r));
r = scenario({ root: true, startsAfter: [false, false], installThrows: true });
out("linux: root, install fails: waits about two minutes in all, then refuses without sudo", r.refused && !r.refused.includes("sudo") && r.refused.includes("install-deps chromium") && pauses(r) === 11, JSON.stringify(r));
r = scenario({ root: true, startsAfter: [false, false, false, true] });
out("linux: root, another run finishes the install meanwhile: no refusal", r.refused === null && pauses(r) === 2 && r.calls.at(-1) === "starts", JSON.stringify(r));
r = scenario({ root: true, trusted: false, startsAfter: [false] });
out("linux: root on a checkout root does not own: nothing runs, nothing installed, no instruction to run it", r.refused === null && r.calls.join() === "trustedTree", JSON.stringify(r));
r = scenario({ root: true, own: false, startsAfter: [false] });
out("linux: root on a checkout the user named: nothing runs, nothing installed", r.refused === null && r.calls.join() === "" && !r.calls.includes("starts"), JSON.stringify(r));

// shQuote: the printed path must reach the shell exactly as it is, whatever it holds.
out("shQuote: a plain path is single-quoted", shQuote("/a/b") === "'/a/b'", shQuote("/a/b"));
out("shQuote: an apostrophe becomes '\''", shQuote("o'brien") === "'o'\\''brien'", shQuote("o'brien"));
const samples = ["/home/o'brien/pl", "a b", "$(echo x)", "`echo x`", 'a"b', "it's $HOME; ls", "a\b", "''", "x'"];
const probe = spawnSync("sh", ["-c", "true"]);
if (probe.error) {
  out("shQuote: round trip through sh needs a sh on this machine (Git Bash on Windows)", false, "no sh found: the quoting is not verified");
} else {
  for (const sample of samples) {
    const got = spawnSync("sh", [], { input: `printf %s ${shQuote(sample)}
`, encoding: "utf8" }).stdout; // by stdin: no argument quoting between node and sh
    out(`shQuote: ${JSON.stringify(sample)} reaches the shell unchanged`, got === sample, JSON.stringify(got));
  }
}
for (const platform of ["win32", "darwin", "freebsd"]) {
  let touched = false;
  forThisMachine(platform).ensureBrowser({ home: "/h", own: true, refuse: () => { touched = true; }, timeoutMs: 1 });
  out(`${platform}: the browser step prepares nothing`, !touched);
}
