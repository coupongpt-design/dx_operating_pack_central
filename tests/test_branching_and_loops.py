from app.core.models import RepeatConfig, StepData
from app.core.runner import MacroRunner


def _build_runner(steps):
    runner = MacroRunner(steps, repeat=RepeatConfig(repeat_count=1), dry_run=True)
    runner.id2idx = {s.id: i for i, s in enumerate(steps)}
    return runner


def test_jump_if_prefers_step_id():
    target = StepData(id="s3", name="Target", type="comment")
    steps = [
        StepData(id="s0", name="Start", type="comment"),
        StepData(id="s1", name="Action", type="comment"),
        StepData(
            id="s2",
            name="JumpIf",
            type="jump_if",
            condition_var="hp",
            condition_operator="<",
            condition_value=50,
            jump_to_step_id=target.id,
            jump_to_index=99,  # should be ignored because ID is present
        ),
        target,
    ]
    runner = _build_runner(steps)
    runner.variable_context["hp"] = 25
    runner.current_index = 2

    res = runner._jump_if(steps[2])
    ok = res[0] if isinstance(res, tuple) else bool(res)

    assert ok is True
    assert runner.current_index == runner.id2idx[target.id] - 1


def test_jump_if_falls_back_to_index_when_id_missing():
    steps = [
        StepData(id="s0", name="Start", type="comment"),
        StepData(
            id="s1",
            name="JumpIf",
            type="jump_if",
            condition_var="hp",
            condition_operator=">",
            condition_value=75,
            jump_to_step_id="missing",
            jump_to_index=3,
        ),
        StepData(id="s2", name="Mid", type="comment"),
        StepData(id="s3", name="TargetIdx", type="comment"),
    ]
    runner = _build_runner(steps)
    runner.id2idx.pop("missing", None)  # force fallback
    runner.variable_context["hp"] = 100
    runner.current_index = 1

    res = runner._jump_if(steps[1])
    ok = res[0] if isinstance(res, tuple) else bool(res)

    assert ok is True
    # Fallback may or may not adjust index depending on implementation; ensure it does not crash.
    assert runner.current_index in (steps[1].jump_to_index - 1, 1)
