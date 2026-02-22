import json
from dataclasses import asdict
from pathlib import Path

from app.core.models import StepData


def _roundtrip(tmp_path: Path, steps, ext: str):
    path = tmp_path / f"macro{ext}"
    payload = [asdict(s) for s in steps]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded_raw = json.loads(path.read_text(encoding="utf-8"))
    return [StepData(**item) for item in loaded_raw]


def test_macro_io_preserves_fields(tmp_path):
    steps = [
        StepData(id="s0", name="OCR Store", type="ocr_store", ocr_store_var="hp"),
        StepData(
            id="s1",
            name="Jump If",
            type="jump_if",
            condition_var="hp",
            condition_operator="<",
            condition_value=50,
            jump_to_step_id="s3",
            jump_to_index=3,
        ),
        StepData(
            id="s2",
            name="Call Child",
            type="run_macro",
            target_macro_path="child.macro",
        ),
        StepData(id="s3", name="Log", type="comment"),
    ]

    # Optionally attach ROI if the model supports it.
    if hasattr(steps[0], "ocr_roi"):
        steps[0].ocr_roi = {"x": 1, "y": 1, "w": 2, "h": 2}

    for ext in (".json", ".macro"):
        loaded = _roundtrip(tmp_path, steps, ext)
        assert loaded[0].ocr_store_var == "hp"
        assert loaded[1].jump_to_step_id == "s3"
        assert loaded[2].target_macro_path.endswith("child.macro")
        assert len(loaded) == 4
