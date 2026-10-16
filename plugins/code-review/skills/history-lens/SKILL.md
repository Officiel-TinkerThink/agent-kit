---
name: history-lens
description: "Focus-mode lens for commit-history intent checks. Preloaded into history-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: history-lens v1

# History Lens

Checks that each intent in the commit digest (fix, guard, limit, revert, review rule, ops dependency) still holds in the code after the change.
Every claim is classified PRESERVED, MOVED, EXPLAINED or REGRESSED, with evidence.

## How to look

1. Turn the digest into an intent list, one line per entry: fix, guard, limit with its reason, unit stated for a constant, parameter or config key, revert, review comment, ops dependency (a log or metric text that alerting uses).
2. For each entry, find its lines in the code after the change. Grep the identifier or the message text. Record `path:line` or `NOT FOUND`.
3. Check whether a later digest entry explains, replaces or re-authorises the intent before you call it REGRESSED. Digest entries are listed oldest first with date and hash; "later" means after the entry under review. If order or date is missing, do not claim EXPLAINED.
4. For a MOVED claim, list every branch and entry point that existed before the move (fast path, batch path, retry path, sibling function). Confirm each still reaches the new location. One missing branch makes it REGRESSED. If every branch reaches the new location, the classification is MOVED and there is no finding.
5. For limits and numbers, compare the new value with the ceiling or measurement quoted in the digest or review. Check units against the commit that changed them.
6. For a revert, or a revert of a revert, find why the value was changed and whether the digest gives a new reason. A plain revert of a fix with no reason in its message is REGRESSED.
7. For ops dependencies, grep the repo (alerts, dashboards, runbooks, tests) for the removed or changed text.
8. Read the author's description critically. "No behaviour change" or "within the ceiling" is a claim to check, not evidence.

## Catalog

### Guard removed
- Tell: an `if` check or `raise` on the input is deleted in the hunk, and no check replaces it on the same path.
- Fails when: a refund of a negative amount reaches `balance += amount` and debits the customer.
- Bad:
```python
# digest 3f9a2c1 "fix: reject non-positive refund amounts"
# hunk: -    if amount_cents <= 0: raise ValueError("amount must be positive")
def refund(account, amount_cents):
    account.balance += amount_cents   # -500 now debits the account
```
- Good:
```python
def refund(account, amount_cents):
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    account.balance += amount_cents
```
- Not a defect when: a schema model rejects the value before this call, or the caller checks the same rule on every path.

### Guard moved into a helper that one branch does not call
- Tell: a check moved into `_check()`, and another function still calls the sink `_write()` directly.
- Fails when: `save_many()` loops over records and calls `_write()` without `_check()`, so an empty `owner_id` is stored.
- Bad:
```python
# digest 7c01e9b "move record checks into _check()"; owner_id guard moved
# before: def save_many(recs): for r in recs: _check(r); _write(r)
def save(rec):
    _check(rec); _write(rec)
def save_many(recs):
    for r in recs: _write(r)   # _check() never runs here
```
- Good:
```python
def save_many(recs):
    for rec in recs:
        _check(rec)
        _write(rec)
```
- Not a defect when: every branch and entry point that existed before the move still calls `_check()`, or the batch was validated before the loop.

### Limit re-raised above a measured ceiling
- Tell: a constant or default is raised, and a review comment or commit message gives a measured ceiling for it.
- Fails when: 500 items hit the 30 s worker timeout the review measured (PR 412), so 1000 does too.
- Bad:
```python
# digest 9d4e7a0 "perf: raise import batch size to 1000"
# PR 412 review: "keep at 200; 500 hit the 30 s worker timeout"
BATCH_SIZE = 1000   # above the measured ceiling
```
- Good:
```python
BATCH_SIZE = 200   # measured: 500 exceeds the 30 s worker timeout (PR 412)
```
- Not a defect when: a later commit or PR records a new measurement that clears the ceiling (EXPLAINED), or the constant is used only with small test inputs.

### Revert of a revert restores a removed value
- Tell: a commit reverts a revert, and the restored value is the one an earlier revert removed for a stated reason, and the restoring commit gives no reason.
- Fails when: a 30 s vendor timeout returns after a revert that removed it because it stalled the connection pool.
- Bad:
```python
# digest 1a2b3c4 "raise vendor timeout to 30 s"   (A)
# digest 5e6f7a8 "Revert 1a2b3c4: stalls pool"    (B)
# digest 9b8c7d6 "Revert 5e6f7a8"                 (C)
VENDOR_TIMEOUT_S = 30   # after C; B removed this value for a stated reason
```
- Good:
```python
VENDOR_TIMEOUT_S = <value kept by 5e6f7a8>   # 9b8c7d6 gives no reason to restore 30 s; a re-raise needs a new measurement
```
- Not a defect when: the digest gives the reason for the second reversal, such as a fixed vendor, or the value is set through another path with its own measured limit.

### Unit confusion after a unit-changing commit
- Tell: a constant, parameter or config value changes unit (ms, s, bytes, items), or a commit, config key, constant name or author note states a unit, and the value after the change does not match it. A `*_MS` constant holding a value that a note gives in seconds is this case.
- Fails when: `wait(timeout=5000)` now waits 5000 s (about 83 minutes) because the callee expects seconds. Or `UPLOAD_TIMEOUT_MS = 3` is read in ms, so every upload times out after 3 ms when the author meant 3 s. Grep the consumer and state which unit it reads before reporting.
- Bad:
```python
# digest 2c4d6e8 "wait(): timeout is now seconds (was ms)"
# jobs/sync.py unchanged: wait(timeout=5000)
def wait(timeout: float):   # seconds since 2c4d6e8
    return _poll(timeout)
```
- Good:
```python
wait(timeout=5.0)   # seconds since 2c4d6e8; caller updated
```
- Bad, constant in the wrong unit (second pair):
```python
# digest 4b7e1d2 "config: UPLOAD_TIMEOUT_MS is in milliseconds"; author note: "3 s"
UPLOAD_TIMEOUT_MS = 3       # changed value; consumer reads ms
```
- Good:
```python
UPLOAD_TIMEOUT_MS = 3000    # 3 s as the note says; unit matches the name
```
- Not a defect when: the caller was updated in the same or a later commit, or the callee takes a typed value such as `timedelta`. For the constant case: the name, config key or commit was updated to the new unit in the same or a later commit, or the consumer takes a typed value.

### Removed log or alert message that operations depend on
- Tell: a log line or metric text is removed or changed, and an alert, dashboard or runbook in the repo matches it. Compare the text byte for byte; a changed suffix breaks an exact-match rule.
- Fails when: a lock loss is no longer logged, so the alert `sync: lock lost` never fires and the failure is silent.
- Bad:
```python
# digest 4e0f1a9 "tidy logging" removed log.error("sync: lock lost"); alerts/sync.yml matches it
def on_lock_lost():
    return abort()   # no log line; the alert cannot fire
```
- Good:
```python
def on_lock_lost():
    log.error("sync: lock lost")   # text kept verbatim: alerts/sync.yml matches it
    return abort()
```
- Not a defect when: the alert rule was updated in the same commit to match the new text, or the line is debug-level and no rule, dashboard or runbook names it.

### Contradicted review comment
- Tell: a review thread says "do not" or "must" about a code path, and the change does the opposite on that path.
- Fails when: an fsync per record is added after review asked for one fsync per batch, adding about 4 ms per record.
- Bad:
```python
# digest 8ab3c21 "write: durable per record" (subject only, empty body); PR 377 review: "do not fsync per record"
def write_records(f, records):
    for r in records:
        f.write(r)
        os.fsync(f.fileno())   # contradicts PR 377
```
- Good:
```python
def write_records(f, records):
    f.writelines(records)
    f.flush()
    os.fsync(f.fileno())   # one fsync per batch (PR 377)
```
- Not a defect when: the thread was resolved with a written reason (such as a new durability requirement), or the commit body (not the subject) gives a reason, or the per-record call sits on a path the comment excluded.

### Retry cap raised, authorised by a later commit (EXPLAINED)
- Tell: a retry or attempt cap is raised, and a later digest entry authorises the new value with a ticket or incident.
- Fails when: a reviewer reports REGRESSED and ignores the later entry that authorises 8 retries for INC-2231.
- Bad:
```python
# digest 6d2f8b0 "raise MAX_RETRIES 3 -> 8"
# digest 0c9e4d7 "retries: 8 allowed, INC-2231 needs outage tolerance"
MAX_RETRIES = 8   # reviewer error: reported as REGRESSED without reading 0c9e4d7
```
- Good:
```python
MAX_RETRIES = 8   # EXPLAINED by 0c9e4d7 (INC-2231); the write path is checked separately
```
- Not a defect when: always, as EXPLAINED. Only if the authorising entry covers just the read path is the write path a finding.

### Guard removed, replaced by a stronger common check (EXPLAINED)
- Tell: a guard is removed in one commit, and a later commit adds a check at a shared point (schema, constraint, decorator) that covers every path.
- Fails when: the replacement covers only some paths, so an unguarded path still accepts a negative quantity.
- Bad:
```python
# digest 5a7c3e1 "drop qty check in reserve(); DB constraint replaces it"
# digest 8f1d2b6 "migration 0042: CHECK (qty >= 0) on stock.qty"
def reserve(stock, qty):
    stock.qty -= qty   # reviewer error: flagged as unguarded without reading 8f1d2b6
```
- Good:
```python
def reserve(stock, qty):
    stock.qty -= qty   # negative result rejected at flush by CHECK (qty >= 0), 8f1d2b6
```
- Not a defect when: the later check covers every writer of the column. Confirm with a grep for other writers before classifying.

### Regression test removed or skipped
- Tell: a fix commit added a test; a later hunk deletes it, adds skip or xfail, or weakens its assertion, with no reason in the digest.
- Fails when: the test that reproduced the crash no longer runs, so the bug can return unseen.
- Bad:
```python
# digest 3c8f0a5 "fix: crash on empty cart" added test_empty_cart_checkout
@pytest.mark.skip(reason="flaky")
def test_empty_cart_checkout(): ...
```
- Good: the skip marker is removed and the assertion stays.
- Not a defect when: a later entry or the commit body records a fix for the flakiness, or the same assertion runs in another test file (grep).

### Default flipped back to an unsafe value
- Tell: a default changes to the value an earlier hardening commit changed away from (`verify=True` to `False`, `strict=True` to `False`).
- Fails when: TLS verification is off for every caller that takes the default.
- Bad:
```python
# digest 6e1a9d3 "security: verify TLS certificates by default"
def fetch(url, verify=False):   # default flipped back by this change
    return requests.get(url, verify=verify)
```
- Good:
```python
def fetch(url, verify=True):
    return requests.get(url, verify=verify)
```
- Not a defect when: a later entry or the commit body gives a reason, or every caller passes `verify` explicitly and the default is never used.

## Traps

- A guard moved to a caller that validates the same input on every path: enumerate the callers before calling it lost.
- A limit raised above a comment's ceiling when the same PR adds a new measurement: EXPLAINED by the new measurement.
- A function body deleted and re-added in another module with all branches reaching the sink: a pure move (MOVED, not a finding).
- A rename back to an earlier name: grep for callers that imported the intermediate name before classifying.
- Fewer retry attempts with a longer backoff and the same total wait, stated as intent in the digest: not a cap regression.
- A log text changed while the old text still exists in a second location that alerting matches: the dependency is preserved.

## Do not report

- General bugs with no link to a digest entry: other reviewers own them.
- A reversal the digest explains with a reason or a later measurement.
- Anything at all when no digest is given: state NO HISTORY AVAILABLE.
- Style, naming or formatting changes unrelated to a digest intent.
- Pre-existing problems on lines the change did not touch, even when the digest mentions the area.
- Security or design concerns, unless the digest states the intent that was lost; then report only the lost intent.
- Speculation about load or incidents that the digest does not mention.

## Before you write a finding

1. Quote the digest entry (commit id and subject) and the code line after the change.
2. Name the lost intent: the guard, limit, message, revert reason or review rule.
3. List the later digest entries that could explain or replace it. Confirm none does.
4. For MOVED, show that every branch and entry point reaches the new location, if one does not, it is REGRESSED; if all do, it stays MOVED and there is no finding.
5. State the failing input or sequence and the outcome, or drop the finding. Never report a missing digest as a finding.
