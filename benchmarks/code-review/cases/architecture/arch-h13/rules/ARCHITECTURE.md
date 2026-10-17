# Architecture rules

## Layers
- Package `billing` is one layer made of three peer modules: `billing/models.py` (data types), `billing/reports.py` (rendering from models) and `billing/service.py` (use cases).
- Modules of the same layer must not form an import cycle at module load time.
- `billing/reports.py` may import `billing/models.py` to render model types.
- `billing/service.py` may import `billing/models.py` and `billing/reports.py`.
- An import inside an `if TYPE_CHECKING:` block is allowed, because it is not a runtime edge.
- An import inside a function body is a runtime edge and counts for the cycle rule.
- Dependencies point from use cases to models and reports; models and reports must not depend on each other in a loop.
