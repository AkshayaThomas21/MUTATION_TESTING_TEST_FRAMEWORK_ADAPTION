"""
AdapterRegistry — the plugin system.

Two onboarding paths:

1. CODE adapters (`adapters/*_adapter.py`): subclass BaseAdapter, set
   `capabilities`, and the registry auto-discovers them on import.

2. SPEC adapters (`adapters/specs/*.md`): a markdown file with a small YAML
   front-matter block describes a framework's syntax. A *generic, spec-driven*
   adapter is synthesized at runtime — onboarding a new framework with ZERO
   Python code. This is the scalability story for "any current or future
   BOSCH framework".

Resolution order: explicit name -> file-glob match -> default (gtest).
"""

from __future__ import annotations

import os
import re
import glob
import importlib
import inspect
import logging
from typing import Dict, List, Optional, Type

from adapters.base_adapter import BaseAdapter, AdapterCapabilities

log = logging.getLogger(__name__)

_SPECS_DIR = os.path.join(os.path.dirname(__file__), "specs")


class AdapterRegistry:
    """Singleton-ish registry of all available framework adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseAdapter] = {}
        self._discovered = False

    # ------------------------------------------------------------------ #
    # Discovery                                                          #
    # ------------------------------------------------------------------ #
    def discover(self, force: bool = False) -> "AdapterRegistry":
        if self._discovered and not force:
            return self
        self._adapters.clear()
        self._discover_code_adapters()
        self._discover_spec_adapters()
        self._discovered = True
        log.info("AdapterRegistry: %d adapters available", len(self._adapters))
        return self

    def _discover_code_adapters(self) -> None:
        pkg_dir = os.path.dirname(__file__)
        for path in glob.glob(os.path.join(pkg_dir, "*_adapter.py")):
            mod_name = os.path.splitext(os.path.basename(path))[0]
            if mod_name in ("base_adapter", "spec_adapter"):
                continue
            try:
                module = importlib.import_module(f"adapters.{mod_name}")
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Could not import adapter module %s: %s", mod_name, exc)
                continue
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseAdapter)
                    and obj is not BaseAdapter
                    and obj.__module__ == module.__name__
                ):
                    try:
                        self.register(obj())
                    except Exception as exc:  # pragma: no cover
                        log.warning("Could not instantiate %s: %s", obj.__name__, exc)

    def _discover_spec_adapters(self) -> None:
        if not os.path.isdir(_SPECS_DIR):
            return
        # Imported lazily to avoid a hard dependency if no specs exist.
        from adapters.spec_adapter import SpecAdapter, parse_spec_markdown

        for md in glob.glob(os.path.join(_SPECS_DIR, "*.md")):
            try:
                spec = parse_spec_markdown(md)
                name = spec.get("name")
                if not name or name.lower() in self._adapters:
                    continue
                self.register(SpecAdapter(spec))
            except Exception as exc:  # pragma: no cover
                log.warning("Could not load spec adapter %s: %s", md, exc)

    # ------------------------------------------------------------------ #
    # Registration / lookup                                              #
    # ------------------------------------------------------------------ #
    def register(self, adapter: BaseAdapter) -> None:
        self._adapters[adapter.capabilities.name.lower()] = adapter

    def names(self) -> List[str]:
        self.discover()
        return sorted(self._adapters.keys())

    def all(self) -> List[BaseAdapter]:
        self.discover()
        return list(self._adapters.values())

    def capabilities(self) -> List[AdapterCapabilities]:
        return [a.capabilities for a in self.all()]

    def get(self, name: str) -> BaseAdapter:
        self.discover()
        key = (name or "").lower().strip()
        if key not in self._adapters:
            raise KeyError(
                f"No adapter '{name}'. Available: {', '.join(self.names())}"
            )
        return self._adapters[key]

    def resolve(
        self, framework: Optional[str] = None, test_files: Optional[List[str]] = None
    ) -> BaseAdapter:
        """Pick the best adapter by explicit name, else by file-glob match."""
        self.discover()
        if framework:
            key = framework.lower().strip()
            if key in self._adapters:
                return self._adapters[key]
            # fuzzy: 'gtest-1.11' -> 'gtest' (guard short keys to avoid false hits)
            if len(key) >= 3:
                for k, a in self._adapters.items():
                    if key in k or k in key:
                        return a
        if test_files:
            for a in self._adapters.values():
                if any(a.matches_file(f) for f in test_files):
                    return a
        return self.get("gtest")


_REGISTRY: Optional[AdapterRegistry] = None


def get_registry() -> AdapterRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AdapterRegistry().discover()
    return _REGISTRY
