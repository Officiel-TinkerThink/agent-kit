"""The proof-lab plugin's install lock (owner token, gone owners, put-back), its root warning and its browser digest check."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PINS = ROOT / "plugins" / "proof-lab" / "browsers.sha256.json"
failed = 0


def check(name, cond, extra=""):
    global failed
    if cond:
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


p = subprocess.run(["node", str(ROOT / "tests" / "proof-lab" / "lock_browser_check.mjs")], capture_output=True, text=True, encoding="utf-8", timeout=120)
lines = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
check("the lock and browser checks ran", p.returncode == 0 and len(lines) >= 25, f"exit {p.returncode} err {p.stderr!r}")
for item in lines:
    check(item["name"], item["ok"], item["detail"])

# The pinned table: one SHA-256 per archive, and every build (Linux x64 and arm64, macOS x64 and arm64, Windows x64)
# has its Chromium, its headless shell and its ffmpeg.
table = json.loads(PINS.read_text(encoding="utf-8"))
digests = table.get("digests", {})
check("browsers.sha256.json: every digest is a SHA-256", digests and all(len(d) == 64 and all(c in "0123456789abcdef" for c in d) for d in digests.values()), str(digests)[:200])
for build in ("linux64", "linux-arm64", "mac-x64", "mac-arm64", "win64"):
    check(f"browsers.sha256.json: the {build} build has Chromium and its headless shell", sum(1 for k in digests if f"/{build}/" in k) == 2, [k for k in digests if build in k])
check("browsers.sha256.json: an ffmpeg for each build", sum(1 for k in digests if k.startswith("builds/ffmpeg/")) == 5, [k for k in digests if "ffmpeg" in k])

sys.exit(1 if failed else 0)
