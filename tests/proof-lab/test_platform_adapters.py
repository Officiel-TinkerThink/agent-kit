"""The machine adapters of the proof-lab plugin: the right adapter for each system, the Linux browser step with every
machine call replaced, and the design rule that no code outside scripts/platform/ looks at the operating system."""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "proof-lab" / "scripts"
failed = 0


def check(name, cond, extra=""):
    global failed
    if cond:
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


p = subprocess.run(["node", str(ROOT / "tests" / "proof-lab" / "platform_adapters_check.mjs")], capture_output=True, text=True, encoding="utf-8", timeout=60)
lines = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
check("the adapter checks ran", p.returncode == 0 and len(lines) >= 15, f"exit {p.returncode} err {p.stderr!r}")
for item in lines:
    check(item["name"], item["ok"], item["detail"])

# The design rule: the operating system is looked at in one place only.
offenders = []
for path in sorted(SCRIPTS.rglob("*.mjs")):
    rel = path.relative_to(SCRIPTS).as_posix()
    if rel.startswith("platform/"):
        continue
    text = path.read_text(encoding="utf-8")
    if re.search(r"process\.platform|os\.platform\(|\bwin32\b|\blinux\b|\bdarwin\b", text):
        offenders.append(rel)
check("no code outside scripts/platform/ names an operating system", offenders == [], str(offenders))
index = (SCRIPTS / "platform" / "index.mjs").read_text(encoding="utf-8")
check("scripts/platform/index.mjs is the only place that reads process.platform", len(re.findall(r"process\.platform", index)) == 1 and all("process.platform" not in f.read_text(encoding="utf-8") for f in (SCRIPTS / "platform").glob("*.mjs") if f.name != "index.mjs"))

sys.exit(1 if failed else 0)
