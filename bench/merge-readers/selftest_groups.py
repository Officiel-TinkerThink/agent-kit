"""Scorer self-test: every task must accept a hand-written correct answer and reject a bad one. Run: python selftest_groups.py"""
import sys

import tasks_groups as TG
import bench

TG.build_corpora()
L, ents, cont = TG._entries()
first_err_line = next(n for n, l in ents if " ERROR " in l)
prev = L[first_err_line - 2].split(" ", 2)[2]
IDEAL = {
    "C1": "2 CREATE TABLE statements.\n- customers: 3 columns\n- orders: 4 columns",
    "C2": "4 operations across 2 paths.",
    "C3": "Backend declares 3 routes; frontend resolves 4 calls; UNCLEAR: contracts/frontend/src/api.ts:6",
    "C4": "| id | - |\n| customer_id | - |\n| total | - |\n| status | 'NEW' |",
    "C5": "DELETE /pets/{petId}: Parameters petId:path:true (path-level); Security -. The tenant header applies to GET /pets and POST /pets.",
    "C6": "HEADS: d4, f6. BRANCH POINTS: b2. Merge: d4. DANGLING: 0007_bad.py (f6 -> zz9). NUMERIC GAPS: 0005.",
    "C7": "CALLED BUT NOT DECLARED: PUT /orders/{}/cancel (contracts/frontend/src/api.ts:4); DELETE /orders/{} (contracts/frontend/src/api.ts:5).\nDECLARED BUT NOT CALLED: DELETE /orders/{id}/ (contracts/backend/routes.py:8).",
    "N1": "3 stages. Test: when { branch 'main' }",
    "N2": "2 FROM lines: aliases build, runtime. ENV APP_ENV=test",
    "N3": "API_TOKEN, APP_ENV, DB_PASSWORD, LOG_LEVEL. TOTAL 4. OLD_TIMEOUT is commented-out.",
    "N4": "| left-pad-fixture | ^1.2.0 | dependencies |\n| react | ^19.2.4 | dependencies |\n| lodash | * | dependencies |\n| jest | ~29.7.0 | devDependencies |\n| react | 18.3.1 | devDependencies |\n| react-dom | >=18 | peerDependencies |\nTOTAL 6",
    "N5": "credential id: nexus-creds\nHardcoded-secret candidates: DEPLOY_TOKEN <literal value present - not shown>",
    "N6": "ONLY IN .env.example: API_TOKEN, LOG_LEVEL. ONLY IN compose: DB_HOST. IN BOTH: APP_ENV, DB_PASSWORD.",
    "D1": "| URS-001 | ... |\n(6 rows; 1 row has ID (none))",
    "D2": "Gaps: URS-003. Duplicates: URS-004. Referenced IDs not defined: URS-009 (not defined in this document).",
    "D3": "| T-101 | defect |\n| T-102 | other |\n| T-103 | feature |\n| T-104 | docs-or-ops |",
    "D4": "CHECKED: 6 relative links in 3 documents; BROKEN: 1\ndocs/docs/guide.md:6 missing.md\nLimits: reference-style links not detected.",
    "D5": "DRAFT - UNREVIEWED\n\nAudit trail data is retained for 10 years. Backups run nightly [VERIFY: weekly check not confirmed 99].\n\nOpen items\n- [VERIFY: weekly check not confirmed 99]",
    "D6": "T-103 feature\nBorderline: T-103 (also a refactor)",
    "L1": f"INFO {sum(1 for _, l in ents if ' INFO ' in l)}; WARN 2; ERROR 4; continuation lines {cont}",
    "L2": f"first {ents[0][1].split()[0]}; last {ents[-1][1].split()[0]}",
    "L3": "Printed: 2 failed, 7 passed, 1 skipped, 1 error in 4.21s. Recomputed failed + errors = 3.",
    "L4": f"triage/app-run.log:{first_err_line} 2026 ERROR [db] db timeout after 3000ms\nBefore it: {prev}",
    "L5": "| db timeout after <N>ms | 3 |\n| unhandled exception in handler | 1 |",
    "L6": "AssertionError group: test_calc, test_total. Skipped: not printed.",
    "K1": "TOTAL: 4 files; YES 2; NO 2",
    "K2": "TOTAL candidates: 4",
    "K3": "TOTAL: 5 claims; confirmed 2, wrong-line 1 (actual line 3), wrong-text 1, missing 1, unclear 0",
    "K4": "TOTAL candidates: 4\nenv file present, not scanned: compliance/.env",
    "K5": "not_determinable. Evidence: YES 2 / NO 2.",
    "K6": "TOTAL: 5 files; YES 3; NO 2",
}
bad = 0
for k, (f, r, g) in TG.EXTRA.items():
    p, s = f()
    ok, notes = s(IDEAL[k])
    rej, _ = s("I could not find anything.")
    if not ok or rej:
        bad += 1
        print("FAIL", k, "accepts ideal:", ok, "rejects bad:", not rej, notes)
print("self-test:", "all scorers behave" if not bad else f"{bad} scorer(s) wrong")
sys.exit(1 if bad else 0)
