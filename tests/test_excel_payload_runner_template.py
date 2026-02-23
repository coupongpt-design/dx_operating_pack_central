from contextlib import contextmanager

from app.core.models import StepData


class _FakeInputLockManager:
    def __init__(self):
        self.operations = []

    @contextmanager
    def acquire(self, timeout_sec=10.0, owner="", operation=""):
        self.operations.append(("enter", str(operation)))
        try:
            yield object()
        finally:
            self.operations.append(("exit", str(operation)))


def _build_window(monkeypatch, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    return win


def test_excel_payload_runner_replaces_double_brace_token(monkeypatch, qapp, qtbot):
    from app import main as main_module

    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.steps = [StepData(id="s1", name="text", type="text", key_string="{{user_name}}")]

    runner = win._build_excel_payload_runner()
    runner.execute_job({"user_name": "Alice"})

    assert typed
    assert typed[-1][0] == "Alice"
    win.close()


def test_excel_payload_runner_uses_payload_text_when_template_missing(monkeypatch, qapp, qtbot):
    from app import main as main_module

    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.steps = []

    runner = win._build_excel_payload_runner()
    runner.execute_job({"text": "hi {{user_name}}", "user_name": "Bob"})

    assert typed
    assert typed[-1][0] == "hi Bob"
    win.close()


def test_excel_payload_runner_template_has_priority_and_case_insensitive_binding(monkeypatch, qapp, qtbot):
    from app import main as main_module

    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.steps = [StepData(id="s1", name="text", type="text", key_string="{{USER_NAME}}")]

    runner = win._build_excel_payload_runner()
    runner.execute_job({"message": "should-not-win", "user_name": "Alice"})

    assert typed
    assert typed[-1][0] == "Alice"
    win.close()


def test_excel_payload_runner_blocks_unresolved_placeholder(monkeypatch, qapp, qtbot):
    import pytest
    from app import main as main_module

    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.steps = [StepData(id="s1", name="text", type="text", key_string="{{user_name}}")]

    runner = win._build_excel_payload_runner()
    with pytest.raises(RuntimeError, match="unresolved_placeholder"):
        runner.execute_job({})

    assert typed == []
    win.close()


def test_excel_payload_runner_fallback_uses_keyboard_text_step(monkeypatch, qapp, qtbot):
    from app import main as main_module

    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.steps = [
        StepData(
            id="k1",
            name="keyboard",
            type="keyboard",
            keyboard_mode="text",
            key_string="Hello {{user_name}}",
        )
    ]

    runner = win._build_excel_payload_runner()
    runner.execute_job({"user_name": "Eve"})

    assert typed
    assert typed[-1][0] == "Hello Eve"
    win.close()


def test_excel_payload_runner_uses_clipboard_paste_for_non_ascii(monkeypatch, qapp, qtbot):
    from app import main as main_module

    typed = []
    hotkeys = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))
    monkeypatch.setattr(main_module.pyautogui, "hotkey", lambda *keys: hotkeys.append(keys))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.steps = []

    runner = win._build_excel_payload_runner()
    copied = []
    monkeypatch.setattr(runner, "_get_clipboard_text", lambda: "prev")
    monkeypatch.setattr(runner, "_set_clipboard_text", lambda text: copied.append(text) or True)
    runner.execute_job({"text": "김철수 1번"})

    assert typed == []
    assert hotkeys == [("ctrl", "v")]
    assert copied[0] == "김철수 1번"
    assert copied[-1] == "prev"
    win.close()


def test_excel_payload_runner_ascii_write_is_locked(monkeypatch, qapp, qtbot):
    from app import main as main_module

    fake_lock = _FakeInputLockManager()
    monkeypatch.setattr(main_module, "get_global_input_manager", lambda: fake_lock)
    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    runner = win._build_excel_payload_runner()
    runner.execute_job({"text": "hello"})

    assert typed
    assert ("enter", "keyboard_typewrite") in fake_lock.operations
    assert ("exit", "keyboard_typewrite") in fake_lock.operations
    win.close()


def test_excel_payload_runner_non_ascii_paste_is_locked(monkeypatch, qapp, qtbot):
    from app import main as main_module

    fake_lock = _FakeInputLockManager()
    monkeypatch.setattr(main_module, "get_global_input_manager", lambda: fake_lock)
    hotkeys = []
    monkeypatch.setattr(main_module.pyautogui, "hotkey", lambda *keys: hotkeys.append(keys))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    runner = win._build_excel_payload_runner()
    monkeypatch.setattr(runner, "_get_clipboard_text", lambda: "prev")
    monkeypatch.setattr(runner, "_set_clipboard_text", lambda text: True)
    runner.execute_job({"text": "한글"})

    assert hotkeys == [("ctrl", "v")]
    assert ("enter", "keyboard_paste") in fake_lock.operations
    assert ("exit", "keyboard_paste") in fake_lock.operations
    win.close()


def test_excel_payload_runner_auto_enter_for_ascii_text(monkeypatch, qapp, qtbot):
    from app import main as main_module

    typed = []
    pressed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append((text, interval)))
    monkeypatch.setattr(main_module.pyautogui, "press", lambda key: pressed.append(key))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.chkAutoEnterAfterText.setChecked(True)
    runner = win._build_excel_payload_runner()
    runner.execute_job({"text": "hello"})

    assert typed
    assert pressed == ["enter"]
    win.close()


def test_excel_payload_runner_auto_enter_for_non_ascii_paste(monkeypatch, qapp, qtbot):
    from app import main as main_module

    hotkeys = []
    pressed = []
    monkeypatch.setattr(main_module.pyautogui, "hotkey", lambda *keys: hotkeys.append(keys))
    monkeypatch.setattr(main_module.pyautogui, "press", lambda key: pressed.append(key))

    win = _build_window(monkeypatch, qtbot)
    win.chkDry.setChecked(False)
    win.chkAutoEnterAfterText.setChecked(True)
    runner = win._build_excel_payload_runner()
    monkeypatch.setattr(runner, "_get_clipboard_text", lambda: "prev")
    monkeypatch.setattr(runner, "_set_clipboard_text", lambda text: True)
    runner.execute_job({"text": "한글"})

    assert hotkeys == [("ctrl", "v")]
    assert pressed == ["enter"]
    win.close()


def test_excel_worker_note_shows_template_token_and_resolved_value(monkeypatch, qapp, qtbot):
    win = _build_window(monkeypatch, qtbot)
    win.steps = [StepData(id="s1", name="text", type="text", key_string="{{USER_NAME}}")]
    win._excel_payload_by_job_id = {"excel-2": {"user_name": "김철수", "message": "unused"}}

    note = win._build_excel_worker_note(
        {"event": "job_dispatched", "job_id": "excel-2", "consumer_id": "excel-1"}
    )

    assert note == "[Worker 1] 처리 중: {{USER_NAME}} -> 김철수"
    win.close()
