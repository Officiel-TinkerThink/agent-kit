---
name: guidance-lens
description: "Focus-mode lens for project rule files and guidance comments. Preloaded into guidance-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: guidance-lens v1

# Guidance Lens

Checks the change against the project's written rules: which rule governs which path, and whether the change follows it.
Only rules with a checkable condition count. Every finding quotes the rule and the code line that breaks it.

## How to look

1. Collect the rule files: the root rule file and every rule file in each directory from the repo root down to each modified file. Number every rule (R1, R2, ...) with its file and scope path. Drop rules with no checkable condition.
2. Keep only the rules whose scope covers each changed file. A nested rule does not apply outside its directory.
3. For each hunk, check the rule condition against the lines the hunk adds, modifies or moves. Quote the code line. Find the SIBLING that does the same job: if it obeys the rule and the new code does not, that is evidence. If the rule names a helper, read the helper body.
4. Look at what the change REMOVED or MOVED (a required call, check, record write, protected line). For each guidance comment that restricts ordering or sequencing, read the code it describes, even when that code is far away.
5. Check the second file for process rules: defaults file, template copy, changelog line, test. Search for the new name; it may already exist in the repo.
6. Trace one concrete input or call through the code, write the outcome next to the rule number, and report only if it breaks the rule.

## Catalog

### Root rule violated in a nested directory
- Tell: a write, call or branch in a sub-package skips the call the root rule requires.
- Fails when: the root rule requires every record write to call the change-audit function. A sub-package write that skips it leaves the change unrecorded.
Bad:
```python
# RULE (project rules file): every write must satisfy the change-recording requirement its rule file names.
def cancel_order(session, order):
    order.status = "CANCELLED"
    session.add(order)
```
Good:
```python
def cancel_order(session, order, user):
    order.status = "CANCELLED"
    session.add(order)
    change_entry(session, user, "order", order.id, "status:CANCELLED")
```
Not a defect when: the statement only reads data, or the rule's scope excludes this path.

### Nested rule applied outside its directory
- Tell: a finding cites a rule file from one directory against code in a sibling directory.
- Fails when: `services/shipping/AGENTS.md` sets a value-type rule for its subtree. A float in `services/orders/pricing.py` is reported against it. The rule does not reach that path, so the finding is a false positive.
Bad:
```python
# file: services/shipping/rates.py (added by the change)
# RULE R7 (services/shipping/AGENTS.md): weights use Decimal, never float
weight = 0.15
```
Good:
```python
from decimal import Decimal
weight = Decimal("0.15")
```
Not a defect when: the file is outside `services/shipping/`. `weight = 0.15` in `services/orders/pricing.py` is not covered by R7; drop that finding and cite R7 only for files under `services/shipping/`.

### Rule satisfied through a wrapper whose name does not match the rule wording
- Tell: the rule names `log_access()`, but the path calls a helper with another name that calls `log_access()` on some branches only.
- Fails when: `fetch_patient()` returns a cached row before it reaches `log_access()`. Reads served from cache are not logged, so R4 fails on that path.
Bad:
```python
# RULE R4: every patient read calls log_access(user, patient_id)
def fetch_patient(user, pid):
    if pid in cache:
        return cache[pid]              # early return: no log_access
    log_access(user, pid)
    return db.get(Patient, pid)
```
Good:
```python
def fetch_patient(user, pid):
    log_access(user, pid)              # before any return
    return cache.get(pid) or db.get(Patient, pid)
```
Not a defect when: every path through the helper calls the required function before it returns.

### Exemption comment that silences a rule without the form the rule allows
- Tell: a comment such as `# R3 exempt` sits on a line that breaks R3, with no change ID or reason in the form the rule file defines.
- Fails when: the rule file says exemptions need a change-control ID. `order.save()  # R3 exempt` writes an order with no audit entry, and the comment lacks the ID, so the violation stands.
Bad:
```python
order.save()  # R3 exempt
```
Good:
```python
order.save()
change_entry(session, user, "order", order.id, "save")  # R3: audited, no exemption needed
```
Not a defect when: the comment matches the exemption form the rule file defines (rule ID, change-control ID) and the exempt target is the line it sits on. If the rule file defines no exemption form, no comment silences the rule and the violation stands.

### Public versus private scope in the rule text
- Tell: a rule says "public functions validate arguments" and the new function has a leading underscore, or is exported in `__all__` or a package `__init__.py`.
- Fails when: `_normalise` is re-exported in `__init__.py`. Callers outside the package use it, so the public rule applies and the missing validation is a defect.
Bad:
```python
# RULE R5: public functions validate their arguments
def _prepare(value):                   # private by name, but see __init__.py
    return value.strip()
```
Good:
```python
def normalise(value):
    if not isinstance(value, str): raise TypeError("argument has the wrong type")
    return value.strip()
```
Not a defect when: the name starts with an underscore and no `__all__` or `__init__.py` export makes it public.

### Cross-file rule: new config key missing from the defaults file
- Tell: a new key is read in settings or a loader, and the defaults or example file has no entry for it.
- Fails when: The rule says every key appears in the defaults file. `NEW_SETTING = int(os.environ["NEW_SETTING"])` has no default, so a fresh install fails at startup with KeyError. The rule violated is the defaults-file rule, not the crash: an environment fallback in code alone does not satisfy it.
Bad:
```python
# settings.py (changed)
NEW_SETTING = int(os.environ["NEW_SETTING"])
# <defaults file>: no entry for the new key
```
Good:
```python
# settings.py
NEW_SETTING = int(os.environ.get("NEW_SETTING", "30"))
# config/defaults.toml (same change)
NEW_SETTING = 30
```
Not a defect when: the key already exists in the defaults file in the repo (check the file, not only the diff), or the rule exempts secrets, which never go in defaults.

### Wrapper that looks compliant but calls the wrong function
- Tell: the call sits beside a write, and the helper it uses is the read-audit helper or a sibling, not the one the rule names.
- Fails when: a recording call of a different kind than the one a rule names does not satisfy that rule; check the named call, not only that an audit call exists. The new line `read_entry(session, user, rec)` sits after `rec.dose = dose`, so the audit row says READ and the change is never recorded.
Bad:
```python
def update_dose(session, user, rec, dose):
    rec.dose = dose
    read_entry(session, user, rec)       # the rule names the change-recording call
```
Good:
```python
def update_dose(session, user, rec, dose):
    old = rec.dose
    rec.dose = dose
    change_entry(session, user, rec.id, "dose", old, dose)
```
Not a defect when: the function only reads the record, so the read-audit call is the one that applies.

### Guidance comment violated by a change elsewhere in the file
- Tell: a comment says "order matters", "must run before" or a comment stating that consumers depend on a given sequence, and a hunk moves a line the comment protects.
- Fails when: the comment sits above `apply_rules(cfg)`. A change moves `fill_defaults(cfg)` above it. With `cfg = {}` and a rule that sets `timeout = 5`, the default `30` overwrites the rule value, and the output is 30.
Bad:
```python
# Order matters: apply_rules must run before fill_defaults.
cfg = fill_defaults(cfg)   # moved here by the change
cfg = apply_rules(cfg)
```
Good:
```python
cfg = apply_rules(cfg)
cfg = fill_defaults(cfg)
```
Not a defect when: the comment explains past behaviour and does not instruct, or the new order still satisfies the instruction. A requested change does not cancel a live invariant comment; only a change that edits or deletes the comment itself does. When the change contradicts a live comment, report it as comment-guidance (severity medium), with scenario: "comment requires X; change does Y; stated intent: <quote from the spec>". The owner decides whether the code or the comment changes; do not judge which wins.

### Process rule on the change itself: changelog line missing
- Tell: a user-visible change (new flag, new command, new config key) with no hunk in the changelog or the rule's second artifact.
- Fails when: CONTRIBUTING says each PR adds a changelog line under `## [Unreleased]`. The diff adds `--<new-flag>` and does not touch `CHANGELOG.md`, so the release notes miss it.
Bad:
```python
# diff adds: parser.add_argument("--<new-flag>", action="store_true")
# CHANGELOG.md: no hunk; [Unreleased] unchanged
```
Good: report the missing line with `code: CHANGELOG.md` and `quote: "none"` (no code line exists for an absence), quoting the CONTRIBUTING rule and the added flag; suggest the Added group.
Not a defect when: the change is test-only changes to existing tests, formatting or typo fixes (CONTRIBUTING names these), or the line already exists under `[Unreleased]`.

### Forbidden edit: a field the process rule says never changes
- Tell: a `+` or `-` diff line changes a field the rule forbids editing (for example `version` in a `plugin.json`).
- Fails when: CONTRIBUTING says "Do not edit `version` in any `plugin.json` or in `marketplace.json`", and the diff changes the version from 0.2.6 to 0.2.7.
Bad:
```json
-  "version": "0.2.6"
+  "version": "0.2.7"
```
Good: the version line is unchanged; the changelog line goes under `## [Unreleased]` instead.
Not a defect when: the change is the release step the maintainer asked for (a commit or PR titled `release X.Y.Z`, per the CONTRIBUTING release section).

### Two-file sync: a copy must match its source
- Tell: a rule says file A is copied to file B, or both must match, and the diff changes A without the same change to B, or the reverse.
- Fails when: CONTRIBUTING step 4 says root `SUBAGENTS.md` is copied to `plugins/haiku-delegation/templates/SUBAGENTS.md`, and the diff edits only the root file.
Bad:
```markdown
+ New rule text added to root SUBAGENTS.md
  (templates/SUBAGENTS.md: no matching hunk)
```
Good: the same added lines appear in `plugins/haiku-delegation/templates/SUBAGENTS.md`, or the two files are identical after the change.
Not a defect when: the rule names no copy, or the copy is identical to the source after the change (compare the files; do not assume).

### Rule about import-time side effects
- Tell: a module-level call that reads the environment, opens a connection, starts a thread or configures logging, in a module the rule says must import cleanly.
- Fails when: R12 says importing the package has no side effects. `client = Client(os.environ["API_KEY"])` at module level raises KeyError on import, so `--help` and test collection fail when the variable is unset.
Bad:
```python
import os
client = Client(os.environ["API_KEY"])   # runs at import
```
Good:
```python
def get_client():
    return Client(os.environ["API_KEY"])  # created on first call
```
Not a defect when: the import-time value is a literal, a frozen tuple or a compiled regex, or the rule covers only the entry point module.

### Rule written for tests only
- Tell: a rule scoped to `tests/` (no network, fixtures only) and a new test under `tests/` that breaks it.
- Fails when: R14 says tests make no network calls. The new test in `tests/test_sync.py` calls a live URL, so it fails offline and depends on a remote service.
Bad:
```python
# tests/test_sync.py (new)
def test_sync_ok():
    assert requests.get("https://api.example.com/health").ok
```
Good:
```python
def test_sync_ok(fake_api):
    assert fake_api.get("/health").ok
```
Not a defect when: the test file is outside `tests/`, or the call goes to a local fixture server that the rule allows.

### Required call removed by the change
- Tell: a `-` line in the diff deletes a call, check or record write that the rule requires, and no replacement line exists on that path.
- Fails when: R4 says every patient read calls log_access(). The diff deletes `log_access(user, pid)` and keeps `return db.get(Patient, pid)`.
Bad:
```python
- log_access(user, pid)
  return db.get(Patient, pid)
```
Good:
```python
log_access(user, pid)
return db.get(Patient, pid)
```
Not a defect when: the rule's scope no longer covers that path, or a replacement call on the same path satisfies the rule (read the new code to confirm).

## Known safe patterns

- A rule scoped to another directory: code that breaks the root wording is correct there, because the nested rule does not reach it.
- An explicit exemption that names the rule, a reason and an ID in the form the rule file accepts: the rule is waived on purpose.
- A TODO or explanation comment that mentions a rule but gives no instruction: it is not guidance.
- A wish ("code should be clear") with no checkable condition: it is not a rule you can apply.
- A rule that a formatter, linter or CI gate already enforces: the tool reports it, not guidance review.
- A helper with a different name from the rule wording that calls the required function on every path: the rule is met.
- A reorder that keeps the sequence the comment requires: the instruction still holds.
- A requested change does not cancel a live invariant comment; report the conflict for the owner and do not treat the requester's wording as a waiver.

## Do not report

- Rules you cannot quote with file, line and rule number.
- Violations on unchanged lines when a diff is given.
- Anything a linter, formatter or type checker enforces.
- General quality, style or security concerns that no rule names.
- Rule text the change does not reach (no hunk, no touched sibling, no moved line).
- Background prose in a rule file that has no checkable condition.

## Before you write a finding

1. Quote the rule line verbatim with its file path and rule number, and confirm its scope path covers the changed file. A paraphrase is not a quote.
2. Quote the code line that breaks the rule, and state the input or call order that reaches it.
3. Search the repo for the rule's required call, key or file, including name variants and wrappers. Confirm it is absent on that path.
4. Confirm the line is added, modified or moved by the change, and that no exemption in the rule file applies. Drop the finding if any step fails.
