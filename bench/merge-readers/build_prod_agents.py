"""Builds the shipped merged agents (code-explorer, contracts-reader) mechanically from the frozen old definitions in old-agents/.
The shared operating rules are written once, each old agent's task rules become one section named by its kind, and the description tells the caller to start the task with `Task kind: <kind>`.
Run: python build_prod_agents.py   (writes plugins/haiku-delegation/agents/<name>.md)"""
import sys
from pathlib import Path

import bench

OUT = bench.REPO / "plugins" / "haiku-delegation" / "agents"

MERGES = {
    "code-explorer": {
        "role": "read-only code and document explorer",
        "effort": "low",
        "kinds": [
            ("locate", "repo-scout", "where a symbol, config key or endpoint is defined or used, and which files exist for a feature"),
            ("read", "bulk-reader", "answer a question that needs reading large files or many files"),
            ("map", "module-mapper", "packages and modules, import edges, entry points, and what one file or module is for"),
            ("inventory", "inventory-extractor", "tables of endpoints, config keys, env vars, dependencies, TODOs, requirement IDs"),
            ("tests", "test-case-lister", "which automated tests exist, what they exercise, and which public functions have none"),
        ],
        "description": ("Use proactively for read-only work on code and documents: locate where something is defined or used, answer questions that need reading large or many files, "
                        "map structure and imports or summarise a file, build inventories (endpoints, config keys, env vars, dependencies, TODOs, requirement IDs) as tables, or list existing tests "
                        "and untested public functions. Start the task with a line `Task kind: locate`, `read`, `map`, `inventory` or `tests` (several kinds when it mixes them). "
                        "Not for editing, debugging, architecture decisions or safety/GxP judgement."),
    },
    "contracts-reader": {
        "role": "read-only reader of database and API contracts",
        "effort": "medium",
        "kinds": [
            ("schema", "schema-reader", "tables, columns, keys and indexes from DDL, migration files or ORM models"),
            ("api-spec", "contract-reader", "operations, parameters, responses and security of an OpenAPI or GraphQL schema file"),
            ("migrations", "migration-checker", "the revision chain of an Alembic-style migrations folder: heads, branches, merges, dangling parents, gaps"),
            ("api-match", "api-contract-checker", "frontend HTTP calls against backend route declarations: matched, called but not declared, declared but not called"),
        ],
        "description": ("Use proactively to read database and API contracts without judging them: tables and columns from DDL, migrations or ORM models; operations of an OpenAPI or GraphQL file; "
                        "the revision chain of a migrations folder (heads, branches, merges, dangling parents, gaps); or frontend calls compared with backend routes. "
                        "Start the task with a line `Task kind: schema`, `api-spec`, `migrations` or `api-match` (several kinds when it mixes them). "
                        "Reports what is written; never reviews design, naming or security, and never reads seed or data rows."),
    },
}


def build(name, spec):
    assert '"' not in spec["description"] and "\\" not in spec["description"], "the description is written as a double-quoted YAML string"
    agents = [a for _, a, _ in [(k, a, p) for k, a, p in spec["kinds"]]]
    parts = [bench.split_agent(a) for a in agents]
    shared = {p[2] for p in parts}
    assert len(shared) == 1, f"{name}: operating-rule blocks differ"
    turns = max(int(p[0]["maxTurns"]) for p in parts)
    lines = ["---", f"name: {name}", f'description: "{spec["description"]}"', "tools: Read, Grep, Glob", "model: claude-haiku-5-5", f"effort: {spec['effort']}", "omitClaudeMd: true", f"maxTurns: {turns}", "---", ""]
    kinds = ", ".join(f"`{k}`" for k, _, _ in spec["kinds"])
    lines += [f"You are a {spec['role']}. You handle {len(agents)} kinds of task: {kinds}. The first line of the task names the kind (`Task kind: <kind>`); apply that section first and follow every rule of it. "
              "If the task names several kinds, apply each section. If it names none, choose the section that fits the question.", ""]
    lines += [parts[0][2], ""]
    for (kind, agent, purpose), (meta, intro, _, rules) in zip(spec["kinds"], parts):
        lines += [f"## {kind}: {purpose}", intro, "", rules.replace("Task rules:", f"Rules for `Task kind: {kind}`:", 1), ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    for name, spec in MERGES.items():
        text = build(name, spec)
        (OUT / f"{name}.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"{name}: {len(text)} chars, {text.count(chr(10))} lines")


if __name__ == "__main__":
    sys.exit(main())
