# Architecture rules (benchmark case)

Layers, from inner to outer:
- domain: entities and pure rules. May import only the standard library and other domain modules. An import placed under `if TYPE_CHECKING:` is allowed when it is used only in annotations (type-only), because it does not exist at runtime.
- application: use cases. May import domain and application ports (Protocol interfaces). Must not import vendor SDKs or adapters.
- infrastructure: adapters that implement application ports with the system clock, vendor SDKs or HTTP clients. May import application ports and domain.
- composition root (main.py): wires infrastructure into use cases. May import everything.

Dependency rule: source imports point inward only. Infrastructure and the composition root are the only places that read the system clock or construct vendor clients. Domain code receives time and clients as parameters. Environment values come from settings, never literals in logic.
