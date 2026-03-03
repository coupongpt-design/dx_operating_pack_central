from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    script = Path(__file__).resolve().parents[1] / "dx_operating_pack" / "tools" / "promote_dx_feedback.py"
    if not script.exists():
        print(f"[fail] missing script: {script}")
        return 1
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
