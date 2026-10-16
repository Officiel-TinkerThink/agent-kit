# Lab Inventory Service: Repository Rules

- New config keys must be added to config.defaults.toml with a default value.
- No network calls at import time: modules must not open sockets, send HTTP requests or read remote resources while being imported. Do the work inside functions called at runtime.
