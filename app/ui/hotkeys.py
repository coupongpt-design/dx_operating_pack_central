import ctypes
from ctypes import wintypes
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, 
    QLabel, QDialogButtonBox, QMessageBox, QWidget, QApplication
)
from PyQt5.QtCore import Qt, QAbstractNativeEventFilter, QAbstractEventDispatcher
from PyQt5.QtGui import QKeySequence
from ..utils.common import hk_normalize, hk_pretty
from ..ui.styles import DarkTheme

# Windows API Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312

class SystemHotkeys(QAbstractNativeEventFilter):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.registered = {} # id -> (mods, vk)
        self.next_id = 1
        self.is_installed = False

    def install(self):
        if self.is_installed: return
        app = QApplication.instance()
        app.installNativeEventFilter(self)
        self.is_installed = True
        self._register_all()

    def uninstall(self):
        if not self.is_installed: return
        app = QApplication.instance()
        app.removeNativeEventFilter(self)
        self.is_installed = False
        self._unregister_all()

    def _register_all(self):
        self._reg(getattr(self.mw, "_hk_run", ""), 1)
        self._reg(getattr(self.mw, "_hk_stop", ""), 2)
        self._reg(getattr(self.mw, "_hk_record", ""), 3)
        self._reg(getattr(self.mw, "_hk_pause", ""), 4)
        self._reg(getattr(self.mw, "_hk_kill", ""), 5)

    def _unregister_all(self):
        for hk_id in list(self.registered.keys()):
            ctypes.windll.user32.UnregisterHotKey(int(self.mw.winId()), hk_id)
        self.registered.clear()

    def _reg(self, combo, hk_id):
        if not combo: return
        mods, vk = self._parse_combo(combo)
        if vk is None:
            print(f"Skipped invalid hotkey: {combo}")
            return
        
        ok = ctypes.windll.user32.RegisterHotKey(int(self.mw.winId()), hk_id, mods, vk)
        if ok:
            self.registered[hk_id] = (mods, vk)
        else:
            print(f"Failed to register hotkey: {combo}")

    def nativeEventFilter(self, eventType, message):
        if eventType == "windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_HOTKEY:
                hk_id = msg.wParam
                if hk_id == 1:
                    self.mw._act_run_from_hotkey()
                elif hk_id == 2:
                    self.mw._act_stop_from_hotkey()
                elif hk_id == 3:
                    self.mw._act_record_from_hotkey()
                elif hk_id == 4 and hasattr(self.mw, "_act_pause_resume_from_hotkey"):
                    self.mw._act_pause_resume_from_hotkey()
                elif hk_id == 5 and hasattr(self.mw, "_act_kill_from_hotkey"):
                    self.mw._act_kill_from_hotkey()
                return True, 0
        return False, 0

    def _parse_combo(self, combo):
        combo = (combo or "").lower()
        parts = [p.strip() for p in combo.split('+') if p.strip()]
        mods = 0
        key_tokens = []
        for part in parts:
            if part in ("ctrl", "control"):
                mods |= MOD_CONTROL
            elif part == "alt":
                mods |= MOD_ALT
            elif part == "shift":
                mods |= MOD_SHIFT
            elif part in ("win", "meta", "super"):
                mods |= MOD_WIN
            else:
                key_tokens.append(part)

        if len(key_tokens) != 1:
            return mods, None
        return mods, self._get_vk(key_tokens[0])

    def _get_vk(self, key):
        key = (key or "").strip().lower()
        if not key:
            return None

        # Alnum keys
        if len(key) == 1 and key.isalnum():
            return ord(key.upper())

        # Function keys (F1~F24)
        if key.startswith('f') and key[1:].isdigit():
            idx = int(key[1:])
            if 1 <= idx <= 24:
                return 0x70 + idx - 1
            return None

        # NumPad numeric keys
        if key.startswith("num") and key[3:].isdigit():
            idx = int(key[3:])
            if 0 <= idx <= 9:
                return 0x60 + idx
        if key.startswith("numpad") and key[6:].isdigit():
            idx = int(key[6:])
            if 0 <= idx <= 9:
                return 0x60 + idx

        map_ = {
            'esc': 0x1B, 'space': 0x20, 'enter': 0x0D, 'tab': 0x09,
            'escape': 0x1B,
            'return': 0x0D,
            'spacebar': 0x20,
            'backspace': 0x08,
            'ins': 0x2D, 'insert': 0x2D,
            'del': 0x2E, 'delete': 0x2E,
            'capslock': 0x14,
            'numlock': 0x90,
            'scrolllock': 0x91,
            'pause': 0x13,
            'printscreen': 0x2C,
            'prtsc': 0x2C,
            'apps': 0x5D,
            'menu': 0x5D,
            'home': 0x24, 'end': 0x23,
            'pgup': 0x21, 'pageup': 0x21,
            'pgdn': 0x22, 'pagedown': 0x22,
            'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
            'multiply': 0x6A, 'num*': 0x6A, 'num_mul': 0x6A, 'numpad*': 0x6A,
            'add': 0x6B, 'num+': 0x6B, 'num_add': 0x6B, 'numpad+': 0x6B,
            'subtract': 0x6D, 'num-': 0x6D, 'num_sub': 0x6D, 'numpad-': 0x6D,
            'decimal': 0x6E, 'num.': 0x6E, 'num_dec': 0x6E, 'numpad.': 0x6E,
            'divide': 0x6F, 'num/': 0x6F, 'num_div': 0x6F, 'numpad/': 0x6F,
            ';': 0xBA, 'semicolon': 0xBA,
            '=': 0xBB, 'equals': 0xBB,
            ',': 0xBC, 'comma': 0xBC,
            '-': 0xBD, 'minus': 0xBD,
            '.': 0xBE, 'period': 0xBE, 'dot': 0xBE,
            '/': 0xBF, 'slash': 0xBF,
            '`': 0xC0, 'backtick': 0xC0, 'tilde': 0xC0,
            '[': 0xDB, 'lbracket': 0xDB,
            '\\': 0xDC, 'backslash': 0xDC,
            ']': 0xDD, 'rbracket': 0xDD,
            "'": 0xDE, 'quote': 0xDE,
        }
        return map_.get(key)

class _KeyCapG(QWidget):
    def __init__(self, label, initial, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.lbl = QLabel(label)
        self.btn = QPushButton(initial or "None")
        self.btn.setCheckable(True)
        self.btn.toggled.connect(self._on_toggle)
        self.btn.setStyleSheet("text-align: left; padding: 5px;")
        layout.addWidget(self.lbl)
        layout.addWidget(self.btn)
        self.recording = False
        
    def _on_toggle(self, checked):
        if checked:
            self.btn.setText("Press keys...")
            self.recording = True
            self.grabKeyboard()
        else:
            self.recording = False
            self.releaseKeyboard()
            
    def keyPressEvent(self, e):
        if not self.recording: return
        
        mod = e.modifiers()
        key = e.key()
        
        # Ignore modifier-only presses
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
            
        parts = []
        if mod & Qt.ControlModifier: parts.append("ctrl")
        if mod & Qt.ShiftModifier: parts.append("shift")
        if mod & Qt.AltModifier: parts.append("alt")
        if mod & Qt.MetaModifier: parts.append("win")
        
        # Key mapping
        kstr = QKeySequence(key).toString().lower()
        parts.append(kstr)
        
        res = "+".join(parts)
        self.btn.setText(res)
        self.btn.setChecked(False)
        
    def text(self):
        t = self.btn.text()
        return "" if t in ("None", "Press keys...") else t


class HotkeySettingsDialog(QDialog):
    def __init__(
        self,
        run_combo,
        stop_combo,
        rec_combo,
        pause_combo,
        kill_combo,
        add_img_combo,
        add_notimg_combo,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle('Hotkeys (Capture)')
        self.setStyleSheet(DarkTheme.get_stylesheet())
        root = QVBoxLayout(self)
        form = QFormLayout()
        
        self._run = _KeyCapG('Run', run_combo, self)
        self._stop = _KeyCapG('Stop', stop_combo, self)
        self._rec = _KeyCapG('Record', rec_combo, self)
        self._ai = _KeyCapG('Add Image', add_img_combo, self)
        self._an = _KeyCapG('Add Action', add_notimg_combo, self)
        self._pause = _KeyCapG('Pause/Resume', pause_combo, self)
        self._kill = _KeyCapG('Emergency Kill', kill_combo, self)
        
        for w in (self._run, self._stop, self._rec, self._pause, self._kill, self._ai, self._an):
            form.addRow(w)
            
        root.addLayout(form)
        self.lblConflict = QLabel("")
        self.lblConflict.setStyleSheet("color: #ff7f7f; padding: 4px 0;")
        root.addWidget(self.lblConflict)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        root.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def _collect_hotkeys(self):
        return {
            "Run": self._run.text(),
            "Stop": self._stop.text(),
            "Record": self._rec.text(),
            "Pause/Resume": self._pause.text(),
            "Emergency Kill": self._kill.text(),
            "Add Image": self._ai.text(),
            "Add Action": self._an.text(),
        }

    def _find_conflicts(self):
        by_combo = {}
        for label, combo in self._collect_hotkeys().items():
            normalized = hk_normalize(combo)
            if not normalized:
                continue
            by_combo.setdefault(normalized, []).append(label)
        return {combo: labels for combo, labels in by_combo.items() if len(labels) > 1}

    def accept(self):
        conflicts = self._find_conflicts()
        if conflicts:
            first_combo = sorted(conflicts.keys())[0]
            labels = ", ".join(conflicts[first_combo])
            self.lblConflict.setText(
                f"이미 사용 중인 단축키입니다: {first_combo} ({labels})"
            )
            return
        self.lblConflict.clear()
        super().accept()

    def result_hotkeys(self):
        return (
            self._run.text(), 
            self._stop.text(), 
            self._rec.text(), 
            self._pause.text(),
            self._kill.text(),
            self._ai.text(), 
            self._an.text()
        )
