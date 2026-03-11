import run_health_check


def test_build_pytest_args_defaults_to_runtime_smoke(monkeypatch):
    monkeypatch.delenv("HEALTHCHECK_TEST_ARGS", raising=False)
    monkeypatch.delenv("HEALTHCHECK_FULL", raising=False)

    args = run_health_check._build_pytest_args()

    assert args[0] == "-q"
    assert "tests/test_e2e_runtime_orchestration.py" in args
    assert "tests/test_scheduler_core.py" in args
    assert "tests/test_trigger_engine_core.py" in args
    assert "tests/test_image_dialog_presets.py" in args
    assert "tests/test_matcher_quality.py" in args
    assert "tests/test_stepdata_serialization.py" in args
    assert "tests/test_ui_integration.py::test_mainwindow_record_path_has_no_smart_record_state" in args
    assert "tests/test_recorder_logic.py::test_recorded_scroll_keeps_pointer_position" in args
    assert "tests/test_signal_and_logic.py::test_runner_mouse_actions" in args
    assert "tests/test_runner_logic.py::test_image_click_relative_target_search_clicks_target_from_embedded_bytes" in args
    assert "tests/test_runner_logic.py::test_image_click_relative_target_search_clicks_target_with_ratio_area" in args
    assert "tests/test_macro_load_formats.py::test_save_json_roundtrip_preserves_captured_relative_target" in args


def test_build_pytest_args_uses_full_suite_when_enabled(monkeypatch):
    monkeypatch.delenv("HEALTHCHECK_TEST_ARGS", raising=False)
    monkeypatch.setenv("HEALTHCHECK_FULL", "1")

    assert run_health_check._build_pytest_args() == ["tests", "-q"]


def test_build_pytest_args_respects_custom_args(monkeypatch):
    monkeypatch.setenv(
        "HEALTHCHECK_TEST_ARGS",
        "tests/test_main_trigger_scheduler_integration.py -q --maxfail=1",
    )

    assert run_health_check._build_pytest_args() == [
        "tests/test_main_trigger_scheduler_integration.py",
        "-q",
        "--maxfail=1",
    ]


def test_main_reports_healthy_when_runner_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(run_health_check, "_run_pytest_subprocess", lambda *a, **k: 0)
    monkeypatch.delenv("HEALTHCHECK_TEST_ARGS", raising=False)
    monkeypatch.delenv("HEALTHCHECK_FULL", raising=False)

    rc = run_health_check.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "SYSTEM HEALTHY" in out


def test_main_reports_failing_when_runner_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(run_health_check, "_run_pytest_subprocess", lambda *a, **k: 2)
    monkeypatch.delenv("HEALTHCHECK_TEST_ARGS", raising=False)
    monkeypatch.delenv("HEALTHCHECK_FULL", raising=False)

    rc = run_health_check.main()
    out = capsys.readouterr().out

    assert rc == 2
    assert "SYSTEM FAILING" in out
