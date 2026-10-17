---
name: defect-lens-python
description: "Focus-mode catalogue of common Python behavioural defects: mutation during iteration, consumed iterators, shared mutable class state, control flow in finally, unreachable except clauses and discarded results. Preloaded into defect-reviewer alongside defect-lens; not for direct use."
user-invocable: false
---
LENS-MARKER: defect-lens-python v1

# Defect Lens: Python

Companion to defect-lens. Same method: work from the failure sequence, and name the state left behind and the input that leaves it.
Each Tell is a shape to look for, not a finding. Before you write a finding, name the guarantee the code breaks and check the "Not a defect when" clause.

## How to look

1. For each `for` loop, list what the loop body does to the iterated object: removes, adds, rebinds or only reads its elements.
2. For each generator or iterator variable, count the consumers in the same function and in its callers; a second consumer is a candidate.
3. For each class body, list the mutable class attributes and every method that changes them through `self`.
4. For each `try` with a `finally`, `except` or `return` statement, check which exit paths the block takes when an exception is in flight.
5. For each call that returns a new value (strings, sorted copies), check whether the result is assigned or returned.

## Catalog

### Collection mutated while iterated
- Tell: a `for` loop over a list, dict or set that calls `remove`, `append`, `pop`, `del`, or assigns a new key to the same object inside the loop body.
- Fails when: removing the current item from a list skips the next item; adding keys to a dict during iteration raises `RuntimeError`, and a removal inside the loop silently skips elements.
- Bad:
```python
for item in items:
    if item.done:
        items.remove(item)     # the item after each removal is skipped
```
- Good: iterate over a copy (`for item in list(items):`), or build the kept items in a new list and assign it back.
- Not a defect when: the loop iterates over a copy, or it only mutates the elements' attributes and not the container.
### Generator or iterator consumed twice
- Tell: a generator, iterator or file object passed to two consumers, or read once to compute a value and then again in the same function, with no `list()` or re-creation in between.
- Fails when: the first consumer exhausts the iterator; the second sees nothing and computes an empty result with no error (`sum` gives 0, a loop body never runs).
- Bad:
```python
rows = load_rows(path)            # generator
count = sum(1 for _ in rows)
total = sum(r.amount for r in rows)   # always 0: rows is already exhausted
```
- Good: materialise once (`rows = list(load_rows(path))`) or recreate the iterator for each consumer.
- Not a defect when: the object is a list, tuple or other re-iterable collection, or the second read is guarded by a fresh call.
### Shared mutable class attribute
- Tell: a mutable literal (`[]`, `{}`, `set()`) assigned in the class body and changed through `self.<name>.append`, `[key] = ...` or `.update` in an instance method.
- Fails when: every instance shares one list or dict, so a value added through one instance is visible through all of them, including the ones created for other requests.
- Bad:
```python
class Session:
    cart = []                    # one list for every instance
    def add(self, item):
        self.cart.append(item)
```
- Good: create the container in `__init__` (`self.cart = []`).
- Not a defect when: the class attribute is intentionally a shared container by design and the spec or docstring says so, or the attribute is never mutated through an instance.
### Return or break inside finally
- Tell: `return`, `break` or `continue` inside a `finally` block.
- Fails when: the `finally` return replaces an in-flight exception, so the caller receives a normal value and the error is lost.
- Bad:
```python
def read_config(path):
    try:
        return parse(open(path).read())
    finally:
        return {}                # discards any exception raised by parse
```
- Good: move the cleanup into `finally` with no control-flow statement, and return from the `try` body.
- Not a defect when: the `finally` return is intentional and the swallowed exception is documented as expected.
### Unreachable except clause
- Tell: an `except` clause whose exception type is a subclass of a type caught by an earlier `except` clause in the same `try` statement.
- Fails when: the later handler never runs; the error it was written for takes the earlier path and gets the earlier handling, which may be wrong.
- Bad:
```python
try:
    load(path)
except OSError:
    return None
except FileNotFoundError:        # subclass of OSError: never reached
    raise MissingConfig(path)
```
- Good: list the more specific type first.
- Not a defect when: the earlier handler re-raises or does the same work as the later one, or the types are unrelated.
### Return value of a non-mutating call discarded
- Tell: a call to a method that returns a new value and leaves the receiver unchanged (`str.strip`, `str.replace`, `str.upper`, the built-in `sorted()`), used as a statement with the result not assigned or returned.
- Fails when: the intended transformation never happens; the code proceeds with the original value and the caller gets the unmodified data.
- Bad:
```python
def normalise(code):
    code.strip().upper()         # result discarded: code is unchanged
    return code
```
- Good: `code = code.strip().upper()`.
- Not a defect when: the call is made for its side effect on a mutable receiver (for example `list.sort()`, which returns None and mutates in place), or the result is intentionally unused and the spec says so.

## Known safe patterns

- `for x in list(items):` or a comprehension that builds a new list: the loop iterates over a copy; removing from `items` is safe.
- `sorted(items)` assigned to a name, or `list.sort()` used as a statement: the sort is kept on the receiver that the code reads afterwards.
- `return` inside `try` with a `finally` that only closes a handle: the handle is released and the value is returned; nothing is lost.
- `except Exception as exc: raise AppError(...) from exc`: the error is wrapped and propagated, not swallowed.
- A class attribute that is a tuple, frozenset or string: immutable, so sharing it between instances is not a defect.

## Do not report

- Formatting, import order and naming taste.
- Missing tests or low test coverage (not a defect by itself).
- Security issues and spec deviations (other reviewers own them).
- Style choices such as `list(...)` copies that are not needed when the loop does not mutate the container.
- Patterns that are only unfamiliar to the reader but behave correctly on a trace.
