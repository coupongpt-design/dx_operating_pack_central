import sys
import cv2
import numpy as np
from PyQt5.QtGui import QImage, QPixmap

def info(msg: str):
    print(f"[INFO] {msg}")

def warn(msg: str):
    print(f"[WARN] {msg}")

def err(msg: str):
    print(f"[ERROR] {msg}")

def hk_normalize(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip().lower().replace(" ", "")
    s = s.replace("ctrl+", "ctrl+").replace("shift+", "shift+").replace("alt+", "alt+").replace("win+", "win+")
    return s

def hk_to_tuple(hk_str: str | None) -> tuple[set[str], str | None]:
    if not hk_str:
        return set(), None
    parts = hk_str.lower().split('+')
    mods = set()
    base = None
    for p in parts:
        p = p.strip()
        if p in ('ctrl', 'shift', 'alt', 'win'):
            mods.add(p)
        else:
            base = p
    return mods, base




def hk_pretty(s: str | None) -> str | None:
    if not s:
        return None
    parts = s.split("+")
    parts = [p.capitalize() if p not in ("ctrl","shift","alt","win") else {"ctrl":"Ctrl","shift":"Shift","alt":"Alt","win":"Win"}[p] for p in parts]
    return "+".join(parts)

def decode_png_bytes(png: bytes | None) -> np.ndarray | None:
    if not png:
        return None
    data = np.frombuffer(png, np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img

def encode_png_bytes(img_bgr: np.ndarray) -> bytes | None:
    if img_bgr is None:
        return None
    success, enc = cv2.imencode(".png", img_bgr)
    if not success:
        return None
    return enc.tobytes()

def cvimg_to_qpixmap(img_bgr: np.ndarray) -> QPixmap:
    h, w = img_bgr.shape[:2]
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)
