---
name: simplicity-lens
description: "Focus-mode lens for logic that is more complicated than it needs to be. Preloaded into simplicity-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: simplicity-lens v1

# Simplicity Lens

Finds code the change added that can be replaced by a simpler form with IDENTICAL behaviour. This is not a style review and not a bug hunt.
A finding names the simpler form and shows that the behaviour stays the same for the inputs the code can receive. If the behaviour would change, it is not a finding.

## How to look

1. For each hunk, read the added or modified code and ask: what is the shortest form that does exactly this? Write that form down before you decide.
2. Prove sameness. Run both forms in your head on these inputs: empty, None, 0, False, one item, many items, a value on each side of every comparison, and every exception the original can raise.
3. Compare side effects too: log calls, writes, counters, the order of calls. A simpler form that drops a log line or a write is not identical.
4. For a parameter, flag, branch or function you think is unnecessary, Grep every caller in the material you were given. The claim "every caller passes the same value" needs the list of callers behind it. If you cannot see all callers, report it at confidence 55 and name the callers you could not see; the validator decides.
5. For duplicated code, open every copy. Report duplication only when the copies are the same except for names, and say which lines differ. Copies that differ in a comparison, a limit or a message may differ on purpose; read the intent before you merge them.
6. Check Known safe patterns before you write a candidate. The look-alikes that are not simplifications are listed there.
7. One finding per root cause. Copies of one function are one finding with one location per copy.

## Catalog

The Bad and Good blocks show the shape of each simplification. They are not proof: a Good form that differs from its Bad form for an input the code can receive is not a finding. Prove identity for the actual code in front of you.

### Boolean ladder
- Tell: `if cond: return True` followed by `else: return False` (or `x = True` / `x = False` in two branches).
- Fails when: the extra four lines hide that the function simply returns the comparison, and a later edit changes one branch only.
Bad:
```python
def predicate(value, bound):
    if value < bound:
        return True
    else:
        return False
```
Good:
```python
def predicate(value, bound):
    return value < bound    # identical only when the comparison returns a bool
```
Not a defect when: `cond` can be a non-bool value that the function must turn into True or False (then `return bool(cond)`), or the function must return the original truthy value, or the two branches differ in a side effect.

### Reimplemented standard library
- Tell: a hand-written loop that sums, finds the maximum or minimum, counts, joins, tests any/all, builds a dict with a `get` default, or strips a suffix by slicing.
- Fails when: a hand-written loop that duplicates a built-in aggregate can be one call, so a reader has to verify the loop to learn that.
Bad:
```python
total = 0
for v in items:
    total += v
best = None
for v in items:
    if best is None or v > best:
        best = v
```
Good:
```python
total = sum(items)  # not identical for None items or float sums (see Not a defect)
best = max(items, default=None)
```
Not a defect when: the loop has an early exit, logs or counts per item, mutates something, or iterates a generator that a second pass would exhaust. The built-in form must also keep the same result for the empty input, and for floats `sum()` can differ from `+=` (compensated summation in Python 3.12+); `max` raises TypeError on None items where a guarded loop skips them.

### Append loop that is a plain map or filter
- Tell: `result = []`, then `for x in items:`, then `result.append(f(x))` with an optional `if`, and nothing else in the loop.
- Fails when: five lines say what one comprehension says. This is the weakest finding in the catalog: report it only when the loop body is exactly one append and one optional condition, and rate it low.
Bad:
```python
result = []
for item in items:
    result.append(transform(item))
```
Good:
```python
result = [transform(item) for item in items]
```
Not a defect when: the loop logs, counts, catches errors per item, breaks early or builds two results.

### No-op try/except
- Tell: a `try` with no `else` or `finally` whose `except SomeError:` body is only a bare `raise`. (`raise e` adds a traceback frame: not identical.)
- Fails when: the handler catches an exception and raises the same exception unchanged; removing the whole `try` gives identical behaviour (same type, same traceback to the caller).
Bad:
```python
try:
    return lookup(key)
except KeyError:
    raise
```
Good:
```python
return lookup(key)
```
Not a defect when: the handler logs, cleans up, translates the exception into another type (`raise AppError(...) from exc`), retries, or changes state before re-raising.

### Redundant cast, comparison or guard
- Tell: `str(str_value)` (exact str, not a subclass), `int(value)` where value is already an int, `x if x else x`.
- Fails when: the cast does nothing, so the reader looks for a type that cannot occur.
Bad:
```python
label = str(name)
```
Good:
```python
label = name  # identical: name is already an exact str
```
Not a defect when: `== True` or `not not x` (they change the value or type), `list(v)` (breaks aliasing), the cast changes the type or value (a conversion such as float to a decimal type), the guard prevents a division by zero or an exception, or the copy is defensive because the callee mutates it.

### Branch that cannot run
- Tell: a condition that an earlier line in the same function, or the only caller, already guarantees (`if value is not None:` after the caller validated and replaced None).
- Fails when: the dead branch makes the reader wonder which state is possible, and the else branch is untested because nothing reaches it.
Bad:
```python
def compute(a, b):
    if b is not None:        # verify: grep every caller of the validator first
        return scale(a * b)
    raise GuardError(b)
```
Good:
```python
def compute(a, b):
    return scale(a * b)      # identical only if b is never None; removing a guard can change the raised exception type
```
Not a defect when: the function is public and the change makes its guard the only check on a reachable input, or the guard is the only check on that path. A public function called only from the material you were given is a finding at confidence 55, not UNCLEAR.

### Abstraction with one implementation
- Tell: an abstract base class, a factory and a registry that together serve one concrete class that nothing else subclasses or swaps.
- Fails when: three layers wrap one function, so a reader follows the registry to learn that `make(key)` returns `Impl`.
Bad:
```python
class Base(ABC):
    @abstractmethod
    def run(self, rows): ...

TABLE = {"kind": Impl}
def make(key):
    return TABLE[key]()
```
Good:
```python
def write_rows(rows, stream):  # a shape only: the signature and the callers change
    ...
```
Not a defect when: a second implementation exists in the material you were given (a test double does not count unless it is in the code), the base class defines a contract that other code type-checks against, or the registry is filled from configuration, or the project standard requires an interface (SOLID, testability).

### Parameter or flag that every caller sets the same way
- Tell: a new boolean or option parameter, and every call site (Grep them) passes the same literal.
- Fails when: a flag that the only caller always sets to the same value, so the other branch is untested dead code that adds a way to misconfigure.
Bad:
```python
def emit(self, rows, verbose=True):
    if verbose:
        writer.writerow(HEADER)
```
Good:
```python
def emit(self, rows):  # removes a keyword: any caller that still passes verbose breaks
    writer.writerow(HEADER)
```
Not a defect when: a caller outside the material you were given may pass the other value, or the function is a documented public API.

### Pure pass-through wrapper
- Tell: a function whose whole body is a call to another function with the same arguments in the same order.
- Fails when: `_wrap(x, y)` only calls `inner(x, y)`, so every reader opens two functions to read one.
Bad:
```python
def _wrap(x, y):
    return inner(x, y)
```
Good:
```python
inner(x, y)   # at the call sites; keep `return` if the value is used
```
Not a defect when: the wrapper validates, logs, converts arguments or exceptions, adds a default, or exists to give a stable name to an interface that other code imports.

### Copied logic across files
- Tell: two or three functions with the same body in different modules, differing only in identifiers (a label that reaches a message or error is a difference).
- Fails when: the same check lives in `module_a.py`, `module_b.py` and `module_c.py`. A fix to one leaves the others wrong.
Bad:
```python
def check_c(record):
    ...   # same body as check_a and check_b
```
Good:
```python
def check(record, label):  # callers must now pass label; a one-argument call breaks
    ...   # one shared body; the three modules pass their label
```
Not a defect when: the copies differ in a comparison operator, a limit, a message or an error type. Name the differing line. A boundary that is `<` in one copy and `<=` in the other may be required by the intent; do not merge it.

### Long if/elif that maps one value to another
- Tell: six or more branches of the form `if code == A: return "x"` / `elif code == B: return "y"`, with no side effects.
- Fails when: several branches say what one dict lookup with a default says.
Bad:
```python
if code == CODE_A:
    return "label_a"
elif code == CODE_B:
    return "label_b"
# ... seven more branches that only return a label
else:
    return "default"
```
Good:
```python
return TABLE.get(code, "default")  # identical for hashable codes only
```
Not a defect when: the branches differ in side effects, raise, compute a value, or the chain has fewer than four branches. An unhashable input that the original maps to the default and a dict would raise on only matters if the function can receive one.

### Nested conditionals that return the same value
- Tell: three levels of `if` where two different paths end in the same return value or the same exception.
- Fails when: the reader has to hold three conditions to see that two of them lead to the same value.
Bad:
```python
if a is not None:
    if a.ok:
        return "X"
    else:
        return "Y"
else:
    return "Y"
```
Good:
```python
if a is None or not a.ok:
    return "Y"
return "X"
```
Not a defect when: the branches return different values, run different side effects, or the nesting follows the order the intent requires (check A before B for a reason the spec states).

### Machinery around a cheap pure function
- Tell: a cache or invalidation hook wrapped around a function that is pure, cheap and called a few times, and nothing ever calls the invalidation.
- Fails when: a cache object with extra state makes a cheap lookup look stateful.
Bad:
```python
class Cache:
    def __init__(self): self._memo = {}
    def get(self, a, b): return self._memo.setdefault((a, b), _compute(a, b))
```
Good:
```python
value = compute(a, b)  # a shape only: needs compute() and the cache removed
```
Not a defect when: the function reads a file, a database or the network, is expensive, or has a documented invalidation path that code in the material actually calls.

### Dead code added by the change
- Tell: a function, method, import, parameter or variable the change adds that nothing in the provided material uses.
- Fails when: a function the change adds has no caller, so it will rot and mislead.
Bad:
```python
def dump(path, rows):      # no caller in the code
    ...
```
Good:
```python
# removed  # a deletion, not a rewrite: any importer breaks; grep first
```
Not a defect when: it is a public API of a library, an entry point named in a config or a decorator registry, a hook called by name, or a test helper used by tests you were not given. When in doubt report it at confidence 55 and name the doubt.

## Known safe patterns

These look simplifiable and are not. Check each before you report.

- `x or default` for a value where 0, "" or False is legal: `value or default` turns a legal 0 into the default. An explicit `is None` check is required.
- `return cond` where the original returns a non-bool, or returns a different value per branch (`"UPPER" if x else None`).
- A loop with an early exit plus a per-item log call: `next(...)` or `any(...)` drops the log lines.
- Two near-duplicate functions that differ in `<` versus `<=`, a limit or a message. Read the intent.
- `try/except` that translates the exception type (`raise AppError from exc`). Removing it changes what callers catch.
- `Decimal(float_value)` keeps the binary approximation; `Decimal(str_value)` does not.
- `lru_cache` or a memo on a function that reads a file or a table that changes at run time.
- An empty-input guard before an average: the division by zero is the reason. A guard that returns a value different from what the operation would give is part of the contract: read the callers first.
- `return x or None` for a string: `''` becomes `None`. Keep the explicit check when the empty string is a valid result.
- An abstract base with two real implementations, or a base that other code type-checks against.
- A wrapper that validates, logs or converts. A wrapper that gives a stable public name.
- A generator that is read twice: replacing a list with a generator changes the second read.
- `bool` is an `int`: `isinstance(x, int)` accepts `True`. A guard that rejects bool must stay.
- A copy that the callee mutates: the defensive copy is not redundant.
- A removed log line, counter or write: that is a behaviour change, not a simplification.
- `try/except ValueError` replaced by `isdigit()`: negatives, whitespace and the exception type for None differ.
- `sorted(xs)[:3]` from a copy plus in-place sort: the in-place form mutates the caller's list; the reverse rewrite is only valid when the list is local.
- `str(v)` on bytes returns the repr, so a decode branch is not redundant.
- `not count` versus `count == 0`: differ for None, "" and [].
- Dropping a `None` sentinel for a list, dict or set default creates a shared default.
- `set(xs)` for `dict.fromkeys(xs)` loses insertion order.
- `d.get(k, expensive())` evaluates the default always; `if k in d` does not. `==` versus `is`. `a < b < c` evaluates b once.
- A comprehension replacing a loop leaves the loop variable unbound. `s[:-len(suffix)]` versus `removesuffix` differ only when the suffix can be empty. `int(x)` on a float truncates.
- Easy wins that are identical: `else` after an unconditional return, `try/finally` that only closes (use `with`), copy plus in-place sort of a local list (use `sorted()`), index loop reading only `xs[i]` over a sequence (iterate directly).

## Do not report

- Pre-existing code the change did not touch (diff mode), even if it can be simplified.
- Naming, formatting, comment wording, import order, line length: no written rule, no finding.
- Performance tuning, unless the simpler form is also identical in behaviour.
- A rewrite into another paradigm, another library or another dependency.
- Anything where the simpler form differs for an input the code can receive (exception, type, order or dropped side effect): raises a different exception, returns a different type, changes order, or drops a side effect.
- A bug, a race, a missing check or a spec deviation. If you see one, put it under UNCLEAR as out of focus; other reviewers own it.
- A preference. The test for a finding is "I can write the simpler form and show it behaves the same".
