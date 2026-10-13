"""Builds the shipped plugin agents from the benchmarked prompt files, so the shipped text is exactly what was measured.

  python build_agents.py            # writes plugins/haiku-delegation/agents/browser-{explorer,operator}.md
Edit SHIP below when a new prompt version wins the benchmark.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parents[1] / "plugins" / "haiku-delegation" / "agents"
CHROME = "mcp__claude-in-chrome__"
READ = ["tabs_context_mcp", "tabs_create_mcp", "tabs_close_mcp", "navigate", "read_page", "get_page_text", "find",
        "read_console_messages", "read_network_requests", "computer"]

SHIP = {
    "browser-explorer": {
        "prompt": "prompts/explorer_v5.md", "effort": "low", "maxTurns": 30, "tools": READ,
        "description": "Use proactively when a task needs a web page opened and read: extract text or table values, follow links across pages, "
                       "find JS-rendered content, read console errors and failed network requests. Read-only (a hook blocks clicks, typing and "
                       "scripts). Reports facts with URLs. Not for filling forms or pressing buttons (use browser-operator), logins, or judgement calls.",
    },
    "browser-operator": {
        "prompt": "prompts/operator_v4.md", "effort": "low", "maxTurns": 30, "tools": READ + ["form_input"],
        "description": "Use to carry out named steps on a named web page: click specific buttons, fill form fields, change filters, then report what the page "
                       "shows and the numbered actions taken. A hook blocks submit, delete, send, pay, approve, sign and export actions and writes an "
                       "audit trail; it stops and reports instead. Not for open-ended exploration (use browser-explorer), logins, or irreversible steps.",
    },
}

for name, s in SHIP.items():
    body = (HERE / s["prompt"]).read_text(encoding="utf-8").strip()
    tools = ", ".join(["ToolSearch"] + [CHROME + t for t in s["tools"]])
    text = (f"---\nname: {name}\ndescription: {json.dumps(s['description'])}\ntools: {tools}\nmodel: claude-haiku-5-5\neffort: {s['effort']}\n"
            f"omitClaudeMd: true\nmaxTurns: {s['maxTurns']}\n---\n\n{body}\n")
    (OUT / f"{name}.md").write_text(text, encoding="utf-8")
    print("wrote", OUT / f"{name}.md", f"({len(text)} chars)")
