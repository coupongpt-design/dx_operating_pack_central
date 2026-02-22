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
    img_bgr, _ = decode_png_with_mask(png)
    return img_bgr

def decode_png_with_mask(png: bytes | None) -> tuple[np.ndarray | None, np.ndarray | None]:
    """
    Decode PNG bytes and optionally extract alpha mask.
    Returns:
      - bgr image (always 3-channel when not None)
      - alpha mask (uint8 0/255) or None
    """
    if not png:
        return None, None
    data = np.frombuffer(png, np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None, None

    if len(img.shape) == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return bgr, None

    if len(img.shape) == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
        # Skip mask when fully opaque to avoid unnecessary overhead.
        if np.all(alpha == 255):
            return bgr, None
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
        return bgr, np.ascontiguousarray(mask)

    if len(img.shape) == 3 and img.shape[2] == 3:
        return img, None

    return None, None

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
