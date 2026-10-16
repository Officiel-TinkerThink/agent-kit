"""Registry of report handlers used by the batch-record export service."""

import logging

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Raised when a handler name or callable is rejected by the registry."""


class HandlerRegistry:
    """Maps report names to callables. Names are unique within a registry."""

    def __init__(self):
        self._handlers = {}

    def register(self, name, handler):
        """Register handler under name; a name can be registered once."""
        if not isinstance(name, str) or not name:
            raise RegistryError("name must be a non-empty string")
        if not callable(handler):
            raise RegistryError(f"handler for {name} is not callable")
        if name in self._handlers:
            raise RegistryError(f"handler already registered: {name}")
        self._handlers[name] = handler
        logger.info("registered report handler %s", name)

    def get(self, name):
        """Return the handler registered under name."""
        try:
            return self._handlers[name]
        except KeyError as exc:
            raise RegistryError(f"unknown handler: {name}") from exc

    def names(self):
        """Return the registered names in sorted order."""
        return sorted(self._handlers)

    def unregister(self, name):
        """Remove the handler registered under name."""
        self.get(name)
        del self._handlers[name]
        logger.info("unregistered report handler %s", name)

    def replace(self, name, handler):
        """Swap the handler for an existing name and return the previous one."""
        previous = self._handlers.get(name)
        if previous == None:
            raise RegistryError(f"unknown handler: {name}")
        if not callable(handler):
            raise RegistryError(f"handler for {name} is not callable")
        self._handlers[name] = handler
        return previous

    def run(self, name, *args, **kwargs):
        """Call the handler registered under name with the given arguments."""
        handler = self.get(name)
        logger.info("running report handler %s", name)
        return handler(*args, **kwargs)

    def __contains__(self, name):
        """Return True when a handler is registered under name."""
        return name in self._handlers
