# Architecture rules (benchmark case)

Layers, from inner to outer:
- domain: entities and pure rules. May import only the standard library and other domain modules.
- application: use cases. May import domain and application ports (Protocol interfaces). Must not import vendor SDKs or adapters.
- adapters: implement application ports with vendor SDKs or HTTP clients. May import application ports and domain.
- composition root (main.py): wires adapters into use cases. May import everything.

Dependency rule: source imports point inward only. Adapters and the composition root are the only places that construct vendor clients. Environment values come from settings, never literals in logic.
