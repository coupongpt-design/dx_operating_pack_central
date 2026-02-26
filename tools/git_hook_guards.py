from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_dx_module():
    target = Path(__file__).resolve().parents[1] / "dx_operating_pack" / "tools" / "git_hook_guards.py"
    spec = importlib.util.spec_from_file_location("dx_git_hook_guards", target)
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
