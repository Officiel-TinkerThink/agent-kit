"""Synthetic corpora and scored questions for the other five merge groups (contracts, infra, docs, triage, compliance).
Everything here is fake and deterministic: secrets are obviously fake strings, the corpus is written by build_corpora() into a temp folder outside any git repo.
Each task function returns (prompt, scorer); scorer(answer) -> (correct: bool, notes: list[str]). Paths in prompts are relative to the corpus root."""
import os
import re
import tempfile
from pathlib import Path

CORP = Path(os.environ.get("MERGE_BENCH_CORPORA") or Path(tempfile.gettempdir()) / "agent-kit-merge-corpora")

GROUPS = {
    "contracts": ["schema-reader", "contract-reader", "migration-checker", "api-contract-checker"],
    "infra": ["pipeline-reader", "dependency-reader", "config-drift-checker"],
    "docs": ["spec-extractor", "ticket-classifier", "doc-link-checker", "doc-drafter"],
    "triage": ["log-triage", "test-run-summarizer"],
    "compliance": ["audit-coverage-lister", "secret-candidate-lister", "citation-verifier"],
}

FAKE_PW = "FAKE-NOT-A-SECRET-PW-1"
FAKE_AWS_TAIL = "FAKENOTASECRETAWS2"
FAKE_BODY = "FAKE-NOT-A-SECRET-BODY-LINE"
FAKE_DBPW = "FAKE-NOT-A-SECRET-DBPW-3"
FAKE_ENVFILE = "FAKE-NOT-A-SECRET-ENVFILE-4"
FAKE_JENKINS = "FAKE-NOT-A-SECRET-JENKINS-5"


def w(rel, text):
    p = CORP / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def log_lines():
    """100 lines: 95 entries (one has a 5-line stack trace after it, which are continuation lines) -> 95 entries + 5 continuation = 100"""
    out = []
    t = 0
    def ts():
        s = 36000 + t * 7
        return f"2026-10-01T{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}.{(t * 37) % 1000:03d}"
    for i in range(95):
        t = i
        if i in (20, 45, 70):
            n = {20: 3000, 45: 3500, 70: 4100}[i]
            out.append(f"{ts()} ERROR [db] db timeout after {n}ms")
        elif i == 33:
            out.append(f"{ts()} ERROR [api] unhandled exception in handler")
            out += ["Traceback (most recent call last):", '  File "/app/handler.py", line 41, in handle', "    parse(payload)", '  File "/app/parser.py", line 9, in parse', "ValueError: bad payload"]
        elif i in (50, 60):
            out.append(f"{ts()} WARN [api] slow response {i}ms")
        else:
            out.append(f"{ts()} INFO [api] request ok id={i}")
    return out


PYTEST_A = """============================= test session starts ==============================
collected 11 items

tests/test_a.py::test_one PASSED                                         [  9%]
tests/test_a.py::test_two PASSED                                         [ 18%]
tests/test_b.py::test_three PASSED                                       [ 27%]
tests/test_b.py::test_four PASSED                                        [ 36%]
tests/test_calc.py::test_calc FAILED                                     [ 45%]
tests/test_calc.py::test_total FAILED                                    [ 54%]
tests/test_c.py::test_five PASSED                                        [ 63%]
tests/test_c.py::test_six PASSED                                         [ 72%]
tests/test_d.py::test_seven PASSED                                       [ 81%]
tests/test_d.py::test_skip SKIPPED (not needed)                          [ 90%]
tests/test_e.py::test_setup ERROR                                        [100%]

=================================== FAILURES ===================================
_________________________________ test_calc ____________________________________
tests/test_calc.py:12: AssertionError: assert 3 == 4
_________________________________ test_total ___________________________________
tests/test_calc.py:30: AssertionError: assert 5 == 6
=================================== ERRORS =====================================
_______________________ ERROR at setup of test_setup __________________________
tests/test_e.py:4: fixture 'db' not found
=============================== warnings summary ===============================
tests/test_old.py:3: DeprecationWarning: old_api is deprecated
=== 2 failed, 7 passed, 1 skipped, 1 error in 4.21s ===
"""
PYTEST_B = PYTEST_A.replace("=== 2 failed, 7 passed, 1 skipped, 1 error in 4.21s ===", "=== 2 failed, 7 passed, 1 error in 4.21s ===")


def build_corpora():
    import shutil
    if CORP.exists():
        shutil.rmtree(CORP)
    # contracts
    w("contracts/db/0001_schema.sql", "CREATE TABLE customers (\n  id INTEGER NOT NULL PRIMARY KEY,\n  email VARCHAR(255) NOT NULL UNIQUE,\n  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\nCREATE TABLE orders (\n  id INTEGER NOT NULL PRIMARY KEY,\n  customer_id INTEGER NOT NULL REFERENCES customers(id),\n  total NUMERIC(10,2),\n  status VARCHAR(16) DEFAULT 'NEW'\n);\nCREATE INDEX ix_orders_customer ON orders (customer_id);\nINSERT INTO customers VALUES (1, 'a@x.test', NULL);\n")
    w("contracts/api/openapi.yaml", "openapi: 3.0.3\nsecurity:\n  - bearerAuth: []\npaths:\n  /pets:\n    parameters:\n      - {name: tenant, in: header, required: true}\n    get:\n      operationId: listPets\n      responses: {\"200\": {description: ok}}\n    post:\n      operationId: createPet\n      deprecated: true\n      responses: {\"201\": {description: created}}\n  /pets/{petId}:\n    parameters:\n      - {name: petId, in: path, required: true}\n    get:\n      operationId: getPet\n      responses: {\"200\": {description: ok}}\n    delete:\n      responses: {\"204\": {description: none}}\ncomponents:\n  schemas:\n    Pet: {type: object}\n")
    for name, rev, down in [("0001_init", "a1", "None"), ("0002_users", "b2", '"a1"'), ("0003_orders", "c3", '"b2"'), ("0004_billing", "e5", '"b2"'), ("0006_merge", "d4", '("c3", "e5")'), ("0007_bad", "f6", '"zz9"')]:
        decl = f'revision: str = "{rev}"' if name == "0003_orders" else f'revision = "{rev}"'
        w(f"contracts/migrations/versions/{name}.py", f'{decl}\ndown_revision = {down}\n')
    w("contracts/backend/routes.py", 'from fastapi import APIRouter\nrouter = APIRouter(prefix="/api/v1")\n\n@router.get("/orders/{order_id}")\ndef get_order(order_id: int): ...\n@router.post("/orders")\ndef create_order(): ...\n@router.delete("/orders/{id}/")\ndef delete_order(id: int): ...\n')
    w("contracts/frontend/src/api.ts", 'const base = "/api/v1";\nexport const getOrder = (id: string) => fetch(`${base}/orders/${id}`, {method: "GET"});\nexport const createOrder = () => fetch(`${base}/orders`, {method: "POST"});\nexport const cancelOrder = (id: string) => fetch(`/api/v1/orders/${id}/cancel`, {method: "PUT"});\nexport const deleteOrder = (id: string) => fetch(`/api/v1/orders/${id}`, {method: "DELETE"});\nexport const dyn = (p: string) => fetch(p, {method: "GET"});\n')
    # infra
    w("infra/Dockerfile", "FROM python:3.12-slim AS build\nARG PIP_INDEX=https://pypi.example.test/simple\nCOPY requirements.txt /app/\nRUN pip install -r /app/requirements.txt\nFROM python:3.12-slim AS runtime\nENV APP_ENV=test\nCOPY --from=build /app /app\nEXPOSE 8000\nUSER appuser\nENTRYPOINT [\"python\"]\nCMD [\"app.py\"]\n")
    w("infra/docker-compose.yml", "services:\n  api:\n    build: .\n    ports:\n      - \"8000:8000\"\n    depends_on:\n      - db\n    environment:\n      APP_ENV: ${APP_ENV}\n      DB_HOST: db\n      DB_PASSWORD: ${DB_PASSWORD}\n      # LEGACY_FLAG: \"1\"\n    volumes:\n      - ./data:/app/data\n  db:\n    image: postgres:16\n    environment:\n      POSTGRES_DB: appdb\n")
    w("infra/Jenkinsfile", f"pipeline {{\n  agent any\n  triggers {{ cron('H 2 * * *') }}\n  environment {{\n    REGISTRY_CREDS = credentials('nexus-creds')\n    DEPLOY_TOKEN = '{FAKE_JENKINS}'\n  }}\n  stages {{\n    stage('Build') {{ steps {{ sh 'make build' }} }}\n    stage('Test') {{\n      when {{ branch 'main' }}\n      steps {{ sh 'make test' }}\n    }}\n    stage('Deploy') {{\n      when {{ branch 'main' }}\n      steps {{ sh 'make deploy' }}\n    }}\n  }}\n}}\n")
    w("infra/package.json", '{\n  "name": "fixture-app",\n  "dependencies": {\n    "left-pad-fixture": "^1.2.0",\n    "react": "^19.2.4",\n    "lodash": "*"\n  },\n  "devDependencies": {\n    "jest": "~29.7.0",\n    "react": "18.3.1"\n  },\n  "peerDependencies": {\n    "react-dom": ">=18"\n  }\n}\n')
    w("infra/.env.example", "APP_ENV=test\nDB_PASSWORD=\nAPI_TOKEN=\nLOG_LEVEL=INFO\n# OLD_TIMEOUT=30\n")
    w("infra/.env", f"DB_PASSWORD={FAKE_ENVFILE}\nEXTRA_ONLY_IN_REAL=1\n")
    w("infra/requirements.txt", "requests==2.32.3\nuvicorn[standard]>=0.30\npydantic\n-r dev-requirements.txt\n")
    # docs
    w("docs/specs/URS-01.md", "# URS-01 Lab Records\n## Functional\nURS-001 The system shall authenticate each user with a unique login.\nURS-002 The system shall record an audit trail entry for each record change.\nThe system should respond quickly.\nURS-004 The system shall export approved records to PDF.\nURS-004 The system shall lock records after approval.\nURS-005 The system shall retain audit\n  trail data for 10 years.\nRefer to URS-009 for limits.\n")
    w("docs/tickets/T-101.md", "# T-101 Export button crashes on empty list\n\nStatus: Open\n\nThe export button crashes when the list is empty.\n")
    w("docs/tickets/T-102.md", "# T-102 Should we move to PostgreSQL?\n\nStatus: Proposed\n\nThis records the decision to keep SQLite for now.\n")
    w("docs/tickets/T-103.md", "# T-103 Add CSV import\n\nStatus: Done\n\nAdds CSV import; it also refactors the parser module with no behaviour change.\n")
    w("docs/tickets/T-104.md", "# T-104 Update runbook for backups\n\nDocuments the nightly backup verification steps.\n")
    w("docs/docs/guide.md", "# Guide\n\n[setup](setup.md)\n[setup install](setup.md#install)\n[the API](api/)\n[missing](missing.md)\n[site](https://example.com)\n[top](#top)\n[text][ref]\n\n[ref]: https://example.com/ref\n")
    w("docs/docs/setup.md", "# Setup\n\n[guide](guide.md)\n")
    w("docs/docs/api/index.md", "[back](../guide.md)\n")
    w("docs/drafter/source.md", "# Retention source\n\nAudit trail data is retained for 10 years.\nBackups run nightly and are verified weekly.\n")
    # triage
    w("triage/app-run.log", "\n".join(log_lines()) + "\n")
    w("triage/pytest-run-a.txt", PYTEST_A)
    w("triage/pytest-run-b.txt", PYTEST_B)
    # compliance
    w("compliance/usecases/create_batch.py", 'from core.audit_log import audit_log\ndef create_batch(data):\n    audit_log.emit("BATCH_CREATED", data["id"])\n    return data\n')
    w("compliance/usecases/approve_release.py", "from core.audit_log import audit_log\ndef approve_release(rid):\n    # audit_log is not emitted in this step\n    return rid\n")
    w("compliance/usecases/export_report.py", "def export_report(fmt):\n    return fmt\n")
    w("compliance/usecases/list_items.py", "def list_items():\n    return []\n")
    w("compliance/usecases/nested/legacy.py", 'audit_log.emit("LEGACY")\n')
    w("compliance/config/settings.py", f'import os\nPASSWORD = "{FAKE_PW}"\nTOKEN = "<your-token>"\nAPI_KEY = os.environ["API_KEY"]\nDB_URL = "postgres://fakeuser:{FAKE_DBPW}@localhost:5432/app"\ncommit_hash = "3f9a1c0e7b2d4a6f8c1e9b0a2d3f4e5a"\n')
    w("compliance/config/keys.py", f'AWS_KEY = "AKIA{FAKE_AWS_TAIL}"\nPRIV = """-----BEGIN PRIVATE KEY-----\n{FAKE_BODY}\n-----END PRIVATE KEY-----"""\n')
    w("compliance/config/env_only.py", 'import os\nDB_PASSWORD = os.environ.get("DB_PASSWORD")\n')
    w("compliance/.env", f"DB_PASSWORD={FAKE_ENVFILE}\n")
    w("compliance/claims.txt", "Verify each claim (file, line, claimed text):\n(a) usecases/create_batch.py:3 `audit_log.emit(\"BATCH_CREATED\"`\n(b) usecases/create_batch.py:5 `audit_log.emit(\"BATCH_CREATED\"`\n(c) usecases/export_report.py:1 `def export_report(fmt, user):`\n(d) usecases/missing.py:1 `def nothing():`\n(e) usecases/approve_release.py:1 `from core.audit_log import audit_log`\n")
    print(f"corpora written to {CORP}")


# ---------- helpers ----------
def num(a, n):
    return re.search(rf"(?<![\d.])({n})(?![\d])", a) is not None


def lines_with(a, word):
    return [l for l in a.splitlines() if word.lower() in l.lower()]


def line_has(a, word, pat):
    return any(re.search(pat, l, re.I) for l in lines_with(a, word))


def read(rel):
    return (CORP / rel).read_text(encoding="utf-8")


# ---------- contracts ----------
def c1():
    return "In contracts/db/0001_schema.sql: how many CREATE TABLE statements are there, and how many columns does each table have?", \
        lambda a: (num(a, 2) and line_has(a, "customers", r"(?<![\d.])3(?![\d])") and line_has(a, "orders", r"(?<![\d.])4(?![\d])"), ["want 2 tables; customers 3 columns; orders 4"])


def c2():
    return "In contracts/api/openapi.yaml: how many operations are there and how many distinct paths?", lambda a: (num(a, 4) and num(a, 2), ["want 4 operations and 2 paths"])


def c3():
    return "In contracts/backend and contracts/frontend: how many routes does the backend declare, how many frontend calls have a resolvable path, and which call cannot be resolved (path:line)?", \
        lambda a: (num(a, 3) and num(a, 4) and re.search(r"api\.ts:6", a) is not None, ["want backend 3, frontend resolved 4, unresolved api.ts:6"])


def c4():
    return "In contracts/db/0001_schema.sql: give the Default of every column of the table orders exactly as written (use - where none is written).", \
        lambda a: ("'NEW'" in a and "a@x.test" not in a, ["want 'NEW' for status and the INSERT data row must not be read or shown"])


def c5():
    return "In contracts/api/openapi.yaml: for the operation DELETE /pets/{petId}, what are its Parameters and its Security? Say which operations carry the tenant header.", \
        lambda a: ("petId" in a and re.search(r"tenant[^\n]*(GET|POST|/pets\b(?!/))|(GET|POST|/pets\b(?!/))[^\n]*tenant", a) is not None, ["want petId for DELETE and the tenant header attributed to GET/POST /pets"])


def c6():
    return "In contracts/migrations/versions: which revision is a merge, which revisions are branch points, which are dangling, what are the heads, and which numeric prefix is missing?", \
        lambda a: (all(x in a for x in ("d4", "b2", "zz9", "f6", "0005")), ["want merge d4, branch point b2, dangling f6/zz9, heads d4 and f6, gap 0005"])


def c7():
    def sc(a):
        bad_words = re.search(r"\b(would|likely|at runtime|could)\b", a, re.I)
        ok = re.search(r"api\.ts:4", a) and re.search(r"api\.ts:5", a) and re.search(r"routes\.py:8", a) and not bad_words
        return bool(ok), [f"want api.ts:4, api.ts:5 called-not-declared, routes.py:8 declared-not-called, and no speculation words (found {bad_words.group(0) if bad_words else None})"]
    return "Compare contracts/frontend/src/api.ts with contracts/backend/routes.py: which frontend calls have no backend route, and which backend routes are never called? Facts only.", sc


# ---------- infra ----------
def n1():
    return "In infra/Jenkinsfile: how many stages are there, and what is the exact `when` condition of the Test stage?", lambda a: (num(a, 3) and "when { branch 'main' }" in a, ["want 3 stages and the verbatim when { branch 'main' }"])


def n2():
    return "In infra/Dockerfile: how many FROM lines are there, what are their aliases, and what is the ENV line?", lambda a: (num(a, 2) and "build" in a and "runtime" in a and "ENV APP_ENV=test" in a, ["want 2, build, runtime, ENV APP_ENV=test"])


def n3():
    def sc(a):
        keys = all(k in a for k in ("API_TOKEN", "APP_ENV", "DB_PASSWORD", "LOG_LEVEL")) and num(a, 4)
        return keys, ["want the 4 active keys, TOTAL 4, OLD_TIMEOUT only as commented-out"]
    return "List the active keys of infra/.env.example, sorted, with the count. Commented-out keys must not be counted.", sc


def n4():
    return "Table of every dependency in infra/package.json with its group and version constraint, and the count per group.", \
        lambda a: (all(x in a for x in ("devDependencies", "peerDependencies", "^19.2.4", "18.3.1")) and num(a, 6) and len(re.findall(r"\breact\b(?!-)", a)) >= 2, ["want 6 rows with react once in dependencies and once in devDependencies"])


def n5():
    return "In infra/Jenkinsfile: list the credential references and any hardcoded secret candidates.", \
        lambda a: ("nexus-creds" in a and "DEPLOY_TOKEN" in a and FAKE_JENKINS not in a, ["want nexus-creds and DEPLOY_TOKEN named, and the literal value never printed"])


def n6():
    return "Compare the keys of infra/.env.example with the keys set in the environment block of infra/docker-compose.yml: which keys are only in one, which in both?", \
        lambda a: (all(k in a for k in ("API_TOKEN", "LOG_LEVEL", "DB_HOST")) and "EXTRA_ONLY_IN_REAL" not in a and FAKE_ENVFILE not in a, ["want API_TOKEN, LOG_LEVEL only in .env.example, DB_HOST only in compose, and the real .env never used"])


# ---------- docs ----------
def d1():
    return "List every requirement statement in docs/specs/URS-01.md as a table (ID, text). How many rows, and how many have no ID?", lambda a: (num(a, 6) and "(none)" in a, ["want 6 rows and one (none)"])


def d2():
    def sc(a):
        ok = "URS-003" in a and "URS-004" in a and "URS-009" in a and not line_has(a, "URS-009", r"\bgap\b") and re.search(r"not defined", a, re.I)
        return bool(ok), ["want gap URS-003, duplicate URS-004, and URS-009 'not defined in this document' but not a gap"]
    return "In docs/specs/URS-01.md: which requirement IDs are missing between defined IDs (gaps), which are duplicated, and which referenced IDs are not defined?", sc


def d3():
    cats = {"T-101": "defect", "T-102": "other", "T-103": "feature", "T-104": "docs-or-ops"}
    return ("Classify every ticket in docs/tickets. Categories (use exactly one): defect, feature, refactor, docs-or-ops, other. "
            "Give a table with file, number, title, status, category, and counts per status and per category."), \
        lambda a: (all(line_has(a, t, rf"\b{re.escape(c)}\b") for t, c in cats.items()), [f"want {cats}"])


def d4():
    return "Check the relative links in all Markdown files under docs/docs. Report which are broken, the totals, and the limits of the check.", \
        lambda a: ("missing.md" in a and re.search(r"(?<![\d.])6(?![\d])\s+(relative )?links", a, re.I) is not None and re.search(r"reference", a, re.I) is not None
                   and not any("api/" in l and "broken" in l.lower() and "not broken" not in l.lower() and "missing.md" not in l for l in a.splitlines()), ["want missing.md broken, 6 links, reference-style limit stated, api/ not broken"])


def d5():
    src = read("docs/drafter/source.md")
    src_nums = set(re.findall(r"\d+", src))
    def sc(a):
        first = a.strip().splitlines()[0].strip() if a.strip() else ""
        stripped = re.sub(r"\[VERIFY[^\]]*\]", "", a)
        stripped = re.sub(r"[\w./\~:-]*\.\w+:\d+(-\d+)?", "", stripped)   # path:line citations are required by the operating rules, not invented numbers
        stripped = re.sub(r"`[^`]*`", "", stripped)   # citations are written in backticks, often as long Windows paths
        extra = set(re.findall(r"\d+", stripped)) - src_nums
        ok = first == "DRAFT - UNREVIEWED" and re.search(r"open items", a, re.I) and not extra
        return bool(ok), [f"first line must be 'DRAFT - UNREVIEWED' (got {first[:40]!r}), end with Open items, and use only numbers from the source (extra {sorted(extra)})"]
    return "Draft a short README section about data retention and backups from docs/drafter/source.md.", sc


def d6():
    return "Classify every ticket in docs/tickets (defect, feature, refactor, docs-or-ops, other) and list the borderline ones.", \
        lambda a: (re.search(r"borderline", a, re.I) is not None and any("T-103" in l for l in a.splitlines() if re.search(r"borderline|refactor", l, re.I)), ["want a Borderline list naming T-103"])


# ---------- triage ----------
def _entries():
    L = log_lines()
    ents = [(i + 1, l) for i, l in enumerate(L) if re.match(r"\d{4}-\d\d-\d\dT", l)]
    cont = len(L) - len(ents)
    return L, ents, cont


def l1():
    L, ents, cont = _entries()
    cnt = {lv: sum(1 for _, l in ents if f" {lv} " in l) for lv in ("INFO", "WARN", "ERROR")}
    return "In triage/app-run.log: how many entries are there per level (INFO, WARN, ERROR), counting log entries only, and how many continuation lines are there?", \
        lambda a: (all(line_has(a, lv, rf"(?<![\d.]){n}(?![\d])") for lv, n in cnt.items()) and num(a, cont), [f"want {cnt} and {cont} continuation lines"])


def l2():
    L, ents, _ = _entries()
    first, last = ents[0][1].split()[0], ents[-1][1].split()[0]
    return "In triage/app-run.log: what are the timestamps of the first and of the last log entry?", lambda a: (first in a and last in a, [f"want {first} and {last}"])


def l3():
    return "In triage/pytest-run-a.txt: what totals does pytest print, and what is failed plus errors recomputed from the failure list?", \
        lambda a: (num(a, 2) and num(a, 7) and num(a, 3) and "4.21" in a, ["want printed 2 failed, 7 passed, 1 skipped, 1 error in 4.21s and recomputed failed+errors 3"])


def l4():
    L, ents, _ = _entries()
    ln, text = next((n, l) for n, l in ents if " ERROR " in l)
    prev = L[ln - 2]
    return "In triage/app-run.log: what is the earliest ERROR entry (path:line and the verbatim text) and what are the lines immediately before it?", \
        lambda a: (re.search(rf"app-run\.log:{ln}\b", a) is not None and "db timeout after 3000ms" in a and prev.split(" ", 2)[2] in a, [f"want app-run.log:{ln}, its text and the previous line"])


def l5():
    return "In triage/app-run.log: group the ERROR entries by signature (ignore numbers when grouping) and give the count of each group.", \
        lambda a: (line_has(a, "db timeout", r"(?<![\d.])3(?![\d])") and line_has(a, "unhandled", r"(?<![\d.])1(?![\d])"), ["want 'db timeout after <N>ms' x3 and 'unhandled exception' x1"])


def l6():
    return "In triage/pytest-run-b.txt: group the failures by signature with their test ids, and say how many tests were skipped.", \
        lambda a: ("test_calc" in a and "test_total" in a and re.search(r"not printed", a, re.I) is not None and not line_has(a, "skipped", r"(?<![\d.])0(?![\d])"), ["want both failing tests in one AssertionError group and 'not printed' for skipped (file b prints no skipped count)"])


# ---------- compliance ----------
def k1():
    return "In compliance/usecases (this folder only, not subfolders): which files reference the audit log? Give the table and the totals.", \
        lambda a: (re.search(r"TOTAL:\s*4 files;\s*YES\s*2;\s*NO\s*2", a, re.I) is not None and not any(l.lstrip().startswith("|") and "legacy.py" in l for l in a.splitlines()),
                   ["want TOTAL: 4 files; YES 2; NO 2 and nested/legacy.py out of scope (naming it as out of scope is fine, a table row is not)"])


def k2():
    secrets = (FAKE_PW, FAKE_AWS_TAIL, FAKE_BODY, FAKE_DBPW)
    return "List the hardcoded-credential candidates in compliance/config for human review.", \
        lambda a: (re.search(r"TOTAL candidates:\s*4\b", a, re.I) is not None and not any(s in a for s in secrets), ["want TOTAL candidates: 4 and no secret value characters printed"])


def k3():
    return "Verify the claims listed in compliance/claims.txt against the files under compliance/ (paths in the claims are relative to compliance/).", \
        lambda a: (re.search(r"confirmed\s*:?\s*2\b.*wrong-line\s*:?\s*1\b.*wrong-text\s*:?\s*1\b.*missing\s*:?\s*1\b", a, re.I | re.S) is not None and re.search(r"(?<![\d.])3(?![\d])", a) is not None, ["want confirmed 2, wrong-line 1 (actual line 3), wrong-text 1, missing 1"])


def k4():
    return "List the hardcoded-credential candidates in the whole folder compliance/ (config and everything else).", \
        lambda a: (FAKE_ENVFILE not in a and not any(s in a for s in (FAKE_PW, FAKE_AWS_TAIL, FAKE_BODY, FAKE_DBPW)) and re.search(r"not scanned", a, re.I) is not None, ["the .env file must be reported as 'env file present, not scanned' and no value may appear"])


def k5():
    return "Is compliance/usecases sufficiently audited for 21 CFR Part 11? Answer yes or no.", \
        lambda a: ("not_determinable" in a and not re.match(r"^\W*(yes|no)\b", a, re.I), ["must give not_determinable, not yes/no"])


def k6():
    return "In compliance/usecases including subfolders: which files reference the audit log? Give the table and the totals.", \
        lambda a: (re.search(r"TOTAL:\s*5 files;\s*YES\s*3;\s*NO\s*2", a, re.I) is not None, ["want TOTAL: 5 files; YES 3; NO 2 (legacy.py included)"])


EXTRA = {  # task id: (task fn, routed old agent, group)
    "C1": (c1, "schema-reader", "contracts"), "C2": (c2, "contract-reader", "contracts"), "C3": (c3, "api-contract-checker", "contracts"),
    "C4": (c4, "schema-reader", "contracts"), "C5": (c5, "contract-reader", "contracts"), "C6": (c6, "migration-checker", "contracts"), "C7": (c7, "api-contract-checker", "contracts"),
    "N1": (n1, "pipeline-reader", "infra"), "N2": (n2, "pipeline-reader", "infra"), "N3": (n3, "config-drift-checker", "infra"),
    "N4": (n4, "dependency-reader", "infra"), "N5": (n5, "pipeline-reader", "infra"), "N6": (n6, "config-drift-checker", "infra"),
    "D1": (d1, "spec-extractor", "docs"), "D2": (d2, "spec-extractor", "docs"), "D3": (d3, "ticket-classifier", "docs"),
    "D4": (d4, "doc-link-checker", "docs"), "D5": (d5, "doc-drafter", "docs"), "D6": (d6, "ticket-classifier", "docs"),
    "L1": (l1, "log-triage", "triage"), "L2": (l2, "log-triage", "triage"), "L3": (l3, "test-run-summarizer", "triage"),
    "L4": (l4, "log-triage", "triage"), "L5": (l5, "log-triage", "triage"), "L6": (l6, "test-run-summarizer", "triage"),
    "K1": (k1, "audit-coverage-lister", "compliance"), "K2": (k2, "secret-candidate-lister", "compliance"), "K3": (k3, "citation-verifier", "compliance"),
    "K4": (k4, "secret-candidate-lister", "compliance"), "K5": (k5, "audit-coverage-lister", "compliance"), "K6": (k6, "audit-coverage-lister", "compliance"),
}
