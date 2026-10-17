# Architecture rules

- Package `shop` is split into `shop.domain`, `shop.config` and `shop.infrastructure`; `shop/main.py` is the composition root.
- The domain (`shop/domain/`) uses plain dataclasses, enums, functions and standard-library value types only.
- The domain holds no environment-specific values: no hosts, ports, service URLs or regions. The domain performs no network or file I/O.
- The domain never imports the infrastructure layer, by absolute import (`shop.infrastructure...`) or by relative import (`from ..infrastructure...`, `from .. import infrastructure`). Any import resolving inside `shop.infrastructure` is forbidden in `shop/domain/`.
- The config layer (`shop/config/`) holds the settings module, which reads environment variables with defaults. Only `shop/infrastructure/` and `shop/main.py` may import `shop.config`.
- The infrastructure layer (`shop/infrastructure/`) owns the adapters, including the tax rate client. It may import the domain; adapters receive their connection settings as constructor arguments.
- `shop/main.py` builds the adapters from the settings and wires them together.
- Dependencies point inward: infrastructure may import the domain; the domain imports nothing from the other layers.
