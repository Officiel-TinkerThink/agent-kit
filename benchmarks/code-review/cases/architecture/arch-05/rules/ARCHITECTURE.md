# Architecture rules

## Layers

- The application layer is the set of top-level packages under `code/` (for example `orders`, `refunds`).
- Packages in the same layer are siblings. Sibling packages must not depend on each other in both directions.

## Dependency direction

- Within the application layer, packages form an acyclic graph.
- A cycle is any import path that leads from a package back to itself, direct or through other siblings.
- Reviewers check every import added by a change against this graph, not only the file the import sits in.

## Shared types

- A type that more than one package needs lives in a module that all of those packages import.
- A package must not own a type that a sibling reads from it when the reading side would then import the owner.
