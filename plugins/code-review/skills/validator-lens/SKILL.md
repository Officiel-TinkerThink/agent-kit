---
name: validator-lens
description: "Focus-mode lens for re-checking a claimed defect. Preloaded into finding-validator; not for direct use."
user-invocable: false
---
LENS-MARKER: validator-lens v1

# Validator Lens

Decide whether a claimed defect is real by trying to refute it first.
A claim stands only when the walk from input to outcome reaches the claimed result and no guard on the way stops it.

## How to look

1. Re-state the claim in one sentence: file, line, input, claimed outcome. If the sentence cannot be written, the claim is not testable: UNVERIFIABLE.
2. Open the cited line and quote it. For a missing-code claim (quote none), find the function by name with search and read it whole. A missing quote is never a reason to refute.
3. Look for the refutation first: guard, bound, allowlist, parameter binding, constraint, requirement met elsewhere, a runtime validator on this path (Pydantic or schema model, database constraint), or a line outside a stated diff scope (only when the brief states one). A type annotation, a linter or a type-checker result is not a runtime guard.
4. Trace the input backwards to its source. Read each caller inside the given paths up to the entry point, note every validation, cast or default on the way, and name any caller or entry point outside them as unsearched.
5. Check the sibling: another route, function or branch that does the same job. If the sibling has the guard, the claim is stronger. If the sibling also lacks it, check whether a shared helper or decorator covers both.
6. In diff mode, check what the change removed or moved: a guard, a check, a lock, a timeout, an audit call. A moved guard is safe only when every path that used to hit it still reaches the new place.
7. Walk the scenario with the concrete input. Write each step and its result, one line per step. Stop at the first step a guard stops.
8. Check the layers the code may not show: decorators, middleware, router-level dependencies, database constraints and triggers, ORM defaults. If one of them could hold the guard and was not given to you, the verdict is UNVERIFIABLE, not CONFIRMED.
9. Confirm only when the walk reaches the claimed outcome. Score confidence with the rubric in the agent file.

## Catalog

Each entry: what a real instance looks like (Tell, Bad), when it fails, what confirms it, what refutes it, and when it is not a defect.

### Injection into a query
- Tell: SQL text built with an f-string, %, or + around a value that comes from a parameter or request.
- Fails when: a value with a quote character changes the statement structure, so the query returns rows the caller may not see.
```python
def find_user(conn, name):
    sql = f"SELECT id, email FROM users WHERE name = '{name}'"
    return conn.execute(sql).fetchall()
```
- Confirmed by: the interpolated value traces to an untrusted source (request, file, message) with no escaping, and the string reaches execute.
- Refuted by: placeholders (`?`, `%s`, `:name`) with values in the parameter tuple; identifiers taken from a constant allowlist dict only when a miss raises or returns a fixed value (`ALLOWED[key]` or `ALLOWED.get(key, "id")`); an int() cast before the value enters the string. `ALLOWED.get(key, key)` or any fallback to the raw input does not refute.
- Not a defect when: the f-string only builds placeholders, for example `",".join("?" * len(ids))`, and the values go in a bound tuple.

### Path traversal
- Tell: a file path built with os.path.join or + from a request value, with no realpath or commonpath check before open.
- Fails when: an absolute name discards the base (os.path.join semantics), or a name with parent segments reaches a file outside BASE_DIR.
```python
def read_upload(name):
    return open(os.path.join(BASE_DIR, name), "rb").read()
```
- Confirmed by: the name comes from an untrusted source and nothing between the join and the open confines the resolved path.
- Refuted by: realpath of the result followed by commonpath([BASE, real]) == BASE; a name matched by a fixed pattern with no separators; a server-generated name (uuid) as the only input.
- Not a defect when: the name is a literal in code, or it comes from a database lookup keyed by an integer id.

### Server-side request forgery
- Tell: an outbound HTTP call on a URL from input, with a host check but no check on redirects or on the resolved address.
- Fails when: an allowed host answers with a redirect to an internal address and the client follows it (requests follows GET redirects by default).
```python
def fetch(url):
    if urlparse(url).hostname not in ALLOWED_HOSTS:
        raise ValueError("host not allowed")
    return requests.get(url, timeout=5).text
```
- Confirmed by: the URL is untrusted, redirects are not controlled (allow_redirects false or a per-hop check), and the address is not checked at connect time.
- Refuted by: (allow_redirects=False or every hop re-validated against the allowlist) AND the resolved address checked against private ranges at connect time. A host check with redirects disabled does not refute on its own: an allowed name can resolve to an internal address.
- Not a defect when: the URL is a constant, or is built only from a configured base URL plus a validated integer id.

### Missing authorisation on a route
- Tell: a route or verb that reads or changes an object by id with no ownership or role check in the body.
- Fails when: user A changes the object of user B, because the id is the only key the query uses.
```python
@router.delete("/orders/{order_id}")
def delete_order(order_id: int, user=Depends(current_user)):
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
```
- Confirmed by: no ownership filter in the query, no check in a decorator or router-level dependency that covers this route, and a sibling route on the same object does check (this strengthens the claim).
- Refuted by: a `WHERE owner_id = ?` (or equivalent) whose value comes from the authenticated session, not from the request; a role or ownership check in a router-level dependency (an authentication-only dependency such as `current_user` does not count); a middleware rule covering this verb and path.
- Not a defect when: the specification makes the object public, or the endpoint returns only data the caller already holds.

### Audit event missing
- Tell: a write to a regulated table in a function that never calls the audit helper.
- Fails when: a regulated record changes with no audit row in the same transaction, so the change cannot be attributed or reconstructed.
```python
def set_limit(session, limit_id, value):
    rec = session.get(DoseLimit, limit_id)
    rec.value = value
    session.commit()
```
- Confirmed by: the table is named as regulated by the specification or project guidance, no audit call sits on this path, no ORM event listener or session hook writes it (search for `listens_for`, `event.listen`, `before_flush`, `after_flush`), and a sibling update path does write the event (search for the helper name).
- Refuted by: an audit helper call in the function or in a caller that wraps every path; a database trigger on the table shown in a migration; an ORM event listener or session hook on the model that writes the audit row (`before_flush`, `after_flush`, `after_update`), shown in code; the write shares a unit of work that records the audit.
- Not a defect when: the table is not regulated (cache, session, counter, log), or the change is a read-only refresh.

### Race on check-then-act
- Tell: a value read, compared in Python, then written back with a separate statement and no lock or conditional write.
- Fails when: two callers read a stock of 5, both pass a check for 5, both write, and two reservations succeed.
```python
def reserve(conn, sku, qty):
    left = conn.execute("SELECT qty FROM stock WHERE sku = ?", (sku,)).fetchone()[0]
    if left >= qty:
        conn.execute("UPDATE stock SET qty = ? WHERE sku = ?", (left - qty, sku))
```
- Confirmed by: two concurrent callers reach the function (threads, workers or request handlers; a route handler that serves concurrent requests counts as concurrent without a separate config proof), and no lock, unique constraint or conditional UPDATE covers both the read and the write.
- Refuted by: `UPDATE stock SET qty = qty - ? WHERE sku = ? AND qty >= ?` with a rowcount check; `SELECT ... FOR UPDATE` inside the transaction; a single writer proven in code or deployment config (if that proof is not in the code given, UNVERIFIABLE).
- Not a defect when: the read feeds a report with no write, or the code runs once at startup.

### Unsafe retry
- Tell: a retry loop around a non-idempotent call (POST or any side effect) with no idempotency key.
- Fails when: a timeout after the server applied the write, followed by a retry, creates a duplicate record.
```python
for _ in range(5):
    try:
        return client.post(url, json=body)
    except httpx.TransportError:
        time.sleep(1)
```
- Confirmed by: a non-idempotent method, no Idempotency-Key or equivalent in the request, and the contract (code or specification) does not deduplicate.
- Refuted by: retry only for GET or for PUT of full state; an Idempotency-Key header that the server stores and deduplicates. A retry budget, a deadline or a single retry layer does not refute it: they limit duplicates, they do not prevent them.
- Not a defect when: the call is a read, or the only issue is a fixed sleep with no jitter in one caller (jitter matters only when many callers are shown to synchronise).

### Resource leak on the error path
- Tell: an open or acquire, then a call that can raise, then the close, with no `with` block or finally.
- Fails when: the call between open and close raises; the handle stays open and buffered data is lost.
```python
def export(path, rows):
    f = open(path, "w")
    for row in rows:
        f.write(serialize(row))
    f.close()
```
- Confirmed by: a failable call sits between acquire and release, the error path does not release, and the caller does not own the close (read the caller).
- Refuted by: a `with` statement; try/finally with the release; a returned handle the caller is shown to close.
- Not a defect when: the release is in finally, or the object is a context manager.

### Rounding mode
- Tell: `quantize` (or a similar rounding call) with no rounding argument and no local context, where the requirement names a mode.
- Fails when: the requirement says half up and a product of exactly 0.125 quantized to cents uses the default half-even rule, giving 0.12, not 0.13.
```python
from decimal import Decimal
def fee(amount: Decimal) -> Decimal:
    return (amount * Decimal("0.125")).quantize(Decimal("0.01"))
```
- Confirmed by: the requirement names the mode, the call passes no rounding argument, and no context in scope sets one.
- Refuted by: `rounding=ROUND_HALF_UP` on the call; a `localcontext()` with rounding set; the requirement names half-even, or names no mode and the project documents the default.
- Not a defect when: the requirement names no rounding rule, or the value is an integer count with no fractional part.

### Window boundary
- Tell: a half-open comparison (`start <= x < end`) where the end is a date the requirement says is included.
- Fails when: a record dated on the end day is dropped from a result that the specification says includes that day.
```python
def in_period(day, start, end):
    return start <= day < end
```
- Confirmed by: the requirement says the end is inclusive, and the caller passes the end date with no +1 day adjustment (read the caller).
- Refuted by: the caller passes end plus one day; the comparison is `<= end`; the requirement states a half-open interval.
- Not a defect when: the requirement is half-open, or the caller has already shifted the end (show the shift).

### Falsy zero treated as missing
- Tell: `x or default` or `if not x:` on a value where 0, an empty string or an empty list is a legal input.
- Fails when: `requested=0` returns the default 25, while the requirement says 0 must be kept or rejected.
```python
def page_size(requested):
    return requested or 25
```
- Confirmed by: the requirement or a test distinguishes 0 from missing, and the code tests truthiness on that value.
- Refuted by: an `is None` test; 0 rejected by an earlier validator on the same path (trace it); the requirement says 0 means default.
- Not a defect when: the requirement treats 0, empty string and empty list alike as missing, or the value cannot reach 0 after validation.

### Wrong exception type
- Tell: a raise of a type that differs from the type the contract or the caller's except clause names.
- Fails when: an out-of-range value raises TypeError where the contract says ValueError, so `except ValueError` misses it and the request returns 500.
```python
def parse_qty(raw):
    if not isinstance(raw, int):
        raise TypeError("qty must be int")
    if raw < 0:
        raise TypeError("qty must be >= 0")
```
- Confirmed by: the contract (specification or a caller's except clause) names the type, the raise on that path uses another type, and the caller relies on it.
- Refuted by: a custom exception that subclasses the named type (read the class); the caller catches both; no contract names a type.
- Not a defect when: no contract names the type, or the raised class is a subclass of the expected one.

### Regression of a guard
- Tell: a removed or moved check (raise, return, validation) in the diff, with the same sink still reachable.
- Fails when: a negative amount reaches the debit and credit calls and reverses the transfer.
```diff
-    if amount <= 0:
-        raise ValueError("amount must be positive")
     debit(src, amount)
     credit(dst, amount)
```
- Confirmed by: the guard exists in the base revision (the removed line), the new code has no equivalent on every path that reaches the sink, and the input reaches the sink unvalidated.
- Refuted by: the same check in a helper every path calls (debit calls a check function); a stronger check that replaces it; a schema validator on an entry point that all callers use.
- Not a defect when: the guard moved to an entry point every caller uses, shown by searching all callers.

### Simplification that is not identical
- Tell: a finding with `simpler:` and `same behaviour:` lines that proposes `x or default`, `return cond`, `any(...)`, `next(...)`, a merged duplicate, a removed wrapper or a removed try/except.
- Fails when: the simpler form differs on one input the original handles: `limit or 50` turns an explicit 0 into 50, `return cond` loses a non-bool value, `next(...)` drops a per-item log call, a merged validator loses a `<` versus `<=` boundary, a removed `except ... from exc` changes the exception type callers catch.
Bad:
```python
limit = requested if requested is not None else 50
limit = requested or 50              # proposed: differs for requested = 0
```
Good:
```python
limit = requested if requested is not None else 50
```
Not a defect when: the simpler form matches on every input the code can receive, including exceptions and side effects; then CONFIRMED, at 75 if one differing input cannot occur.

## Safe-pattern refutation table

| Safe pattern | Refutes | Check that it is correct |
|---|---|---|
| `?`, `%s` or `:name` placeholders with bound values | Injection into a query | Values are in the tuple, not in the string |
| Identifier taken from a constant dict | Injection into ORDER BY or column names | The key is validated against the dict |
| `int()` cast before the value is used in a string | Injection | The cast happens before the string is built |
| `realpath` plus `commonpath([base, real]) == base` | Path traversal | Compared on the resolved path, not the raw name |
| `allow_redirects=False` or a per-hop allowlist | SSRF via redirect | Address also checked at connect time |
| `secrets.compare_digest` or `hmac.compare_digest` | Timing leak on a secret compare | Used on the secret, not on a public id |
| `WHERE owner_id = ?` in the query | Missing authorisation | Owner comes from the session, not the request |
| Conditional UPDATE with a rowcount check | Race on check-then-act | The rowcount is checked and handled |
| `SELECT ... FOR UPDATE` in the transaction | Race on check-then-act | The lock is held across read and write |
| Idempotency-Key checked by the server | Unsafe retry | The server stores and deduplicates the key |
| `with` or try/finally around the handle | Resource leak | Release happens on every path |
| `quantize(..., rounding=ROUND_HALF_UP)` | Rounding mode | The same mode on every money path |

## Traps

- `f"... {placeholders}"` where `placeholders` is only `?` marks: the values are bound, so there is no injection.
- `os.path.join(BASE, "literal.json")`: no input reaches the name, so there is no traversal.
- `UPDATE t SET n = n + ?` is one atomic statement, but it is a race when a separate earlier read or check decides whether to run it. Refute only when the decision and the write are one conditional statement (`... AND qty >= ?`) with a rowcount check.
- `with open(...)` or try/finally: the handle is released even when `serialize` raises.
- `except Exception as exc: raise DomainError(...) from exc` keeps the cause: it is not a swallowed exception.
- `requests.get(url, timeout=5)` on a constant URL: no untrusted input, so no SSRF.
- `Decimal(str(value))` is the shortest decimal that round-trips to the float, not the float's exact binary value; it avoids the long binary expansion that `Decimal(value)` shows.
- `start <= day < end` is correct when the requirement is half-open.
- `raise TypeError` for a wrong Python type is correct when the contract names TypeError.
- A dict written only at import time is not mutable state shared at runtime.

## Do not

- Confirm because a pattern looks risky. A claim needs the walk.
- Confirm style, naming or readability points: refute them as REFUTED, REASON NOT A DEFECT.
- Refute because the quote is none. Search and read the function instead.
- Refute on scope only when the brief states a change scope. With `Change scope: diff <path>`, a flaw on a line outside that diff is REFUTED with REASON NOT A DEFECT (pre-existing, out of scope) and CONFIDENCE 0. With `whole-file`, the whole file is in scope. Without a stated scope, never refute on scope.
- Treat a guard you cannot see as present or absent: mark it UNVERIFIABLE.
- Widen the claim beyond the cited line and input, or add new findings.
- Print credential values, tokens or connection strings, even to show a refutation.
- Accept a comment, a name or a passing test as proof that a guard works.

## Before you write a verdict

1. Did I quote the cited line (or search the function for a missing-code claim) and restate the claim in one sentence?
2. Did I look for the refutation before the confirmation, in the function, its callers, the sibling and the framework layer?
3. Can I write each step of the walk with the concrete input and its result, ending at the claimed outcome?
4. Is every guard I relied on in code I was given? If a guard could live in code I was not given, is the verdict UNVERIFIABLE?
5. Is the claim inside its stated scope (diff lines or whole file), and does the confidence match the rubric?
