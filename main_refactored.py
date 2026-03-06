from __future__ import annotations

import runpy
import sys
from pathlib import Path


def _run_macro_entry() -> None:
    root = Path(__file__).resolve().parent
    macro_dir = root / "macro"
    target = macro_dir / "main_refactored.py"
    if not target.exists():
        raise FileNotFoundError(f"missing runtime entry: {target}")

    # Keep legacy root execution path: `python main_refactored.py`
    # while actual implementation lives under `macro/`.
    sys.path.insert(0, str(root))
    runpy.run_module("macro.main_refactored", run_name="__main__")


if __name__ == "__main__":
    _run_macro_entry()
    
