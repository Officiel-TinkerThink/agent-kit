"""The proof-lab plugin's files agree with each other and with the marketplace."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "proof-lab"
failed = 0


def check(name, cond, extra=""):
    global failed
    if cond:
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


def text(path):
    return path.read_text(encoding="utf-8")


manifest = json.loads(text(PLUGIN / ".claude-plugin" / "plugin.json"))
check("manifest names the plugin", manifest.get("name") == "proof-lab")

market = json.loads(text(ROOT / ".claude-plugin" / "marketplace.json"))
entries = [p for p in market["plugins"] if p["name"] == "proof-lab"]
check("marketplace has one proof-lab entry", len(entries) == 1)
if entries:
    check("marketplace source is the plugin folder", entries[0]["source"] == "./plugins/proof-lab")
    check("marketplace version matches the manifest", entries[0]["version"] == manifest["version"])

skill = text(PLUGIN / "skills" / "proof-lab" / "SKILL.md")
front = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
check("skill has frontmatter", front is not None)
check("skill has a description", front is not None and re.search(r"^description:", front.group(1), re.M) is not None)
check("skill is named proof-lab", front is not None and re.search(r"^name: proof-lab$", front.group(1), re.M) is not None)

agent = text(PLUGIN / "agents" / "proof-runner.md")
check("agent is named proof-runner", re.search(r"^name: proof-runner$", agent, re.M) is not None)
check("agent runs on claude-haiku-5-5", re.search(r"^model: claude-haiku-5-5$", agent, re.M) is not None)
check("skill runs proofs through setup.mjs --run", "scripts/setup.mjs\" --run" in skill and "run-spec.js\" --spec" not in skill)
check("agent runs proofs through setup.mjs --run", "scripts/setup.mjs\" --run" in agent and "run-spec.js" not in agent)

hooks = json.loads(text(PLUGIN / "hooks" / "hooks.json"))
pre = hooks["hooks"]["PreToolUse"]
check("the guard is a PreToolUse hook on Bash", len(pre) == 1 and pre[0]["matcher"] == "Bash")
command = pre[0]["hooks"][0]["command"]
check("the hook runs the router on the guard through CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" in command and "${CLAUDE_PLUGIN_ROOT}/scripts/guard-proof-key" in command)
check("the router exists", (PLUGIN / "scripts" / "run.sh").is_file())
check("the guard has a POSIX version and a PowerShell twin", (PLUGIN / "scripts" / "guard-proof-key.sh").is_file() and (PLUGIN / "scripts" / "guard-proof-key.ps1").is_file())
check("setup script exists", (PLUGIN / "scripts" / "setup.mjs").is_file())

pin_lines = [line for line in text(PLUGIN / "proof-lab.pin").splitlines() if line.strip() and not line.startswith("#")]
check("pin file holds one full commit hash", len(pin_lines) == 1 and re.fullmatch(r"[0-9a-f]{40}", pin_lines[0]) is not None)

sys.exit(1 if failed else 0)
