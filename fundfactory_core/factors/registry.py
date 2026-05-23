"""
Factor registry - single source of truth for factor metadata and calculation.

Factor modules in fundfactory_core.factors.public are auto-loaded.
"""
import os
import importlib
import pkgutil
from typing import Callable, Optional

# Internal registry: factor_id -> {"metadata": dict, "calc_func": callable}
_registry: dict[str, dict] = {}


def register_factor(factor_id: str, metadata: dict, calc_func: Callable) -> None:
    """Register a factor with its metadata and calculation function."""
    _registry[factor_id] = {"metadata": metadata, "calc_func": calc_func}


def get_metadata(factor_id: str) -> Optional[dict]:
    """Get metadata dict for a single factor."""
    return _registry.get(factor_id, {}).get("metadata")


def get_all_metadata() -> dict[str, dict]:
    """Return all factor metadata dicts, keyed by factor_id."""
    return {fid: info["metadata"] for fid, info in _registry.items()}


def get_calc_func(factor_id: str) -> Optional[Callable]:
    """Get calculation function for a single factor."""
    return _registry.get(factor_id, {}).get("calc_func")


def get_all_calc_funcs() -> dict[str, Callable]:
    """Return all calc functions keyed by factor_id."""
    return {fid: info["calc_func"] for fid, info in _registry.items()}


def factor_ids() -> list[str]:
    """Return list of all registered factor IDs."""
    return list(_registry.keys())


def _auto_load_public_factors() -> None:
    """Auto-discover and register factors from factors_public package."""
    import fundfactory_core.factors.public as package
    package_path = os.path.dirname(package.__file__)
    for _, module_name, _ in pkgutil.iter_modules([package_path]):
        try:
            importlib.import_module(f"fundfactory_core.factors.public.{module_name}")
        except ImportError as e:
            import warnings
            warnings.warn(f"Failed to load factor module 'fundfactory_core.factors.public.{module_name}': {e}")


# Auto-load on import
_auto_load_public_factors()
