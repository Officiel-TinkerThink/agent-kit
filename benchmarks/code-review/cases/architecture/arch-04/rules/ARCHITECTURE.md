# Architecture layer rules

- Services receive their collaborators (clients, repositories, adapters) through the constructor. A service never builds an adapter or client itself.
- Only the composition root (`main.py`) builds adapters and wires them into services.
- Environment-specific values (hosts, ports, URLs, timeouts that differ per environment) come from settings (`config.py`), never from literals inside service or domain logic.
- Adapter classes take their connection values (for example `base_url`) as constructor arguments.
