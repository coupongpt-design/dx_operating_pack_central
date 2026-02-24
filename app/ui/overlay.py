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


class CoordinateGuideOverlay(QWidget):
    _shared_instance = None

    def __init__(self, parent=None):
        super().__init__(
            parent,
            flags=Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._marker_visible = False
        self._marker_global = (0, 0)
        self._marker_local = QPoint()
        self._marker_label = ""
        self._bbox_global = None
        self._bbox_local = None
        self._last_marker = {}

        self._phys_bounds = self._detect_physical_bounds()
        self._virt_geom = QRect()
        self._sx = 1.0
        self._sy = 1.0
        self._refresh_geometry_and_scale()
        self.hide()

    @classmethod
    def get_shared(cls, parent=None):
        if cls._shared_instance is None:
            cls._shared_instance = cls(parent=parent)
        return cls._shared_instance

    @staticmethod
    def _detect_physical_bounds():
        try:
            with mss.mss() as sct:
                mon = sct.monitors[0]
                return (
                    int(mon["left"]),
                    int(mon["top"]),
                    int(mon["width"]),
                    int(mon["height"]),
                )
        except Exception:
            screen = QApplication.primaryScreen()
            if not screen:
                return (0, 0, 1, 1)
            vg = screen.virtualGeometry()
            return (int(vg.x()), int(vg.y()), int(vg.width()), int(vg.height()))

    def _refresh_geometry_and_scale(self):
        screen = QApplication.primaryScreen()
        if not screen:
            self._virt_geom = QRect(0, 0, 1, 1)
            self.setGeometry(self._virt_geom)
            self._sx = 1.0
            self._sy = 1.0
            return

        self._virt_geom = screen.virtualGeometry()
        self.setGeometry(self._virt_geom)

        phys_left, phys_top, phys_w, phys_h = self._phys_bounds
        virt_w = max(1, int(self._virt_geom.width()))
        virt_h = max(1, int(self._virt_geom.height()))
        self._sx = virt_w / float(max(1, int(phys_w)))
        self._sy = virt_h / float(max(1, int(phys_h)))
        self._phys_bounds = (int(phys_left), int(phys_top), int(phys_w), int(phys_h))

    def to_overlay_point(self, global_x: int, global_y: int) -> QPoint:
        self._refresh_geometry_and_scale()
        phys_left, phys_top, _phys_w, _phys_h = self._phys_bounds
        mapped_global_x = self._virt_geom.x() + (float(global_x) - float(phys_left)) * self._sx
        mapped_global_y = self._virt_geom.y() + (float(global_y) - float(phys_top)) * self._sy

        local_x = int(round(mapped_global_x - self.geometry().x()))
        local_y = int(round(mapped_global_y - self.geometry().y()))
        local_x = max(0, min(local_x, max(0, self.width() - 1)))
        local_y = max(0, min(local_y, max(0, self.height() - 1)))
        return QPoint(local_x, local_y)

    def _to_overlay_rect(self, rect_global: QRect) -> QRect:
        p1 = self.to_overlay_point(int(rect_global.x()), int(rect_global.y()))
        p2 = self.to_overlay_point(int(rect_global.x() + rect_global.width()), int(rect_global.y() + rect_global.height()))
        return QRect(p1, p2).normalized()

    def show_marker(self, x: int, y: int, step_idx, step_type: str, bbox=None):
        self._marker_global = (int(x), int(y))
        self._marker_local = self.to_overlay_point(int(x), int(y))
        self._marker_label = f"#{step_idx} {step_type}" if step_idx is not None else str(step_type or "")

        self._bbox_global = None
        self._bbox_local = None
        if bbox is not None:
            if isinstance(bbox, QRect):
                self._bbox_global = QRect(bbox)
            elif isinstance(bbox, (tuple, list)) and len(bbox) >= 4:
                self._bbox_global = QRect(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
            elif isinstance(bbox, (tuple, list)) and len(bbox) == 2:
                bw = max(1, int(bbox[0]))
                bh = max(1, int(bbox[1]))
                left = int(round(self._marker_global[0] - (bw / 2.0)))
                top = int(round(self._marker_global[1] - (bh / 2.0)))
                self._bbox_global = QRect(left, top, bw, bh)
            if self._bbox_global is not None:
                self._bbox_local = self._to_overlay_rect(self._bbox_global)

        self._last_marker = {
            "global": self._marker_global,
            "local": QPoint(self._marker_local),
            "step_idx": step_idx,
            "step_type": str(step_type or ""),
            "label": self._marker_label,
            "bbox_global": QRect(self._bbox_global) if isinstance(self._bbox_global, QRect) else None,
            "bbox_local": QRect(self._bbox_local) if isinstance(self._bbox_local, QRect) else None,
        }
        self._marker_visible = True
        self.show()
        self.raise_()
        self.update()

    def clear_marker(self):
        self._marker_visible = False
        self._bbox_global = None
        self._bbox_local = None
        self._last_marker = {}
        self.hide()
        self.update()

    def paintEvent(self, _event):
        if not self._marker_visible:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x = int(self._marker_local.x())
        y = int(self._marker_local.y())

        # Crosshair lines.
        p.setPen(QPen(QColor(80, 220, 255, 100), 1))
        p.drawLine(0, y, self.width(), y)
        p.drawLine(x, 0, x, self.height())

        # Laser point.
        p.setPen(QPen(QColor(0, 230, 255, 230), 2))
        p.setBrush(QColor(0, 230, 255, 190))
        p.drawEllipse(QPoint(x, y), 5, 5)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(x, y), 10, 10)

        # Optional bbox.
        if isinstance(self._bbox_local, QRect) and self._bbox_local.width() > 1 and self._bbox_local.height() > 1:
            p.setPen(QPen(QColor(255, 200, 80, 185), 1, Qt.DashLine))
            p.drawRect(self._bbox_local)

        # Label.
        label = self._marker_label or "step"
        lx = min(self.width() - 180, x + 14)
        ly = max(18, y - 14)
        label_rect = QRect(int(lx), int(ly), 176, 22)
        p.fillRect(label_rect, QColor(0, 0, 0, 130))
        p.setPen(QColor(220, 250, 255, 230))
        p.drawText(label_rect.adjusted(6, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
