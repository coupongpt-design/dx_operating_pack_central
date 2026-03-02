from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path


def _load_dx_module():
    target = Path(__file__).resolve().parents[1] / "dx_operating_pack" / "tools" / "context_compressor.py"
    spec = importlib.util.spec_from_file_location("dx_context_compressor", target)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load dx tool: {target}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_dx = _load_dx_module()
for _k, _v in _dx.__dict__.items():
    if _k in {"__name__", "__file__", "__package__", "__spec__"}:
        continue
    globals()[_k] = _v


if __name__ == "__main__":
    _main = getattr(_dx, "main")
    _params = inspect.signature(_main).parameters
    if len(_params) == 0:
        raise SystemExit(_main())
    raise SystemExit(_main(sys.argv[1:]))
