---
name: spec-lens
description: "Focus-mode lens for spec conformance review. Preloaded into spec-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: spec-lens v1

# Spec Lens

Check code against numbered requirements, not against taste.
Every limit, rule and side effect the spec states is in scope; what the spec leaves open is not.

## How to look

1. Read the spec first. Number each requirement. Note limits, units, rounding mode, inclusive or exclusive ends, error types, defaults versus missing, idempotency, ordering and audit rules.
2. Find each requirement in every public entry point. Grep the function names and the spec terms across the changed files and their callers.
3. Boundary pass: for each limit, trace the value at the limit, one below and one above. Write each outcome.
4. Sibling check: find the function that does the same job elsewhere. If it does it right, the other one not doing it is evidence.
5. Removed-line check: list what the change removed (clamp, check, audit call, alias, factor). Confirm each requirement still holds.
6. Dependency check: read the untouched helpers, constants, tables and queries the changed code relies on.
7. Scope pass: list the observable side effects of each changed function (writes, calls, notifications, transformed results). Each must trace to a requirement.
8. Follow each changed call into the unchanged function it reaches (a parser, a validator, a limit check). If that function breaks a requirement for the values the changed path passes it, report it as newly exposed; do not park it under UNCLEAR for being in an unchanged file.
8. Walk each candidate with one concrete input. Write each step and the final output. Drop it if the walk does not reach a wrong outcome.

## Catalog

### Rounding mode
- Tell: `quantize(` or `round(` where the spec names a rounding mode.
- Fails when: spec says half up; `Decimal("0.125").quantize(Decimal("0.01"))` uses the context rounding, which is ROUND_HALF_EVEN in a default context and gives 0.12, not 0.13.
- Bad:
```python
def fee(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"))  # spec: half up
```
- Good: `amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
- Not a defect when: the spec names half even, or the spec names a mode and the code passes it explicitly. A spec that leaves the mode open is out of scope, not a match.

### Inclusive versus exclusive window end
- Tell: `<` used as the upper bound where the spec says "through", "inclusive" or "to and including"; or `<=` used as the upper bound where the spec says "before" or "until".
- Fails when: spec includes the end day; `day = 2026-01-31` with end `2026-01-31` gives False.
- Bad:
```python
def in_report(day: date, start: date, end: date) -> bool:
    return start <= day < end  # spec: end day included
```
- Good: `start <= day <= end` for dates.
- Not a defect when: the spec states a half-open interval [start, end) and the code is `start <= day < end`.

### Timezone and DST
- Tell: `datetime.fromtimestamp(x)`, `datetime.now()` or `strptime` without a tz where the spec says UTC.
- Fails when: the spec requires UTC and the code returns a naive value with no `tz`. Whether the wrong value appears depends on the host zone, which the code does not show: mark UNCLEAR unless the spec names the host zone.
- Bad:
```python
def created_at(epoch_s: float) -> datetime:
    return datetime.fromtimestamp(epoch_s)  # naive host-local time
```
- Good: `datetime.fromtimestamp(epoch_s, tz=timezone.utc)`.
- Not a defect when: the value is only shown in local time as the spec says, or it is converted to UTC before storage.

### Off-by-one paging
- Tell: `page * size` or `(page - 1) * size` that does not match the spec's page base.
- Fails when: pages are 1-based and page=1, size=20 gives offset 20; the first 20 rows are skipped.
- Bad:
```python
def offset_for(page: int, size: int) -> int:
    return page * size  # spec: pages are 1-based
```
- Good: `(page - 1) * size` after `if page < 1: raise ValueError`.
- Not a defect when: the spec says pages are 0-based and `page * size` is correct.

### Clamp in only one of two entry points
- Tell: a limit (max size, range) applied in one public function and absent from a sibling that takes the same parameter.
- Fails when: `export_orders(size=5000)` runs unbounded; the spec sets max 100 for every entry point.
- Bad:
```python
def list_orders(size: int):
    return _query(limit=min(size, 100))
def export_orders(size: int):
    return _query(limit=size)  # spec: max 100 on every entry point
```
- Good: clamp inside `_query`, or call one shared bounds helper from both.
- Not a defect when: the spec limits only `list_orders`, or the shared `_query` already clamps.

### ORDER BY without tie-breaker
- Tell: `ORDER BY` on a non-unique column combined with LIMIT and OFFSET, where the spec requires stable paging.
- Fails when: two rows share `created_at` across a page boundary; one row appears on two pages and another on none.
- Bad:
```python
sql = "SELECT id FROM orders ORDER BY created_at DESC LIMIT %s OFFSET %s"
```
- Good: `ORDER BY created_at DESC, id DESC` when `id` is the primary key (unique).
- Not a defect when: the spec does not require stable paging, or `created_at` is unique by constraint.

### Falsy zero treated as missing
- Tell: `x or default`, or `if not x:`, on a field where 0, "" or [] is a valid value.
- Fails when: caller sends `{"quantity": 0}` to clear stock; the code stores 1. `if not qty: raise` also rejects a valid 0.
- Bad:
```python
def set_quantity(payload: dict) -> int:
    return payload.get("quantity") or 1  # 0 becomes 1
```
- Good: `q = payload.get("quantity"); return 1 if q is None else q`.
- Not a defect when: the spec says 0, "" and missing all mean "use default".

### Unit conversion factor
- Tell: a numeric factor (1000, 60, 1024) in one branch of a unit switch, or a conversion in some branches only.
- Fails when: spec says g to ug is 1,000,000; `to_ug(2, "g")` returns 2000.
- Bad:
```python
def to_ug(value: float, unit: str) -> float:
    if unit == "mg": return value * 1000
    if unit == "g": return value * 1000  # g to ug is 1,000,000
    return value
```
- Good: `_TO_UG = {"ug": 1, "mg": 1_000, "g": 1_000_000}`, then reject unknown units explicitly.
- Not a defect when: the branch factor matches the spec table (mg to ug is 1000).

### Retired code still accepted
- Tell: a lookup table, alias map or allowlist that still contains a key the spec retires.
- Fails when: spec retires `ST-OLD`; `resolve("ST-OLD")` returns `ST-NEW` and the record is accepted.
- Bad:
```python
_ALIASES = {"ST-OLD": "ST-NEW", "ST-NEW": "ST-NEW"}
def resolve(code: str) -> str:
    return _ALIASES.get(code, code)  # ST-OLD still resolves
```
- Good: check a `_RETIRED` set first and raise `UnknownCodeError`.
- Not a defect when: the spec keeps the alias for backward compatibility.

### Wrong exception type
- Tell: `ValueError` raised where the spec names `TypeError`, or the reverse.
- Fails when: `set_qty("3")` raises ValueError; spec says TypeError; a caller catching TypeError misses it.
- Bad:
```python
def set_qty(qty) -> int:
    if not isinstance(qty, int) or qty < 0:
        raise ValueError("qty")  # spec: TypeError for non-int
    return qty
```
- Good: `if isinstance(qty, bool) or not isinstance(qty, int): raise TypeError("qty")`, then `if qty < 0: raise ValueError("qty")`. The bool check matters because `isinstance(True, int)` is True.
- Not a defect when: the spec names no exception type, or the raised class subclasses the named one.

### Only the first parameter validated
- Tell: a validation block that tests one argument while the spec lists a rule for each argument.
- Fails when: spec says start and end are not in the future; `report(start=future, end=today)` passes.
- Bad:
```python
def report(start: date, end: date) -> list:
    if end > date.today():
        raise ValueError("end in future")
    return _build(start, end)  # start never checked
```
- Good: loop over `(("start", start), ("end", end))` with the same check.
- Not a defect when: the spec states the rule for end only, or `_build` runs its own check first.

### Version strings compared as text
- Tell: `<`, `>=` or `sorted()` applied to version strings.
- Fails when: `"2.10.0" >= "2.9.0"` is False (the character "1" sorts before "9"); the spec expects True.
- Bad:
```python
def supports_v2(version: str) -> bool:
    return version >= "2.9.0"  # text comparison
```
- Good: `tuple(int(p) for p in version.split(".")) >= (2, 9, 0)`, or `packaging.version.Version`.
- Not a defect when: the check is equality with one fixed string.

### Money as float
- Tell: `float` on an amount, or `sum()` over float prices where the spec requires exact cents.
- Fails when: ten items at 0.10 sum to 0.9999999999999999; an exact-cent equality check to 1.00 fails.
- Bad:
```python
def total(prices: list[float]) -> float:
    return sum(prices)  # sum([0.1] * 10) != 1.0
```
- Good: receive prices as strings and `sum((Decimal(p) for p in prices), Decimal("0"))`.
- Not a defect when: the value is a ratio or a sensor reading, not money.

### Idempotent operation writes a second audit entry
- Tell: an audit call placed before the status check, so the replay path also records.
- Fails when: `approve()` is called twice; two "approved" rows exist for one approval; spec says one.
- Bad:
```python
def approve(order) -> None:
    audit.record("approved", order.id)  # also written on replay
    if order.status == "approved":
        return
    order.status = "approved"
```
- Good: check the status, return early, then record and change the status.
- Not a defect when: the spec asks for an entry on every request, repeats included.

### Audit entry missing or missing a field
- Tell: a status change with no audit call on one path, or an audit call with fewer fields than the spec lists.
- Fails when: the spec requires user, from, to and time; `record(order.id, to=new)` drops user and from.
- Bad:
```python
def set_status(order, new, user) -> None:
    order.status = new
    audit.record(order.id, to=new)  # spec: user, from, to, time
```
- Good: capture `old = order.status` first, then `record(order.id, user=user, frm=old, to=new, at=utc_now())`.
- Not a defect when: a database trigger on this table writes the full audit row (verify it covers the column).

### Integer midpoint overflow
- Tell: `(lo + hi) // 2` on fixed-width integers (numpy, ctypes, struct, a database INT column).
- Fails when: lo and hi are int32 arrays; `lo + hi` wraps negative and a binary search indexes outside its range.
- Bad:
```python
import numpy as np
lo = np.array([2_000_000_000], dtype=np.int32)
hi = np.array([2_100_000_000], dtype=np.int32)
mid = (lo + hi) // 2  # the sum wraps to a negative value
```
- Good: for numpy arrays, widen before adding: `mid = (lo.astype(np.int64) + hi.astype(np.int64)) // 2`, then cast back to the input dtype (the result lies between lo and hi, so the cast cannot overflow). Use `lo + (hi - lo) // 2` only after showing the span fits the dtype.
- Not a defect when: plain Python int (unbounded), or the spec sets no fixed width.

### Scope creep with a side effect
- Tell: a data write (insert, update, append) or an outbound network call in a read function that no requirement names. Logging, metrics and tracing are not scope creep unless the spec forbids them.
- Fails when: `get_price()` appends a history row; every read grows the table; the spec says read only.
- Bad:
```python
def get_price(sku: str) -> Decimal:
    price = _repo.price_of(sku)
    _repo.append_history(sku, price)  # write not in spec
    return price
```
- Good: `return _repo.price_of(sku)`; history is written by the command that changes the price.
- Not a defect when: the spec asks for the write, or it is a cache fill that does not change the result. A new validation (rejecting duplicates, storing an extra field) that the spec is silent on is not scope creep unless it breaks an allowed input or a stated requirement.

### State transition not guarded
- Tell: an assignment to a status or state field with no check of the current state, where the spec lists the allowed prior states.
- Fails when: spec allows `approve` only from `pending`; `approve()` on a `rejected` order sets `approved`.
- Bad:
```python
def approve(order) -> None:
    order.status = "approved"  # spec: only from "pending"
```
- Good: `if order.status != "pending": raise InvalidTransitionError(order.status)` before the assignment.
- Not a defect when: the spec allows the transition from every state, or the check is shown on every path.

### Error swallowed where the spec requires an error
- Tell: `except` that passes, returns None or returns a default where the spec names an error, rejection or audit entry for that path.
- Fails when: spec says a failed export raises `ExportError`; `except OSError: return []` reports an empty export as success.
- Bad:
```python
def export(path: str) -> list:
    try:
        return _read(path)
    except OSError:
        return []  # spec: raise ExportError
```
- Good: `except OSError as exc: raise ExportError(path) from exc`.
- Not a defect when: the spec allows the default, or the caller checks for the error on every path.

## Traps

- `Decimal(str(x))` on a float is only a formatting step. It does not repair a float amount computed earlier (`str(0.1 + 0.2)` is `'0.30000000000000004'`); when the float reaches this line after arithmetic, report it under Money as float.
- `tuple(int(p) ...) >= (2, 9, 0)` is a correct numeric order only when every part is digits; a pre-release such as `2.9.0rc1` raises ValueError, which is a finding when the spec accepts such versions.
- `SELECT COUNT(*)` without LIMIT is correct when the spec asks for a total, not a page.
- An early return before side effects is correct idempotency when the replay path writes nothing.
- `min(size or 25, 100)` is correct when the spec says 0 or missing means 25 and the maximum is 100.
- `ROUND_HALF_UP` in one function and default rounding in another is correct when each spec names its own mode.
- `(lo + hi) // 2` on Python int cannot overflow; Python ints are unbounded.
- A guard that cannot fire because an earlier check already excludes its input is redundant, not a spec miss.
- An `if __name__ == "__main__":` demo block is not behaviour and is not in the spec.

## Do not report

- Behaviour the spec leaves open: unstated rounding, ordering, limits, defaults.
- Input types the spec never mentions (None, str for an int) unless the spec states validation for them.
- Style, naming, formatting, import order.
- Missing tests or test coverage.
- Security or design the spec did not ask for. A requirement the spec states is always in scope.
- Pre-existing spec deviations on untouched lines when a diff is given.
- Anything a linter, type checker or compiler reports.
- Performance concerns with no spec requirement.

## Before you write a finding

1. Quote the requirement (ID or sentence) and the exact code line that implements it or should; for scope-creep, quote the side-effect line and state that no requirement names it.
2. State one concrete input, walk the code to the output, and write both. The output must differ from the spec.
3. Grep the other entry points and helpers for a guard that would stop the input. Say what you searched and what you found.
4. Confirm the requirement applies to this entry point and to code the change touched.
5. If the spec is silent or ambiguous here, mark UNCLEAR and do not report. Drop any candidate whose walk you cannot finish.
