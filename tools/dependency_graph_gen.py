from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[1] / "dk_system" / "tools" / "dependency_graph_gen.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dk_tool_dependency_graph_gen", _TARGET)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load dk tool: {_TARGET}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
else:
    _dk = _load_module()
    for _k, _v in _dk.__dict__.items():
        if _k in {"__name__", "__file__", "__package__", "__spec__"}:
            continue
        globals()[_k] = _v
