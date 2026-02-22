import types
from unittest.mock import patch

from app.core.runner import MacroRunner
from app.core.models import StepData, RepeatConfig


class _FakeMSS:
    """Minimal fake mss context to satisfy runner without real screen access."""

    def __init__(self):
        self.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def grab(self, region):
        raise RuntimeError("grab should not be called in this test")


def test_jump_if_skips_and_jumps(monkeypatch):
    # Steps: OCR store -> jump_if -> comment(skip) -> comment(run)
    s0 = StepData(id="s0", name="OCR Store", type="ocr_store", ocr_store_var="hp")
    s1 = StepData(
        id="s1",
        name="Jump If",
        type="jump_if",
        condition_var="hp",
        condition_operator="<",
        condition_value=500,
        jump_to_index=3,
    )
    s2 = StepData(id="s2", name="Should Skip", type="comment")
    s3 = StepData(id="s3", name="Healed", type="comment")

    runner = MacroRunner([s0, s1, s2, s3], repeat=RepeatConfig(repeat_count=1), dry_run=True)

    # Patch mss and ocr_store to avoid real screen access.
    monkeypatch.setattr("app.core.runner.mss", types.SimpleNamespace(mss=lambda: _FakeMSS()))
    def fake_ocr_store(sct, mon, step):
        runner.variable_context["hp"] = 200
        return True
    runner._ocr_store = fake_ocr_store  # type: ignore

    visited = []
    real_exec = runner._exec_step
    def wrapped_exec(sct, mon, step, idx):
        visited.append(idx)
        return real_exec(sct, mon, step, idx)
    runner._exec_step = wrapped_exec  # type: ignore

    logs = []
    runner.log.connect(lambda msg: logs.append(msg))

    runner.run()

    # Expect step 2 skipped, step 3 executed due to jump
    assert visited == [0, 1, 3]
    assert any("Condition TRUE" in m for m in logs)
    assert "Healed" in runner.steps[visited[-1]].name
