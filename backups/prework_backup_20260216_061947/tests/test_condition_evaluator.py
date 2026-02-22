from app.core.evaluator import ConditionEvaluator
from app.core.models import StepData


def test_condition_evaluator_parses_commas():
    evaluator = ConditionEvaluator()
    step = StepData(
        id="s1",
        name="Jump",
        type="jump_if",
        condition_var="hp",
        condition_operator="<",
        condition_value="1,000",
    )

    ok, _ = evaluator.evaluate(step, {"hp": 500})
    assert ok is True

    ok, _ = evaluator.evaluate(step, {"hp": 1500})
    assert ok is False
