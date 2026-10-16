# Contributing: LIMS Export Service

1. Use the `logging` module, never `print()`, in `code/`.
2. Every `batch_id` passes through `lab_core.ids.validate_batch_id()` before it reaches a store query.
3. Never swallow exceptions: no bare `except:` and no `except Exception: pass`.
4. Every module starts with a one-line docstring.
5. Pull requests must not add public functions in `code/` without type annotations on every parameter and the return value.
