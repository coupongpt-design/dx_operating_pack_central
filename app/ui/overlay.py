from __future__ import annotations

import cv2
import mss
import numpy as np
from PyQt5.QtCore import QEventLoop, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QImage, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget


class VisualImageCaptureOverlay(QWidget):
    done = pyqtSignal(QRect, object, tuple)  # rect_phys, crop_bgr, (virt_left, virt_top, virt_w, virt_h)
    canceled = pyqtSignal()

    def __init__(self, frame_bgr: np.ndarray, virt_left: int, virt_top: int, virt_size: QSize, parent=None):
        super().__init__(parent, flags=Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setCursor(Qt.CrossCursor)

        self._frame_bgr = frame_bgr
        self._virt_left = int(virt_left)
        self._virt_top = int(virt_top)
        self._virt_size = virt_size
        self._drag = False
        self._start = QPoint()
        self._end = QPoint()
        self._finished = False
        self._canceled = False

        fh, fw = frame_bgr.shape[:2]
        vw = max(1, int(virt_size.width()))
        vh = max(1, int(virt_size.height()))
        self._fx = fw / float(vw)
        self._fy = fh / float(vh)

        self.setGeometry(self._virt_left, self._virt_top, vw, vh)
        self.show()
        self.raise_()
        self.activateWindow()

    def _rect_in_widget(self) -> QRect:
        return QRect(self._start, self._end).normalized()

    def _to_phys_rect(self, widget_rect: QRect) -> QRect:
        x1w = max(0, int(widget_rect.left()))
        y1w = max(0, int(widget_rect.top()))
        x2w = max(0, int(widget_rect.right()) + 1)
        y2w = max(0, int(widget_rect.bottom()) + 1)
        x1 = int(round(x1w * self._fx))
        y1 = int(round(y1w * self._fy))
        x2 = int(round(x2w * self._fx))
        y2 = int(round(y2w * self._fy))
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        return QRect(x1, y1, w, h)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rgb = cv2.cvtColor(self._frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0], 3 * rgb.shape[1], QImage.Format_RGB888)
        painter.drawImage(self.rect(), qimg)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 95))

        rect = self._rect_in_widget() if self._drag else QRect()
        if not rect.isNull() and rect.width() > 1 and rect.height() > 1:
            painter.fillRect(rect, QColor(255, 255, 255, 36))
            painter.setPen(QPen(QColor(0, 255, 170, 240), 2))
            painter.drawRect(rect)

            phys = self._to_phys_rect(rect)
            gx = self._virt_left + int(phys.x())
            gy = self._virt_top + int(phys.y())
            info = f"X:{gx}  Y:{gy}  W:{int(phys.width())}  H:{int(phys.height())}"
            text_pos = rect.topLeft() + QPoint(6, -8)
            if text_pos.y() < 20:
                text_pos = rect.topLeft() + QPoint(6, 18)
            painter.setPen(QColor(255, 255, 255, 245))
            painter.drawText(text_pos, info)

        painter.setPen(QColor(255, 235, 120, 245))
        painter.drawText(12, 24, "드래그로 캡처 영역 선택 | ESC/우클릭: 취소")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._emit_cancel()
            return
        if event.button() != Qt.LeftButton:
            return
        self._drag = True
        self._start = event.pos()
        self._end = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        if not self._drag:
            return
        self._end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._emit_cancel()
            return
        if event.button() != Qt.LeftButton:
            return
        self._drag = False
        self._end = event.pos()
        rect_w = self._rect_in_widget()
        rect_phys = self._to_phys_rect(rect_w)
        if rect_phys.width() < 3 or rect_phys.height() < 3:
            self._emit_cancel()
            return

        x = int(rect_phys.x())
        y = int(rect_phys.y())
        w = int(rect_phys.width())
        h = int(rect_phys.height())
        crop = self._frame_bgr[y:y + h, x:x + w].copy()
        self._finished = True
        self.done.emit(rect_phys, crop, (self._virt_left, self._virt_top, int(self._virt_size.width()), int(self._virt_size.height())))
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._emit_cancel()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._finished and not self._canceled:
            self._emit_cancel()
        super().closeEvent(event)

    def _emit_cancel(self):
        if self._finished or self._canceled:
            return
        self._canceled = True
        self.canceled.emit()
        self.close()

    @staticmethod
    def _grab_virtual_screen_bgr():
        try:
            with mss.mss() as sct:
                mon = sct.monitors[0]
                frame = np.array(sct.grab(mon), dtype=np.uint8)[:, :, :3].copy()
                return frame, (int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"]))
        except Exception:
            screen = QApplication.primaryScreen()
            vg = screen.virtualGeometry()
            pm = screen.grabWindow(0)
            qi = pm.toImage().convertToFormat(QImage.Format_RGB888)
            w, h = qi.width(), qi.height()
            ptr = qi.bits()
            ptr.setsize(qi.byteCount())
            arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 3))
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return bgr, (vg.x(), vg.y(), vg.width(), vg.height())

    @staticmethod
    def capture_from_screen(parent=None):
        frame_bgr, virt = VisualImageCaptureOverlay._grab_virtual_screen_bgr()
        virt_left, virt_top, virt_w, virt_h = virt
        dlg = VisualImageCaptureOverlay(frame_bgr, virt_left, virt_top, QSize(virt_w, virt_h), parent)
        result = {"rect": QRect(), "crop": None, "virt": (virt_left, virt_top, virt_w, virt_h)}
        loop = QEventLoop()

        def _on_done(rect, crop, virt_bounds):
            result["rect"] = rect
            result["crop"] = crop
            result["virt"] = virt_bounds
            loop.quit()

        def _on_cancel():
            loop.quit()

        dlg.done.connect(_on_done)
        dlg.canceled.connect(_on_cancel)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

        QTimer.singleShot(0, lambda: QApplication.setOverrideCursor(QCursor(Qt.CrossCursor)))
        loop.exec_()
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        dlg.deleteLater()
        return result["rect"], result["crop"], result["virt"]
