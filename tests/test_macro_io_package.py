import json
import zipfile

import cv2
import numpy as np

from app.core.models import RepeatConfig, StepData
from app.io.macro_io import MacroIO


def _tiny_png_bytes() -> bytes:
    img = np.zeros((4, 4, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    return enc.tobytes()


def test_save_macro_writes_template_and_assets(tmp_path):
    png = _tiny_png_bytes()
    steps = [
        StepData(
            id="img1",
            name="Img",
            type="image_click",
            png_bytes=png,
            relative_target_enabled=True,
            relative_target_png_bytes=png,
            relative_target_image_path="target.png",
        ),
        StepData(
            id="br1",
            name="Branch",
            type="image_branch",
            conditional_targets=[{"id": "t1", "name": "T1", "goto_id": None, "png_bytes": png}],
        ),
    ]
    path = tmp_path / "pack.macro"
    MacroIO.save_macro(str(path), steps, RepeatConfig(repeat_count=2), meta={"target_window": "Notepad"})

    with zipfile.ZipFile(path, "r") as z:
        names = set(z.namelist())
        assert "template.json" in names
        assert "assets/img1.png" in names
        assert "assets/img1_relative_target.png" in names
        assert "assets/t1.png" in names
        payload = json.loads(z.read("template.json").decode("utf-8"))

    assert payload["repeat"]["repeat_count"] == 2
    assert payload["steps"][0]["image_path"] == "assets/img1.png"
    assert payload["steps"][0]["relative_target_image_path"] == "assets/img1_relative_target.png"
    assert payload["steps"][1]["conditional_targets"][0]["image_path"] == "assets/t1.png"
    assert payload.get("meta", {}).get("target_window") == "Notepad"


def test_load_macro_restores_relative_target_asset(tmp_path):
    png = _tiny_png_bytes()
    path = tmp_path / "relative.macro"
    payload = {
        "schema_version": 1,
        "repeat": {},
        "steps": [
            {
                "id": "i1",
                "name": "Relative",
                "type": "image_click",
                "image_path": "assets/i1.png",
                "relative_target_enabled": True,
                "relative_target_image_path": "assets/i1_relative_target.png",
            },
        ],
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("template.json", json.dumps(payload, ensure_ascii=False, indent=2))
        z.writestr("assets/i1.png", png)
        z.writestr("assets/i1_relative_target.png", png)

    steps, _ = MacroIO.load_macro(str(path))

    assert len(steps) == 1
    assert steps[0].png_bytes == png
    assert steps[0].relative_target_png_bytes == png


def test_load_macro_supports_legacy_scenario_images(tmp_path):
    png = _tiny_png_bytes()
    path = tmp_path / "legacy.macro"
    payload = {
        "version": "2.0",
        "repeat": {"repeat_count": 3, "repeat_cooldown_ms": 0, "stop_on_fail": True, "max_duration_ms": 0},
        "steps": [
            {"id": "w1", "name": "WaitFor", "type": "wait_for_image", "image_path": "images/w1.png"},
        ],
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("scenario.json", json.dumps(payload, ensure_ascii=False, indent=2))
        z.writestr("images/w1.png", png)

    steps, rc = MacroIO.load_macro(str(path))

    assert rc.repeat_count == 3
    assert len(steps) == 1
    assert steps[0].type == "wait_for_image"
    assert steps[0].png_bytes is not None
    assert steps[0].png_bytes == png


def test_load_macro_blocks_unsafe_asset_paths(tmp_path):
    png = _tiny_png_bytes()
    path = tmp_path / "unsafe.macro"
    payload = {
        "schema_version": 1,
        "repeat": {},
        "steps": [
            {"id": "u1", "name": "Unsafe", "type": "wait_for_image", "image_path": "../evil.png"},
        ],
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("template.json", json.dumps(payload, ensure_ascii=False, indent=2))
        z.writestr("../evil.png", png)

    steps, _ = MacroIO.load_macro(str(path))
    assert len(steps) == 1
    assert steps[0].png_bytes is None
