---
name: defect-lens
description: "Focus-mode lens for behavioural defects: wrong results on reachable paths, boundary and empty-value errors, state changes, retries, concurrency and resources that fail when a call fails, a process dies or a second actor runs. Preloaded into defect-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: defect-lens v1

# Defect Lens

Finds code that is correct on the happy path and wrong on a path a real caller can take: a boundary input, a missing value, a call that fails, a process that dies, or a second actor that runs.
Work from the failure sequence: every finding names the state left behind and the input or interleaving that leaves it.

## How to look

1. List every state-changing call in each changed function in source order (DB write, publish, HTTP call, file write, cache set, lock, release). For each adjacent pair, write what remains if the process dies or the second call raises.
2. For each retry loop, find every other retry around the same call: caller, decorator, client library, queue redelivery. Count the worst-case attempts.
3. For each read-then-write on shared state, name one concrete second actor (other thread, worker, request, scheduler). Drop the candidate if you cannot name one.
4. For each external call and each acquired resource, check the bound: timeout, deadline, close or release on every exit path.
5. Check the SIBLING: the function next to the changed one that does the same kind of write, lock or release. If the sibling uses a transaction, finally or version check and the changed one does not, that is evidence.
6. Check what the change REMOVED (lock, timeout, finally, version check, dedupe key, limit, retry cap) and what it did NOT touch but depends on (callee retry policy, queue delivery, cache TTL, config default). Trace one concrete failing input through the path without the guard and write the outcome; drop the candidate if the trace cannot reach it.

## Catalog

### Dual write without outbox
- Tell: a DB commit followed by a broker, HTTP or file write, with no shared transaction and no outbox row; or a publish inside the transaction block, before the commit (consumers then act on a row that may roll back).
- Fails when: save() commits, then publish() raises or the process dies. The order exists, the event never leaves, and downstream never sees it.
- Bad:
```python
def place_order(db, broker, order):
    db.save(order)                             # committed
    broker.publish("order.placed", order.id)   # lost if this raises
```
- Good: insert an outbox row in the same transaction as the order; a relay publishes committed rows and retries until acknowledged.
- Not a defect when: the event is a best-effort hint the spec says may be lost, or the path already writes to an outbox table.
### Non-idempotent consumer under at-least-once delivery
- Tell: a message handler that adds, appends or sends, with no processed-id check or unique key.
- Fails when: the broker redelivers after a slow ack; the handler credits the same amount twice.
- Bad:
```python
def handle(msg, repo):
    acct = repo.get(msg.account_id)
    acct.balance += msg.amount     # runs again on redelivery
    repo.save(acct)
```
- Good: in the same transaction as the balance change, `INSERT INTO processed_msg(msg_id) VALUES (%s) ON CONFLICT DO NOTHING`; rowcount 0 means skip. Do not SELECT the id first and INSERT after: concurrent redeliveries both pass a SELECT (check-then-act).
- Not a defect when: the handler writes an absolute value (balance = msg.new_balance) or a keyed upsert whose repeat is a no-op.
### Retry amplification
- Tell: a retry at more than one layer, a fixed sleep, no jitter, or no overall deadline or budget.
- Fails when: the inventory service is slow for 60 s; each order makes 5 client attempts times 5 handler attempts at a fixed 2 s interval, so load multiplies when the service is weakest.
- Bad:
```python
@retry(attempts=5, sleep=2)   # client layer; the caller in the order handler adds retry(attempts=5) too: up to 25 attempts
def call_inventory(body): return http.post(INV_URL, json=body, timeout=5)
```
- Good: retry at one layer only, with exponential backoff, full jitter and a total deadline shared by all attempts. Retry a POST only with an idempotency key (`Idempotency-Key` header, same value on every attempt); a non-idempotent POST without a key is not retried at all.
- Not a defect when: the layers retry different error classes (one retries connection errors, the other only 503 after a deadline check), or the total attempts are bounded and jittered.
### Check-then-act on shared state
- Tell: SELECT or read, then a comparison, then a separate UPDATE or write, with no lock, unique constraint or conditional UPDATE.
- Fails when: two requests read stock = 1 and both pass the check; both write stock = 0; two orders are accepted for one item.
- Bad:
```python
row = db.execute("SELECT stock FROM sku WHERE id=%s", (sku,)).fetchone()
if row.stock >= qty:
    db.execute("UPDATE sku SET stock=%s WHERE id=%s", (row.stock - qty, sku))
```
- Good: `UPDATE sku SET stock = stock - %s WHERE id = %s AND stock >= %s` and treat rowcount != 1 as a refusal.
- Not a defect when: the read and write sit in one transaction with SELECT ... FOR UPDATE, or a single-writer worker with a documented guarantee is the only caller.
### Lost update
- Tell: a value read into Python, changed in Python, and saved back as an absolute value.
- Fails when: two workers read 10, both save 11; one increment is lost with no error.
- Bad:
```python
c = repo.get(key)
c.value = c.value + 1     # read in Python
repo.save(c)              # absolute write
```
- Good: `UPDATE counter SET value = value + 1 WHERE key = %s`, or an optimistic version column checked in the WHERE clause.
- Not a defect when: the statement is already `value = value + ?` in SQL (atomic), or the object is process-local and never shared.
### Write skew
- Tell: a transaction checks an invariant over a set of rows (count, sum, "at least one remains") and then writes one of those rows.
- Fails when: under READ COMMITTED two doctors each see two on call, both go off call, and zero remain.
- Bad:
```python
if db.scalar("SELECT count(*) FROM doctors WHERE on_call") > 1:
    db.execute("UPDATE doctors SET on_call = false WHERE id = %s", (doc_id,))
```
- Good: run the check and write at SERIALIZABLE with a retry loop on SQLSTATE 40001; or, when the set cannot grow in the same window, `SELECT id FROM doctors WHERE on_call FOR UPDATE` and count the returned rows in Python (`count(*)` cannot be combined with FOR UPDATE).
- Not a defect when: the invariant involves one row only, or the isolation level is SERIALIZABLE with a retry loop already present.
### Lock with TTL and no fencing token
- Tell: a distributed lock with an expiry, and writes after the lock is taken with no token or version check.
- Fails when: a GC pause or slow step passes the TTL; a second worker takes the lock and writes; the first worker resumes and overwrites the result.
- Bad:
```python
if redis.set("job:lock", worker_id, nx=True, ex=30):
    slow_step()        # can exceed 30 s
    write_result()     # stale holder writes after expiry
```
- Good: take a monotonically increasing fencing token with the lock and have the storage reject any write carrying an older token.
- Not a defect when: the lock guards a read-only cache refresh, or the write is conditional on a version column that the stale holder cannot match.
### Missing timeout on outbound call
- Tell: a `requests`, `urllib`, raw socket, or DB/queue client call with no timeout argument and no timeout set on the client or session (these libraries have no default timeout). Skip httpx (default 5 s) unless the diff sets `timeout=None`. Also not a defect: a fixed third-party URL constant that is identical in every environment (hardcoded hosts are covered by the architecture lens).
- Fails when: the peer accepts the TCP connection and never answers; the worker blocks forever and the pool drains to zero.
- Bad:
```python
resp = requests.get(url)     # no timeout: blocks indefinitely
data = resp.json()
```
- Good: `requests.get(url, timeout=(3.05, 10))` with values read from settings.
- Not a defect when: a session or wrapper applies a default timeout and the diff does not bypass it (read the wrapper first), or the call is in-process.
### Resource leak on error path
- Tell: open, acquire or connect, then use, then close as a plain statement at the end of the function.
- Fails when: parse() raises on bad input; each bad request leaks a file descriptor until the process hits EMFILE.
- Bad:
```python
f = open(path, "rb")
data = parse(f.read())     # raises: f is never closed
f.close()
```
- Good: `with open(path, "rb") as f: data = parse(f.read())`, or try/finally when the handle outlives the block.
- Not a defect when: the caller takes ownership by documented contract, or the handle lives for the whole process by design.
### Cache stampede
- Tell: a get, a miss branch that recomputes, and a set with a fixed TTL, with no single-flight lock and no jitter.
- Fails when: the key expires; 500 concurrent requests miss together and call the 2 s upstream at once; the upstream rate-limits the service.
- Bad:
```python
v = cache.get("rates")
if v is None:
    v = fetch_rates()             # every concurrent miss runs this
    cache.set("rates", v, ex=60)  # all keys expire together
```
- Good: a single-flight lock so one caller recomputes while others wait or serve the stale value, or stale-while-revalidate. A jittered TTL such as `ex=60 + random.randint(0, 10)` only spreads expiry across many keys; it does not stop concurrent misses on one key.
- Not a defect when: a scheduled job warms the key and the miss branch is unreachable in normal operation, and the diff does not change that.
### Unbounded growth
- Tell: a dict, list or queue that gains keys from request input and never evicts or caps.
- Fails when: an attacker sends requests from many distinct client keys; the dict grows until the worker runs out of memory.
- Bad:
```python
hits = {}
def track(client_ip):
    hits[client_ip] = hits.get(client_ip, 0) + 1   # never evicted
```
- Good: a bounded structure with eviction: `cachetools.LRUCache(maxsize=N)`, or an OrderedDict with explicit eviction (set `d[k] = v`, call `d.move_to_end(k)`, then while `len(d) > N` call `d.popitem(last=False)`); a store with TTL; or `queue.Queue(maxsize=N)` for queues.
- Not a defect when: the keys come from a fixed enumeration (for example the twelve month names), or the dict is built per request and discarded.
### Partial failure with no compensation
- Tell: a sequence of external side effects (charge, reserve, send) with no compensating action for a failure after the first one.
- Fails when: reserve() raises out of stock after charge() captured the money; the customer is charged and no order exists.
- Bad:
```python
payments.charge(cart.user, cart.total)     # money captured
inventory.reserve(cart.items)              # raises: no stock
orders.create(cart)
```
- Good: reserve first, charge second, and release the reservation when the charge fails; or record a saga step with a durable compensation.
- Not a defect when: the charge is an authorisation that a void runs on every later exception (check the handler), or the steps are already reserve, charge, create with compensation in place.
### Swallowed exception feeding a normal path
- Tell: a broad except that returns a default value, and the default is a legal value for the caller.
- Fails when: the config store times out; the function returns 0; downstream reads 0 as "no limit", so one timeout removes the limit for every user.
- Bad:
```python
def load_limit(key):
    try:
        return int(config_db.get(key))
    except Exception:
        return 0     # 0 means "no limit" downstream
```
- Good: let the exception propagate, or raise a domain error `from exc`; return a sentinel only when every caller checks for it.
- Not a defect when: the fallback is a documented neutral value on an enrichment path where a missing value has no safety effect, and the failure is logged with context; or the handler logs a cleanup failure and re-raises the original exception (a rollback is not swallowed).
### Hidden mutable global state
- Tell: a module-level variable written at runtime (inside a function with `global`, or by attribute assignment) and read by request-handling code.
- Fails when: two requests interleave on one worker; request B sets the tenant, then request A's query runs with B's tenant; data crosses tenants.
- Bad:
```python
def set_tenant(t):
    global _tenant
    _tenant = t
def query(sql):
    return db.run(sql, tenant=_tenant)
```
- Good: pass the tenant as an argument, or store it in a `contextvars.ContextVar` set per request.
- Not a defect when: the global is loaded once at import and never reassigned, or it is a ContextVar.
### Temporal coupling
- Tell: a method reads state that only another method sets (self._rows set in load()), with no guard or error for the wrong call order.
- Fails when: export() runs before load(); the caller gets an AttributeError with no domain message, or stale data when load() ran earlier.
- Bad:
```python
class Report:
    def load(self): self._rows = fetch()
    def export(self):
        return to_csv(self._rows)    # AttributeError if load() not called
```
- Good: pass the rows to the constructor, load inside export(), or raise a domain error when the object is not loaded.
- Not a defect when: a factory always calls load() and every caller in the repo goes through that factory (check the callers).
### Ignored parameter
- Tell: a parameter in the signature (dry_run, force, timeout) that the body never reads.
- Fails when: the caller passes dry_run=True to preview; the rows are deleted anyway.
- Bad:
```python
def purge(ids, dry_run=False):
    for i in ids:
        store.delete(i)      # dry_run is never read
```
- Good: `if dry_run: return len(ids)` before the loop, or remove the parameter if it is not part of the contract.
- Not a defect when: the signature is fixed by a framework hook or an interface the change cannot alter, and the docstring says it is unused.
### Clock skew across hosts
- Tell: a timestamp written by one host and compared with time.time() or datetime.now() on another host for expiry or ordering.
- Fails when: the writer's clock is 3 s ahead; a lease looks valid for 3 s after it expired; two workers hold the same lease.
- Bad:
```python
def lease_valid(expires_at):
    return time.time() < expires_at     # expires_at set by another host
```
- Good: take the expiry comparison on one clock (the database `now()` or a lease service), or subtract an explicit, documented skew margin.
- Not a defect when: both timestamps come from one process, or time.monotonic() measures a local interval.
### Multi-step write without transaction
- Tell: two or more writes in one function, each committed separately, where the second write uses the id of the first.
- Fails when: insert_order() commits and insert_lines() raises; an order with no lines exists and downstream reads it as complete.
- Bad:
```python
oid = db.execute("INSERT INTO orders (total) VALUES (%s) RETURNING id", (total,)).scalar()
db.commit()
db.executemany("INSERT INTO lines (order_id, sku) VALUES (%s, %s)", [(oid, s) for s in skus])
db.commit()
```
- Good: one transaction (`with db.begin():`) around both writes, so both commit or neither does.
- Not a defect when: one statement writes both (a CTE), or the second write does not depend on the first.
### Lock release without owner check
- Tell: `redis.delete(key)` or DEL in a finally block, without comparing the stored value to this holder's token.
- Fails when: the lock expires during slow_step; worker B takes it; worker A's finally deletes B's lock; worker C takes it; two holders run.
- Bad:
```python
if redis.set("job:lock", worker_id, nx=True, ex=30):
    try:
        slow_step()
    finally:
        redis.delete("job:lock")   # may delete another holder's lock
```
- Good: release atomically only when the value matches the token: `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) end` (Lua, EVAL).
- Not a defect when: nothing else is guarded by the lock and the expiry is the only release path.
### Mutable default argument
- Tell: a parameter whose default is a mutable literal (`[]`, `{}`, `set()`) that the body changes.
- Fails when: the default object is created once at definition time; a later call without the argument receives the items added by earlier calls, so one request sees another request's data.
- Bad:
```python
def add_tag(item, tags=[]):
    tags.append(item)     # shared list across calls
    return tags
```
- Good: `def add_tag(item, tags=None):` then `tags = [] if tags is None else tags`.
- Not a defect when: the default is an immutable value (tuple, frozenset, None) or the body never mutates it.
### Unbounded loop
- Tell: a `while True` or retry loop with no attempt count, deadline or shutdown condition, or one that retries with no sleep.
- Fails when: the upstream stays down; the loop spins at full CPU, holds a connection or worker slot, and never returns; the process cannot shut down cleanly.
- Bad:
```python
while True:
    try:
        return fetch_status()
    except ConnectionError:
        time.sleep(0.1)   # no limit, fixed sleep
```
- Good: a bounded attempt count or deadline, exponential backoff with jitter, and a shutdown event checked on each pass (`stop.wait(delay)`).
- Not a defect when: the loop iterates a finite collection, or it is a daemon poll loop whose exit is the stop event.
### Non-atomic file write
- Tell: `open(path, "w")` (or `write_text`) on the live file that another process or the next start reads.
- Fails when: the process dies after the open truncates the file and before the write completes; the next start reads an empty or partial file as valid state.
- Bad:
```python
with open(state_path, "w") as f:
    f.write(json.dumps(state))
```
- Good: write to a temp file in the same directory, `flush()` and `os.fsync()`, then `os.replace(tmp_path, state_path)`.
- Not a defect when: the file is a scratch file rebuilt on every start, or the write is already the atomic rename above.
### Float used for money or dose rounding
- Tell: `round(x, 2)`, `int(x * 1000)` or a float product feeding a limit, a label or a total where the intent names a rounding mode or an exact unit.
- Fails when: `round(0.125, 2)` gives 0.12 (the exact tie rounds to even) where half-up needs 0.13; `int(1.001 * 1000)` gives 1000; two paths round at different steps so a label total and an API total differ by more than the stated tolerance.
- Bad:
```python
price = round(unit_price * qty, 2)     # float: ties round to even
```
- Good: `Decimal(str(unit_price)) * qty` then `.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
- Not a defect when: the code uses `Decimal` with `quantize` and an explicit rounding mode, or the value is an integer count.
### Wall-clock arithmetic across DST or for a duration
- Tell: `aware_local + timedelta(hours=24)`, naive `datetime.now()` compared with aware stamps, or `time.time()` differences used as elapsed time.
- Fails when: a daily 02:00 local job moves to 03:00 after a DST change; a naive and an aware value meet and the `TypeError` is caught and treated as "not expired".
- Not a defect when: both sides are aware UTC, or the code converts to local time only for display.
### Offset pagination over a non-total order
- Tell: `ORDER BY created_at` (or a sort key with ties) plus `OFFSET`/slicing, or a loop that stops on `len(page) < size` before writing that page.
- Fails when: rows with equal timestamps swap places between pages, an insert repeats a row and a delete skips one; the last partial page is dropped.
- Bad:
```python
page = db.execute("SELECT id, created_at FROM events ORDER BY created_at LIMIT %s OFFSET %s", (size, offset))   # ties on created_at
```
- Good: order by `(created_at, id)` and walk with a keyset condition on that pair.
- Not a defect when: the key ends in a unique id, or the walk is keyset-based on the full key.
### Late-binding closure in a loop
- Tell: `lambda: f(name)` or a nested function appended inside `for name in ...` that reads the loop variable later.
- Fails when: every callback sees the last value of `name`.
- Bad:
```python
handlers = []
for name in names:
    handlers.append(lambda: run(name))   # every handler sees the last name
```
- Good: `handlers.append(lambda name=name: run(name))` or `functools.partial(run, name)`.
- Not a defect when: the value is bound as a default argument (`lambda n=name: f(n)`) or with `functools.partial`.
### Number parsing that guesses the separator
- Tell: `float(s.replace(",", "."))`, locale-dependent `float()`, or a regex that accepts any digit run.
- Fails when: `"1,234"` becomes 1.234 instead of 1234, `"1,234.5"` raises, or a value with a different grouping is accepted silently.
- Not a defect when: the format is fixed and validated first, or `Decimal(text)` rejects everything but the stated format.
### Counter or id masked to a fixed width
- Tell: `n & 0xFF`, `n % 256`, `{n:02X}` or a fixed-width suffix on a counter that can exceed the width.
- Fails when: the 257th item gets the same id as the first, and the duplicate is not detected.
- Not a defect when: the code raises at the limit or the width covers every value the caller can produce.
### Non-finite number accepted by validation
- Tell: `if x < 0: raise` or `if x > MAX: raise` on a float that can be NaN or infinity.
- Fails when: `nan < 0` and `nan > MAX` are both False, so NaN passes and reaches a label or a total; an ordering comparison on `Decimal("NaN")` raises `InvalidOperation` instead of the documented error.
- Bad:
```python
if amount < 0 or amount > MAX:      # NaN passes both tests
    raise ValueError("amount out of range")
```
- Good: `if not math.isfinite(amount) or amount < 0 or amount > MAX: raise ValueError(...)`.
- Not a defect when: the value comes from an integer parse, or `math.isfinite` is checked first.
### Wrong result on a reachable path
- Tell: a branch, boundary, default or null path that returns a value the caller's use of it contradicts (for example an implicit `None` return that the caller does arithmetic on). Cite the caller line and the returning line; trace one concrete input.
- Fails when: a boundary input (zero, empty, equal to the limit, missing key) reaches the return the caller misreads; the caller computes a wrong total or raises on the normal path.
- Bad:
```python
def discount_rate(total):
    if total > 100:
        return 0.1
    # total <= 100 falls through and returns None

def net(total):
    return total * (1 - discount_rate(total))   # TypeError for total <= 100
```
- Good: an explicit `return 0.0` on the fall-through path, matching what the caller expects.
- Not a defect when: the caller checks for None before use, or the expected value for that input is not stated by the intent or by any caller (record it under UNCLEAR, with the input and the caller line).
### Off-by-one at a boundary
- Tell: a comparison or range whose inclusive or exclusive end differs from the intent (`<` where `<=` is meant, `range(n)` for n items plus one, slice ends, `len(x) - 1` used as a count).
- Fails when: a charge of exactly the limit is refused, or the last element of a list is never processed; the input at the boundary is a normal value, not an edge case.
- Bad:
```python
def within_limit(amount, limit):
    return amount < limit      # limit itself is refused
```
- Good: state the intended inclusion in the name and the code (`amount <= limit`) and test the boundary value.
- Not a defect when: the intent or the spec says exclusive, or the boundary value cannot reach the code (a validator above rejects it).
### None or empty value on a reachable path
- Tell: an attribute access, index, `[0]`, `first()`, `max()` or `min()` on a value that can be None or empty on a path the caller takes.
- Fails when: `max([])` raises, or `row.name` runs on a `fetchone()` that returned None for an unknown id; the request returns a 500 instead of the domain error.
- Bad:
```python
row = db.execute("SELECT name FROM users WHERE id=%s", (uid,)).fetchone()
return row.name           # None for an unknown id
```
- Good: check for None before use and raise the domain error (`UserNotFound`), or use the value only after the empty case is handled.
- Not a defect when: a guard above the line already excludes the empty case (cite it), or the value is non-optional by the schema and the schema is enforced at this boundary.
### Unit or type confusion
- Tell: two values of different units or types combined without conversion (seconds with milliseconds, cents with units, a string from a request used as an int, a naive datetime compared with an aware one, local time with UTC).
- Fails when: a timeout in seconds is passed where milliseconds are expected, so the wait is 1000 times shorter; a string `"10" + 5` path raises or concatenates.
- Bad:
```python
time_limit_ms = settings.timeout_seconds    # seconds stored, ms expected
```
- Good: convert at the boundary and name the unit in the variable (`timeout_ms = settings.timeout_seconds * 1000`), or parse request values to the typed field before use.
- Not a defect when: both operands already share the unit and type (check the producer), or the conversion is applied in the same expression.
### zip over sequences of unequal length
- Tell: `zip(a, b)` where the lengths are not guaranteed equal and the code does not check or pass `strict=True`.
- Fails when: the prices list is shorter than the quantities list; the extra quantity is silently dropped from the total.
- Bad:
```python
total = sum(p * q for p, q in zip(prices, quantities))   # silent truncation
```
- Good: `zip(prices, quantities, strict=True)` (Python 3.10 or later; raises ValueError on mismatch) or an explicit length check that raises a domain error.
- Not a defect when: both sequences are built from the same source in one comprehension, or the lengths are equal by construction (check the producer).
## Traps

- `SELECT ... FOR UPDATE` inside a transaction before a write: the lock makes the read-then-write safe.
- `UPDATE t SET n = n + ?`: a single atomic statement; not a lost update.
- A rollback or cleanup that logs its own failure and re-raises the original exception: the original error is not swallowed. A compensating rollback that undoes the only half-written state (the debit row when the credit row fails) leaves no half posting: check the state it leaves, not whether the rollback itself could raise.
- `queue.put(x, timeout=1)` with `except queue.Full`: bounded and handled.
- `with open(...)` or `try/finally` around the handle: released on the error path.
- `except Exception as exc: raise DomainError(...) from exc`: wraps and propagates; nothing is swallowed.
- Lease takeover done as one atomic conditional write (`UPDATE leases SET holder=%s, token=token+1 WHERE name=%s AND (expires_at < now() OR holder IS NULL)`, success when rowcount == 1, or a single Lua compare-and-set in Redis): a correct compare-and-set. A separate SELECT of the token followed by a write is not a trap; report it under Check-then-act on shared state.
## Do not report

- Formatting, import order, naming taste.
- Missing tests or low test coverage (not a design hazard).
- Security issues and spec deviations (other reviewers own them).
- Testability alone, or a pattern that is only unfamiliar.
- Hazards in unchanged code when a diff is given (diff mode scope).
- Races with no second actor in the code: no other writer, worker, request path or scheduler.
## Before you write a finding

1. Quote the line that changes state or holds the resource, and name the failing sequence: which call raises, which process dies, or which second actor runs, in order.
2. Confirm the guard is absent: search the function and its callers for the lock, transaction, finally, timeout, dedupe key or version check.
3. Confirm the line is in scope (added, modified or newly exposed by the diff, or any line in whole-file mode) and the outcome is real harm: lost data, double effect, leak, stuck worker, outage.
4. Drop the finding if any of 1 to 3 cannot be shown. Record `UNCLEAR` or `NOT FOUND` instead, with what you searched.
