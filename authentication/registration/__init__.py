from importlib import import_module
from pathlib import Path

from .registry import get_factory  

_factories_dir = Path(__file__).with_suffix("").parent / "factories"
for p in _factories_dir.glob("*.py"):
    import_module(f"{__package__}.factories.{p.stem}")

__all__ = ["get_factory"]
