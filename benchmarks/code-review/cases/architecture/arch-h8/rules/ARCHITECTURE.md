# Architecture rules

Scope: project modules under `code/`. Standard-library and third-party imports are outside this rule.

## Layers and allowed project imports

| Layer | Package | May import from project layers |
|---|---|---|
| domain | `domain/` | domain only |
| application | `application/` | domain, application and infrastructure |
| infrastructure | `infrastructure/` | domain and application |

## Rules

- A module imports only from the layers listed in its row of the table.
- Domain is the innermost layer. A domain module must not depend on infrastructure, either by a direct import or through another module that it imports. The dependency chain is followed to its end.
- Application is an outer layer. It may import infrastructure directly, for example persistence adapters called from use cases.
- An import from a module in one layer to a module in a layer not listed for it is a layer direction violation.
- Each violation must cite the import line and name both layers.
