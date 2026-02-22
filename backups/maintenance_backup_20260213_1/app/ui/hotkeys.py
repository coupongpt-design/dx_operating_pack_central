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
        self._reg(self.mw._hk_run, 1)
        self._reg(self.mw._hk_stop, 2)
        self._reg(self.mw._hk_record, 3)

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
                return True, 0
        return False, 0

    def _parse_combo(self, combo):
        # Simple parser: "ctrl+shift+f1" -> mods, vk
        # This is a simplified version.
        # We need a map of keys to VK codes.
        # For MVP, let's support basic ones.
        
        combo = combo.lower()
        parts = combo.split('+')
        mods = 0
        if 'ctrl' in parts: mods |= MOD_CONTROL
        if 'alt' in parts: mods |= MOD_ALT
        if 'shift' in parts: mods |= MOD_SHIFT
        if 'win' in parts: mods |= MOD_WIN
        
        key = (parts[-1] or "").strip()
        if not key:
            return mods, None
        vk = self._get_vk(key)
        return mods, vk

    def _get_vk(self, key):
        # Basic map
        if len(key) == 1 and key.isalnum():
            return ord(key.upper())
        
        # Function keys
        if key.startswith('f') and key[1:].isdigit():
            return 0x70 + int(key[1:]) - 1
            
        map_ = {
            'esc': 0x1B, 'space': 0x20, 'enter': 0x0D, 'tab': 0x09,
            'escape': 0x1B,
            'backspace': 0x08,
            'ins': 0x2D, 'insert': 0x2D,
            'del': 0x2E, 'delete': 0x2E,
            'home': 0x24, 'end': 0x23,
            'pgup': 0x21, 'pageup': 0x21,
            'pgdn': 0x22, 'pagedown': 0x22,
            'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28
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
    def __init__(self, run_combo, stop_combo, rec_combo, add_img_combo, add_notimg_combo, parent=None):
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
        
        for w in (self._run, self._stop, self._rec, self._ai, self._an):
            form.addRow(w)
            
        root.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        root.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def result_hotkeys(self):
        return (
            self._run.text(), 
            self._stop.text(), 
            self._rec.text(), 
            self._ai.text(), 
            self._an.text()
        )
