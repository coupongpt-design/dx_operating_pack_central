from types import SimpleNamespace
from pathlib import Path
import sys

from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.runner import MacroRunner
from app.core.models import StepData, RepeatConfig


def _dummy_mss():
    class DummyGrab:
        def __init__(self, width: int, height: int):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class DummyCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        @property
        def monitors(self):
            return [{"left": 0, "top": 0, "width": 10, "height": 10}]

        def grab(self, region):
            w = region.get("width", 10)
            h = region.get("height", 10)
            return DummyGrab(w, h)

    return DummyCtx()


def test_scenario_hunting_loop(monkeypatch):
    """Simulate a hunting loop with phases: attack -> low HP potion -> inventory full run_macro."""
    # Prepare step list
    steps = [
        StepData(id="s0", name="Attack", type="image_click"),
        StepData(id="s1", name="HP Scan", type="ocr_store", ocr_store_var="hp"),
        StepData(
            id="s2",
            name="HP Jump",
            type="jump_if",
            condition_var="hp",
            condition_operator="<",
            condition_value=500,
            jump_to_index=3,
        ),
        StepData(id="s3", name="Potion", type="key", key_string="F1"),
        StepData(id="s4", name="Inv Scan", type="ocr_store", ocr_store_var="inv_full"),
        StepData(
            id="s5",
            name="Inv Jump",
            type="jump_if",
            condition_var="inv_full",
            condition_operator=">",
            condition_value=0,
            jump_to_index=7,
        ),
        StepData(id="s6", name="Noop", type="comment"),
        StepData(id="s7", name="ReturnTown", type="run_macro", target_macro_path="child.json"),
    ]

    runner = MacroRunner(
        steps,
        repeat=RepeatConfig(repeat_count=2),
        dry_run=False,
        capture_on_fail=False,
        human_mode=False,
    )

    # Mock mss
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=_dummy_mss))

    # Mock matcher to always find image_click
    class FakeMatch:
        def __init__(self):
            self.ok = True
            self.x = 1
            self.y = 1
            self.score = 0.99

    monkeypatch.setattr(runner, "_matcher", SimpleNamespace(find_best_optimized=lambda frame, s: FakeMatch()))

    # Mock clicks and key presses
    mock_click = MagicMock()
    monkeypatch.setattr(runner, "_perform_click", lambda x, y, s: mock_click())
    mock_press = MagicMock()
    monkeypatch.setattr("app.core.runner.pyautogui", SimpleNamespace(press=mock_press, hscroll=lambda *a, **k: None, scroll=lambda *a, **k: None))

    # Mock run_macro handler
    mock_run_macro = MagicMock(return_value=True)
    monkeypatch.setattr(runner, "_handle_run_macro", mock_run_macro)
    runner._step_handlers["run_macro"] = lambda sct, mon, s, idx: (runner._handle_run_macro(s), None, 0)

    # Mock OCR values per variable, per loop
    hp_values = [1000, 200]
    inv_values = [0, 1]

    def fake_extract_number(self, img, psm_mode=6):
        # Decide based on current step variable name stored in runner._ocr_store calls
        # We inspect the variable name by checking caller-set attribute via monkeypatch
        return None  # default fallback

    def fake_ocr_store(sct, mon, step: StepData):
        if getattr(step, "ocr_store_var", "") == "hp":
            val = hp_values.pop(0) if hp_values else 0
            runner.variable_context["hp"] = val
            return True
        if getattr(step, "ocr_store_var", "") == "inv_full":
            val = inv_values.pop(0) if inv_values else 0
            runner.variable_context["inv_full"] = val
            return True
        return False

    monkeypatch.setattr("app.core.runner.ImageProcessor.extract_number", fake_extract_number, raising=False)
    runner._ocr_store = fake_ocr_store  # type: ignore

    # Run
    runner.run()

    # Assertions per phase (given linear flow, actions fire each loop)
    # Loop 1: attack click, potion, run_macro
    # Loop 2: attack click, potion (low HP), run_macro
    assert mock_click.call_count == 2  # once per loop
    assert mock_press.call_count == 2  # potion executed per loop in current flow
    assert mock_run_macro.call_count == 2
