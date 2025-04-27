from typing import Dict
from .base import AbstractRegistrationFactory

_FACTORIES: Dict[str, AbstractRegistrationFactory] = {}


def register_factory(cls: type[AbstractRegistrationFactory]) -> type:
    """Decorator – run on import time."""
    _FACTORIES[cls.base_role_name.upper()] = cls()
    return cls


def get_factory(role_name: str) -> AbstractRegistrationFactory:
    try:
        return _FACTORIES[role_name.upper()]
    except KeyError as exc:
        raise ValueError(f"Unknown role {role_name!r}. Available: {list(_FACTORIES)}") from exc
