# Architecture rules

Scope: project modules under `code/`. Standard-library and third-party imports are outside this rule.

## Layers and allowed project imports

| Layer | Package | May import from project layers |
|---|---|---|
| domain | `domain/` | domain only |
| application | `application/` | domain and ports |
| infrastructure | `infrastructure/` | domain and application |

## Rules

- A module imports only from the layers listed in its row of the table.
- Dependencies point inward: domain is the innermost layer and depends on nothing outside itself.
- An import from a module in one layer to a module in a layer not listed for it is a layer direction violation.
- Each violation must cite the import line and name both layers.
