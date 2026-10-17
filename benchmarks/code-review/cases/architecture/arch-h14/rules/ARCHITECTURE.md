# Architecture rules

The package `api` is the public partner API, and its modules in `api/` hold the endpoint functions that partners call.
The package `service` holds the business logic in `service/`, and the API delegates to it.
Dependencies point inward: `api` may import `service`, and `service` never imports `api`.
Function parameters in `api/` are part of the partner contract and are kept even when unused.
Everywhere else, a parameter that the code never reads and that has no caller is speculative generality and must not be added.
A parameter that the code reads, or that at least one caller passes, is not speculative generality.
