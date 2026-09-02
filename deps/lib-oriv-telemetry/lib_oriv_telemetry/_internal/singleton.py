"""Singleton metaclass used by long-lived telemetry providers."""

from typing import Any


class SingletonMeta(type):
    """Metaclass enforcing a single instance per concrete class.

    Subsequent constructor calls return the cached instance and
    silently ignore new arguments; callers must not rely on
    re-initialisation behaviour.
    """

    _instances: dict[type, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
