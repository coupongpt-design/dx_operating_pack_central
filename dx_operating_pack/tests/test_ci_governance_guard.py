from __future__ import annotations

from tools.ci_governance_guard import _validate_commit_tests_semantics


def test_semantics_risk_requires_full_suite_pass_fail() -> None:
    msg = """Tests:
- targeted: PASS (3 passed)
- full suite: not required (no risk trigger)
"""
    errors = _validate_commit_tests_semantics(msg, risk=True)
    assert any("risk commit" in err for err in errors)


def test_semantics_non_risk_allows_not_required() -> None:
    msg = """Tests:
- targeted: PASS (3 passed)
- full suite: not required (no risk trigger)
"""
    assert _validate_commit_tests_semantics(msg, risk=False) == []
