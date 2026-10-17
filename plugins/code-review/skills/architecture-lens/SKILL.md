---
name: architecture-lens
description: "Focus-mode lens for structure: dependency direction between layers, adapters and frameworks leaking into core code, concrete dependencies built inside logic, leaky abstractions, duplicated rules, cycles and speculative generality. Preloaded into architecture-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: architecture-lens v1

# Architecture Lens

Finds code whose dependencies point the wrong way, or whose structure forces a named change to touch many places. A structural finding needs a named rule (the edge that breaks it) or a named change (the places it forces), never a general dislike of the shape.

## How to look

1. Find the rule source first: layer list, ADRs, ARCHITECTURE.md, CLAUDE.md, CONTRIBUTING.md. If none exists, report only named-change findings and write `RULES: none found`.
2. Map each cited module to a layer from the rule source. A module you cannot place goes to UNCLEAR, not to a finding.
3. List the import edges of the inner-layer modules in the change (`import` and `from ... import` lines, plus names passed in signatures). For each edge, check the target's layer.
4. For each concrete construction (`Client(...)`, `Repository(...)`) inside logic, check whether the value it hardcodes differs per environment and whether a port or parameter could carry it.
5. For each named change the brief or the spec mentions (a second adapter, a second database, a new entry point), count the files that must be edited. Three or more places with no shared seam is evidence.
6. Count fan-in and fan-out with Grep for the module you suspect. Report the counts; do not invent a threshold.

## Catalog

### Layer direction violated
- Tell: a module in an inner layer (domain, use case, entity) imports a module of an outer layer (web, persistence, infrastructure, UI), with the edge at `path:line`.
- Fails when: the rule says domain code must not depend on infrastructure, and the change adds one more such edge; a second adapter for the same port then cannot be added without editing the domain module.
- Bad:
```python
# domain/orders.py
from infra.db import session    # outer layer imported by the inner layer
```
- Good: the domain defines a port (an interface or Protocol) and the infrastructure module implements it; the composition root wires them.
- Not a defect when: the composition root (the module that wires adapters) imports adapters, which is its job, or the rule source does not define layers for this package.
### Core code imports an adapter or SDK directly
- Tell: a use case or domain module imports a database driver, HTTP client, web framework, message broker or vendor SDK module by name.
- Fails when: adding a second broker means editing every use case that publishes, because each one names the SDK.
- Bad:
```python
from kafka import KafkaProducer     # in a use case module

def place_order(order):
    KafkaProducer(...).send("orders", order)
```
- Good: the use case calls an `EventPublisher` port; the Kafka adapter implements it and is injected.
- Not a defect when: the module is itself an adapter, or the SDK import is a type-only import under `TYPE_CHECKING` and nothing runs at import.
### Framework type crosses a boundary
- Tell: an inner-layer function takes or returns a framework or transport type (request object, HTTP response, ORM row or model, DataFrame) in its signature.
- Fails when: an ORM model is returned to the web layer, so a change to the model's fields changes the API response shape; each handler that reads its relations must change with it.
- Bad:
```python
def get_order(order_id) -> OrderORM:    # ORM model leaves the persistence boundary
    return session.get(OrderORM, order_id)
```
- Good: map to a plain domain structure (dataclass or TypedDict) at the boundary and pass that.
- Not a defect when: the type is a plain data class defined in the same layer, or the boundary is the framework's own handler.
### Concrete dependency constructed inside logic
- Tell: a service or use case creates an adapter or client inline (`Client(...)`, `Repository(...)`, `connect(...)`), instead of receiving it as a parameter or port.
- Fails when: the test cannot replace the client; a second deployment needs a different endpoint and the code cannot be configured for it.
- Bad:
```python
class BillingService:
    def charge(self, cart):
        client = StripeClient(api_key=os.environ["STRIPE_KEY"])   # built per call, fixed vendor
        return client.charge(cart.total)
```
- Good: accept the client in `__init__` (or a port), and let the composition root build it from settings.
- Not a defect when: the construction is in the composition root, or the client is a stateless helper with no configuration that differs per environment.
### Leaky abstraction
- Tell: a method returns the internal connection, session, file handle or mutable list that the class relies on.
- Fails when: replacing the connection type means editing every caller, because callers already hold and manage the internal connection.
- Bad:
```python
class Repo:
    def __init__(self): self._conn = connect()
    def conn(self):
        return self._conn      # callers now control transactions
```
- Good: expose domain methods only; keep the connection private and scope transactions in a context manager.
- Not a defect when: the accessor returns a copy or a read-only view, or it is used only inside the same module and documented as such.
### Duplicated rule with different strictness
- Tell: the same validation or limit implemented in two places with different conditions.
- Fails when: a third caller must copy one of the two rules, and the copies already differ; a change to the rule is made in one place and missed in the other.
- Bad:
```python
def api_valid(email):
    return "@" in email
def form_valid(email):
    return re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email) is not None
```
- Good: one function in one module, imported by both paths.
- Not a defect when: the two checks are deliberately staged (a cheap edge pre-filter and the full check before persistence), and both are documented; or the two rules serve different operations that the spec or rules say must differ (for example a public signup check and an admin import check, each documented).
### Hardcoded host or port
- Tell: a literal IP, hostname or port inside the function body rather than in settings.
- Fails when: a second environment needs a code edit to change the address, so each deployment becomes a separate build.
- Bad:
```python
def make_client():
    return Client(host="10.20.0.15", port=8443)   # one environment only
```
- Good: read host and port from settings with no default for required values, and fail fast at startup when they are missing.
- Not a defect when: the literal is a loopback default for local development passed through settings, or a fixed public constant such as port 443 for https.
### God class forced by the change
- Tell: the change or a named test must construct a class whose collaborators are unrelated to the change (for example mail and billing for a PDF change) and are required at construction.
- Fails when: a change to PDF rendering needs a billing client to construct Platform, so the rendering change must edit or mock billing code it does not touch.
- Bad:
```python
class Platform:
    def __init__(self, billing, mailer, pdf):   # all required
        self.billing, self.mailer, self.pdf = billing, mailer, pdf
```
- Good: inject only the collaborator the changed code needs, or split the class along the reason it changes.
- Not a defect when: the class is large but cohesive, or no change and no test in scope needs its unrelated parts.
### Cyclic dependency
- Tell: two or more modules in the same layer that import each other directly, or through a chain of imports, with each edge at `path:line`.
- Fails when: a change to either module forces an edit in the other, so the two cannot be changed or tested apart.
- Bad:
```python
# orders/service.py
from orders.repo import OrderRepo
# orders/repo.py
from orders.service import OrderStatus    # closes the cycle
```
- Good: move the shared type (`OrderStatus`) into a third module that both import.
- Not a defect when: the cycle exists only under `TYPE_CHECKING`, or it is between a package and its own test code.
### Speculative generality
- Tell: a parameter or option that the function body never reads, or a hook or base class that no caller or subclass uses (state the Grep pattern and the zero-result count). A parameter the body reads is not speculative even when no caller passes it.
- Fails when: a change that adds a second implementation must edit the signature and every caller for an option that nothing reads.
- Bad:
```python
def export(report, format="csv", plugin=None):   # plugin never read, no caller passes it
    return to_csv(report)
```
- Good: remove the unused parameter, or wire it to the behaviour it names.
- Not a defect when: the signature is fixed by a framework hook or an interface the change cannot alter, or the public API documents the parameter for external callers.
### Hub dependency
- Tell: a module that many modules import (fan-in counted with Grep) and that itself imports unrelated layers.
- Fails when: a change to the hub's signature forces edits in every caller, and the hub's own imports pull in unrelated layers, so every caller depends on them.
- Bad:
```python
# common/utils.py: imported by many callers for one helper
from db import session
from billing import Invoice
from pdf import render

def format_money(value):
    return f"{value:.2f}"
```
- Good: split the hub along its reasons to change, so each caller imports only the part it needs.
- Not a defect when: the hub has no imports from outer layers, or the change does not touch the hub's signature.
## Traps

- An import under `TYPE_CHECKING` that names an outer module: a type-only edge, not a runtime dependency.
- A composition root (the module that builds adapters from settings) importing adapters: its job, not a violation.
- A DTO or dataclass defined in the domain and returned to the web layer: a plain structure crossing a boundary is what the rule asks for.
- A test module importing an adapter: test code is outside the layer rule unless the brief says otherwise.
- A parameter that a framework hook requires but the body ignores: fixed by the interface, not speculative.
## Do not report

- Formatting, import order, naming taste.
- Runtime defects, concurrency and retries (defect-reviewer owns them).
- Security issues, including credentials and secrets, and spec deviations (other reviewers own them). A host or port literal is this lens's concern; a credential value is not.
- A structure that is unfamiliar but follows the rule source.
- Layers the repo does not define: report named-change findings only.
- Hazards in unchanged code when a diff is given (diff mode scope).
## Before you write a finding

1. Cite the edge (import or call line) or the construction line, and name the rule it breaks (rule source path:line) or the named change and the places it forces.
2. Confirm the edge is real: re-open the line and check that it imports or constructs what you quote.
3. Confirm the line is in scope (added, modified or newly exposed by the diff, or any line in whole-file mode).
4. Drop the finding if any of 1 to 3 cannot be shown. Record `UNCLEAR` or `NOT FOUND` instead, with what you searched.
