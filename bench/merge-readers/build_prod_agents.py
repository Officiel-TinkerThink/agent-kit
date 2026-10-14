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
    "infra-reader": {
        "role": "read-only reader of build, deployment, dependency and configuration files",
        "effort": "low",
        "kinds": [
            ("pipeline-reader", "pipeline-reader", "CI/CD, Dockerfile and compose files: triggers, stages, steps, images, deploy targets (secret names only, never values)"),
            ("dependency-reader", "dependency-reader", "dependency manifests and lockfiles: every dependency with its version constraint and group"),
            ("config-drift-checker", "config-drift-checker", "configuration keys compared across .env.example, compose and settings files; never real .env files"),
        ],
        "description": ("Use proactively to read build, deployment and configuration files without judging them: CI/CD pipelines, Dockerfiles and compose files (names of secrets only, never values); "
                        "dependency manifests with versions and groups; or configuration keys compared across example, compose and settings files (never real .env files). "
                        "Start the task with a line `Task kind: pipeline-reader`, `dependency-reader` or `config-drift-checker` (several kinds when it mixes them). "
                        "Not for vulnerability, upgrade or design judgement."),
    },
    "docs-reader": {
        "role": "read-only reader and first-draft writer for documents",
        "effort": "low",
        "kinds": [
            ("spec-extractor", "spec-extractor", "requirements, IDs, acceptance criteria, roles and cross-references from specs, SOPs, URS/FS, tickets exports or notes"),
            ("doc-link-checker", "doc-link-checker", "broken relative links and references in Markdown documents"),
            ("doc-drafter", "doc-drafter", "first drafts of README sections, docstrings, SOP outlines or test descriptions, returned in the reply and never written to files"),
        ],
        "description": ("Use proactively for document work: pull requirements, IDs and acceptance criteria out of specs, SOPs and notes; find broken relative links in Markdown; "
                        "or produce first drafts of README sections, docstrings, SOP outlines or test descriptions (returned as text, always for human review). "
                        "Start the task with a line `Task kind: spec-extractor`, `doc-link-checker` or `doc-drafter` (several kinds when it mixes them). "
                        "A human reviews the output before it is used in validation documentation."),
    },
    "triage": {
        "role": "read-only triage reader for logs, test output and tickets",
        "effort": "low",
        "kinds": [
            ("log-triage", "log-triage", "long logs, stack traces and CI output: grouped errors, counts, first and last timestamps, earliest failure"),
            ("test-run-summarizer", "test-run-summarizer", "saved pytest, jest or CI test output: totals, first failure, failures grouped by signature"),
            ("ticket-classifier", "ticket-classifier", "a folder of ticket Markdown files: number, title, status and a category from a list you supply, with a verbatim quote"),
        ],
        "description": ("Use proactively to triage long material without diagnosing it: logs, stack traces and CI output (groups, counts, timestamps, earliest failure); saved test-run output (totals and failures by signature); "
                        "or a folder of tickets classified into categories you supply. "
                        "Start the task with a line `Task kind: log-triage`, `test-run-summarizer` or `ticket-classifier` (several kinds when it mixes them). "
                        "Root cause stays with the main model; a human confirms the classification."),
    },
    "compliance-lister": {
        "role": "read-only lister of evidence for compliance and quality review",
        "effort": "low",
        "kinds": [
            ("audit-coverage-lister", "audit-coverage-lister", "which use cases or command modules reference the audit log, evidence only"),
            ("secret-candidate-lister", "secret-candidate-lister", "hardcoded-credential candidates in one directory: location and kind only, never the value"),
            ("citation-verifier", "citation-verifier", "path:line claims re-read against the files: CONFIRMED, WRONG LINE, WRONG TEXT or FILE MISSING"),
        ],
        "description": ("Use proactively to list evidence for a human compliance or quality decision: which use cases reference the audit log; hardcoded-credential candidates (location and kind only, never the value); "
                        "or whether path:line claims made by another agent or document are true. "
                        "Start the task with a line `Task kind: audit-coverage-lister`, `secret-candidate-lister` or `citation-verifier` (several kinds when it mixes them). "
                        "Never decides whether something is sufficient or compliant; that stays a human GxP call."),
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
