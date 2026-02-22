from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QColor, QPainter, QPen, QFont
from PyQt5.QtWidgets import QWidget
import time


class DebugOverlay(QWidget):
    """Transparent always-on-top overlay for visual debug."""

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.items = []  # list of dicts: {rect: QRect, text: str, color: QColor, expire: float}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._prune)
        self.timer.start(200)
        self._resize_to_screen()

    def _resize_to_screen(self):
        screen = self.screen() or self.windowHandle().screen()
        if screen:
            g = screen.geometry()
            self.setGeometry(g)

    def add_event(self, rect_tuple, text: str = "", color=(0, 255, 0), duration=2.0):
        x, y, w, h = rect_tuple
        qrect = QRect(int(x), int(y), int(w), int(h))
        qcolor = QColor(*color)
        self.items.append({"rect": qrect, "text": text, "color": qcolor, "expire": time.time() + duration})
        self.update()

    def _prune(self):
        now = time.time()
        before = len(self.items)
        self.items = [it for it in self.items if it["expire"] > now]
        if len(self.items) != before:
            self.update()

    def paintEvent(self, event):
        if not self.items:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("Consolas", 10)
        painter.setFont(font)
        for it in self.items:
            pen = QPen(it["color"])
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(it["rect"])
            if it.get("text"):
                painter.drawText(it["rect"].adjusted(2, -4, 0, -4), Qt.AlignLeft | Qt.AlignTop, it["text"])
        painter.end()
