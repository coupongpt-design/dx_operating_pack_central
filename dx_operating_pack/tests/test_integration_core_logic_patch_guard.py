from pathlib import Path


INTEGRATION_FILES = sorted(
    set(Path("tests").glob("*integration*.py")) | set(Path("tests").glob("*e2e*.py"))
)

# These internal paths are critical business logic and must not be bypassed in integration tests.
FORBIDDEN_MONKEYPATCH_TARGETS = (
    "_build_excel_payload_runner",
    "_get_excel_text_template",
    "TemplateProcessor.render",
    "JobQueueManager.request_job",
    "JobQueueManager.ack_fail",
    "JobQueueManager.ack_success",
    "JobQueueManager.get_recommended_sleep_sec",
    "SessionJobAdapter._worker_loop",
    "MacroRunner._acquire_input_lock",
)


def test_integration_tests_do_not_patch_core_binding_queue_lock_logic():
    violations: list[str] = []
    for path in INTEGRATION_FILES:
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            if "monkeypatch.setattr" not in line:
                continue
            for token in FORBIDDEN_MONKEYPATCH_TARGETS:
                if token in line:
                    violations.append(f"{path}:{idx}: {line.strip()}")

    assert not violations, "core-logic monkeypatch violation(s):\n" + "\n".join(violations)
