import sys
from pathlib import Path

from PyQt5.QtCore import QSettings

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import ConfigManager


def _backup_values(settings: QSettings, keys: list[str]):
    return {k: (settings.contains(k), settings.value(k)) for k in keys}


def _restore_values(settings: QSettings, backup: dict[str, tuple[bool, object]]):
    for k, (had, value) in backup.items():
        if had:
            settings.setValue(k, value)
        else:
            settings.remove(k)
    settings.sync()


def test_load_hotkeys_fallback_and_normalization():
    st = QSettings("ImageMacro", "MVP")
    keys = [
        "hotkeys/run",
        "hotkeys/stop",
        "hotkeys/record",
        "hotkeys/add_img",
        "hotkeys/add_notimg",
        "hotkeys/pause",
        "hotkeys/kill",
    ]
    backup = _backup_values(st, keys)
    try:
        st.setValue("hotkeys/run", None)
        st.setValue("hotkeys/stop", "")
        st.setValue("hotkeys/record", "   ")
        st.setValue("hotkeys/add_img", " Ctrl + Shift + I ")
        st.setValue("hotkeys/add_notimg", None)
        st.setValue("hotkeys/pause", None)
        st.setValue("hotkeys/kill", "")
        st.sync()

        cfg = ConfigManager()
        hotkeys = cfg.load_hotkeys()
        assert hotkeys["run"] == "end"
        assert hotkeys["stop"] == "home"
        assert hotkeys["record"] == "f9"
        assert hotkeys["add_img"] == "ctrl+shift+i"
        assert hotkeys["add_notimg"] == "ctrl+shift+n"
        assert hotkeys["pause"] == "f10"
        assert hotkeys["kill"] == "f12"
    finally:
        _restore_values(st, backup)


def test_save_hotkeys_coerces_invalid_values_to_defaults():
    st = QSettings("ImageMacro", "MVP")
    keys = [
        "hotkeys/run",
        "hotkeys/stop",
        "hotkeys/record",
        "hotkeys/add_img",
        "hotkeys/add_notimg",
        "hotkeys/pause",
        "hotkeys/kill",
    ]
    backup = _backup_values(st, keys)
    try:
        cfg = ConfigManager()
        cfg.save_hotkeys(
            {
                "run": None,
                "stop": "",
                "record": "F10",
                "add_img": " Ctrl + Alt + I ",
                "pause": " Shift + F10 ",
                "kill": None,
            }
        )
        st.sync()

        assert st.value("hotkeys/run") == "end"
        assert st.value("hotkeys/stop") == "home"
        assert st.value("hotkeys/record") == "f10"
        assert st.value("hotkeys/add_img") == "ctrl+alt+i"
        assert st.value("hotkeys/add_notimg") == "ctrl+shift+n"
        assert st.value("hotkeys/pause") == "shift+f10"
        assert st.value("hotkeys/kill") == "f12"
    finally:
        _restore_values(st, backup)


def test_save_record_settings_coerces_invalid_numbers():
    st = QSettings("ImageMacro", "MVP")
    keys = [
        "rec/typed_gap_ms",
        "rec/click_merge_ms",
        "rec/click_radius_px",
        "rec/scroll_flush_ms",
        "rec/scroll_scale_dx",
        "rec/scroll_scale_dy",
        "rec/record_delay_enabled",
    ]
    backup = _backup_values(st, keys)
    try:
        cfg = ConfigManager()
        cfg.save_record_settings(
            {
                "typed_gap_ms": "10.9",
                "click_merge_ms": "abc",
                "click_radius_px": None,
                "scroll_flush_ms": "",
                "scroll_scale_dx": "8.5",
                "scroll_scale_dy": "bad",
                "record_delay_enabled": "yes",
            }
        )
        loaded = cfg.load_record_settings()
        assert loaded["typed_gap_ms"] == 10
        assert loaded["click_merge_ms"] == 350
        assert loaded["click_radius_px"] == 3
        assert loaded["scroll_flush_ms"] == 180
        assert loaded["scroll_scale_dx"] == 8.5
        assert loaded["scroll_scale_dy"] == 120.0
        assert loaded["record_delay_enabled"] is True
    finally:
        _restore_values(st, backup)


def test_numeric_coercion_falls_back_on_overflow_and_bad_types():
    class _BadNumber:
        def __int__(self):
            raise ValueError("bad int")

        def __float__(self):
            raise TypeError("bad float")

    assert ConfigManager._to_int("1e309", 123) == 123
    assert ConfigManager._to_int(_BadNumber(), 77) == 77
    assert ConfigManager._to_float(_BadNumber(), 4.5) == 4.5
