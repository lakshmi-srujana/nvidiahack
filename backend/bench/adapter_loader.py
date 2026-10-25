from __future__ import annotations

import importlib

from bench.batch import BenchmarkAdapter


def load_adapter(spec: str) -> BenchmarkAdapter:
    if ":" not in spec:
        raise ValueError("adapter must use module:factory syntax")
    module_name, factory_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    adapter = factory()
    for attribute in ("name", "is_mock", "generate_initial", "verify", "repair", "metadata"):
        if not hasattr(adapter, attribute):
            raise TypeError(f"benchmark adapter lacks required attribute: {attribute}")
    return adapter
