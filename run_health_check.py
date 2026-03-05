from __future__ import annotations

from importlib import import_module as _import_module
import sys as _sys

_impl = _import_module("macro.run_health_check")

if __name__ == "__main__":
    raise SystemExit(_impl.main())

_sys.modules[__name__] = _impl
