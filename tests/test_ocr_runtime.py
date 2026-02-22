import sys
import types


class _DummySettings:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def value(self, key, default=None):
        return self._values.get(key, default)

    def setValue(self, key, value):
        self._values[key] = value


def test_resolve_tesseract_cmd_prefers_env(monkeypatch):
    from app.core import ocr_runtime as rt

    env_path = r"C:\custom\tesseract.exe"
    monkeypatch.setenv("TESSERACT_CMD", env_path)
    monkeypatch.setattr("app.core.ocr_runtime.os.path.exists", lambda p: p == env_path)
    monkeypatch.setattr("app.core.ocr_runtime.shutil.which", lambda name: None)

    cmd, source = rt.resolve_tesseract_cmd(settings=_DummySettings({"ocr/tesseract_cmd": r"C:\other.exe"}))
    assert cmd == env_path
    assert source == "env"


def test_resolve_tesseract_cmd_uses_settings_when_env_missing(monkeypatch):
    from app.core import ocr_runtime as rt

    setting_path = r"C:\settings\tesseract.exe"
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("app.core.ocr_runtime.os.path.exists", lambda p: p == setting_path)
    monkeypatch.setattr("app.core.ocr_runtime.shutil.which", lambda name: None)

    cmd, source = rt.resolve_tesseract_cmd(settings=_DummySettings({"ocr/tesseract_cmd": setting_path}))
    assert cmd == setting_path
    assert source == "settings"


def test_configure_tesseract_cmd_sets_pytesseract_module(monkeypatch):
    from app.core import ocr_runtime as rt

    env_path = r"C:\custom\tesseract.exe"
    monkeypatch.setenv("TESSERACT_CMD", env_path)
    monkeypatch.setattr("app.core.ocr_runtime.os.path.exists", lambda p: p == env_path)
    monkeypatch.setattr("app.core.ocr_runtime.shutil.which", lambda name: None)

    dummy = types.SimpleNamespace(pytesseract=types.SimpleNamespace(tesseract_cmd=""))
    monkeypatch.setitem(sys.modules, "pytesseract", dummy)

    cmd, source = rt.configure_tesseract_cmd()
    assert cmd == env_path
    assert source == "env"
    assert dummy.pytesseract.tesseract_cmd == env_path
