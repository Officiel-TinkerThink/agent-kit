# Architecture rules

## Layers
- Package `shop` is split into `shop.domain`, `shop.application` and `shop.infrastructure`.
- The domain (`shop/domain/`) uses plain dataclasses, enums and standard-library value types only.
- The domain never imports the infrastructure layer, by absolute import (`shop.infrastructure...`) or by relative import (`from ..infrastructure...`, `from .. import infrastructure`). Any import whose resolved target is inside `shop.infrastructure` is forbidden in `shop/domain/`.
- The application layer (`shop/application/`) may import the domain and passes domain types between the domain and the outside world.
- The infrastructure layer (`shop/infrastructure/`) may import the domain and owns the persistence adapters.
- Dependencies point inward: infrastructure may import the domain; the domain never imports infrastructure; the application layer may import the domain.
