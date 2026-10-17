# Architecture rules

## Layers
- Package `shop` is split into `shop.domain`, `shop.application` and `shop.infrastructure`; `shop/main.py` is the composition root.
- The domain (`shop/domain/`) uses only the standard library and imports only `shop.domain`.
- The application layer (`shop/application/`) may import `shop.domain` and `shop.application.ports`, which holds the typing.Protocol ports the use cases depend on.
- The infrastructure layer (`shop/infrastructure/`) owns the adapters and may import `shop.application.ports` and `shop.domain`.
- The composition root (`shop/main.py`) may import every layer.
- Dependencies point inward: the application layer never imports `shop.infrastructure`, by absolute import (`shop.infrastructure...`) or relative import (`from ..infrastructure...`, `from .. import infrastructure`), including under an alias.
- A port that the application layer needs is defined in `shop/application/ports.py`, and an adapter in `shop/infrastructure/` implements it.
- The domain never imports the application or infrastructure layers.
