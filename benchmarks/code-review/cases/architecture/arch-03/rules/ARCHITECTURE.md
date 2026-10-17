# Architecture rules

## Layers
- The domain (`domain/`) uses plain dataclasses, enums and standard-library value types only.
- The domain never imports or names ORM, persistence or web-framework types (SQL models, sessions, request or response objects).
- The application layer (`application/`) passes domain types between the domain and the outside world.
- The infrastructure layer (`infrastructure/`) owns the ORM models and maps them to domain types before anything leaves it.
- Dependencies point inward: infrastructure may import the domain; the domain never imports infrastructure.
