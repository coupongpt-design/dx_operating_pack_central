from PyQt5.QtCore import QSettings
from ..utils.common import hk_normalize

class ConfigManager:
    def __init__(self):
        self.settings = QSettings("ImageMacro", "MVP")

    @staticmethod
    def _hotkey_or_default(value, default):
        normalized = hk_normalize(value)
        return normalized or default

    @staticmethod
    def _to_int(value, default):
        try:
            if value is None or value == "":
                return int(default)
            return int(value)
        except (TypeError, ValueError, OverflowError):
            try:
                return int(float(value))
            except (TypeError, ValueError, OverflowError):
                return int(default)

    @staticmethod
    def _to_float(value, default):
        try:
            if value is None or value == "":
                return float(default)
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return float(default)
        
    # --- Hotkeys ---
    def load_hotkeys(self):
        return {
            "run": self._hotkey_or_default(self.settings.value("hotkeys/run", "end"), "end"),
            "stop": self._hotkey_or_default(self.settings.value("hotkeys/stop", "home"), "home"),
            "record": self._hotkey_or_default(self.settings.value("hotkeys/record", "f9"), "f9"),
            "add_img": self._hotkey_or_default(self.settings.value("hotkeys/add_img", "ctrl+shift+i"), "ctrl+shift+i"),
            "add_notimg": self._hotkey_or_default(self.settings.value("hotkeys/add_notimg", "ctrl+shift+n"), "ctrl+shift+n")
        }

    def save_hotkeys(self, hotkeys: dict):
        defaults = {
            "run": "end",
            "stop": "home",
            "record": "f9",
            "add_img": "ctrl+shift+i",
            "add_notimg": "ctrl+shift+n",
        }
        self.settings.setValue("hotkeys/run", self._hotkey_or_default(hotkeys.get("run"), defaults["run"]))
        self.settings.setValue("hotkeys/stop", self._hotkey_or_default(hotkeys.get("stop"), defaults["stop"]))
        self.settings.setValue("hotkeys/record", self._hotkey_or_default(hotkeys.get("record"), defaults["record"]))
        self.settings.setValue("hotkeys/add_img", self._hotkey_or_default(hotkeys.get("add_img"), defaults["add_img"]))
        self.settings.setValue("hotkeys/add_notimg", self._hotkey_or_default(hotkeys.get("add_notimg"), defaults["add_notimg"]))

    # --- Recording Settings ---
    def load_record_settings(self):
        raw_delay = self.settings.value("rec/record_delay_enabled", "1")
        if isinstance(raw_delay, bool):
            record_delay_enabled = raw_delay
        elif isinstance(raw_delay, (int, float)):
            record_delay_enabled = bool(raw_delay)
        else:
            record_delay_enabled = str(raw_delay).strip().lower() in ("1", "true", "yes", "y", "on")
        return {
            "typed_gap_ms": self._to_int(self.settings.value("rec/typed_gap_ms", 500), 500),
            "click_merge_ms": self._to_int(self.settings.value("rec/click_merge_ms", 350), 350),
            "click_radius_px": self._to_int(self.settings.value("rec/click_radius_px", 3), 3),
            "scroll_flush_ms": self._to_int(self.settings.value("rec/scroll_flush_ms", 180), 180),
            "scroll_scale_dx": self._to_float(self.settings.value("rec/scroll_scale_dx", 30.0), 30.0),
            "scroll_scale_dy": self._to_float(self.settings.value("rec/scroll_scale_dy", 120.0), 120.0),
            "record_delay_enabled": record_delay_enabled,
        }

    def save_record_settings(self, settings: dict):
        self.settings.setValue("rec/typed_gap_ms", self._to_int(settings.get("typed_gap_ms"), 500))
        self.settings.setValue("rec/click_merge_ms", self._to_int(settings.get("click_merge_ms"), 350))
        self.settings.setValue("rec/click_radius_px", self._to_int(settings.get("click_radius_px"), 3))
        self.settings.setValue("rec/scroll_flush_ms", self._to_int(settings.get("scroll_flush_ms"), 180))
        self.settings.setValue("rec/scroll_scale_dx", self._to_float(settings.get("scroll_scale_dx"), 30.0))
        self.settings.setValue("rec/scroll_scale_dy", self._to_float(settings.get("scroll_scale_dy"), 120.0))
        self.settings.setValue("rec/record_delay_enabled", settings.get("record_delay_enabled"))
