import cv2
import numpy as np
import mss
from PyQt5.QtWidgets import QWidget, QApplication, QDialog
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize, QTimer, QEventLoop
from PyQt5.QtGui import QPainter, QColor, QImage, QCursor
from ..utils.common import err

class ROISelector(QWidget):
    done = pyqtSignal(QRect, object, tuple)  # rect, crop_bgr, (virt_left, virt_top, virt_w, virt_h)

    def __init__(self, frame_bgr: np.ndarray, virt_left: int, virt_top: int, virt_size: QSize, parent=None):
        super().__init__(parent, flags=Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._frame_bgr = frame_bgr
        self._virt_left = virt_left
        self._virt_top = virt_top
        self._virt_size = virt_size
        self._drag = False
        self._start = QPoint()
        self._end = QPoint()
        
        fh, fw = frame_bgr.shape[:2]
        vw, vh = max(1, virt_size.width()), max(1, virt_size.height())
        self._fx = fw / float(vw)
        self._fy = fh / float(vh)
        
        self.setGeometry(virt_left, virt_top, virt_size.width(), virt_size.height())
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, e):
        p = QPainter(self)
        rgb = cv2.cvtColor(self._frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0], 3*rgb.shape[1], QImage.Format_RGB888)
        p.drawImage(self.rect(), qimg)
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))
        
        # Draw selection rectangle
        if self._drag:
            rect = QRect(self._start, self._end).normalized()
            p.fillRect(rect, QColor(255, 255, 255, 40))
            p.setPen(QColor(0, 255, 0, 255))
            p.drawRect(rect)
        
        # Draw instruction text
        from PyQt5.QtGui import QFont
        p.setPen(QColor(255, 255, 0, 255))
        p.setFont(QFont("Arial", 14, QFont.Bold))
        text = "드래그하여 영역 선택 | ESC: 취소 | 우클릭: 취소"
        p.drawText(10, 30, text)
        
        p.end()

    def mousePressEvent(self, e):
        self._drag = True
        self._start = e.pos()
        self._end = e.pos()
        self.update()

    def mouseMoveEvent(self, e):
        if self._drag:
            self._end = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):
        # Right click to cancel
        if e.button() == Qt.RightButton:
            self.close()
            return
            
        self._drag = False
        self._end = e.pos()
        self.update()
        x1w, y1w = min(self._start.x(), self._end.x()), min(self._start.y(), self._end.y())
        x2w, y2w = max(self._start.x(), self._end.x()), max(self._start.y(), self._end.y())
        
        x1 = int(round(x1w * self._fx))
        y1 = int(round(y1w * self._fy))
        x2 = int(round(x2w * self._fx))
        y2 = int(round(y2w * self._fy))
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        
        if w < 3 or h < 3:
            self.done.emit(QRect(), None, (self._virt_left, self._virt_top, self._virt_size.width(), self._virt_size.height()))
        else:
            crop = self._frame_bgr[y1:y1+h, x1:x1+w].copy()
            rect_phys = QRect(x1, y1, w, h)
            self.done.emit(rect_phys, crop, (self._virt_left, self._virt_top, self._virt_size.width(), self._virt_size.height()))
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(e)

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
    def select_from_screen(parent=None):
        frame_bgr, virt = ROISelector._grab_virtual_screen_bgr()
        virt_left, virt_top, virt_w, virt_h = virt
        dlg = ROISelector(frame_bgr, virt_left, virt_top, QSize(virt_w, virt_h), parent)
        result = {}
        loop = QEventLoop()
        def on_done(rect, crop, v):
            result["rect"] = rect
            result["crop"] = crop
            result["virt"] = v
            loop.quit()
        dlg.done.connect(on_done)
        loop.exec_()
        dlg.deleteLater()
        if "rect" not in result:
            return QRect(), None, (virt_left, virt_top, virt_w, virt_h)
        return result["rect"], result["crop"], result["virt"]

class _Overlay(QWidget):
    picked = pyqtSignal(int, int)
    canceled = pyqtSignal()

    def __init__(self, timeout_ms=15000, parent=None, grid=False, grid_step=8):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        
        vrect = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vrect)
        
        self._hover = None
        self._grid = bool(grid)
        self._grid_step = max(1, int(grid_step))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._cancel)
        self._timeout_ms = int(timeout_ms)
        
        c = self.rect().center()
        self._hover = QPoint(c.x(), c.y())
        self._prime_hint = True

    def showEvent(self, e):
        super().showEvent(e)
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self._timer.start(self._timeout_ms)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 60))
        if self._hover is not None:
            p.setPen(QColor(0, 220, 120, 230))
            x, y = self._hover.x(), self._hover.y()
            p.drawLine(x, self.rect().top(), x, self.rect().bottom())
            p.drawLine(self.rect().left(), y, self.rect().right(), y)
            p.drawEllipse(self._hover, 6, 6)

    def mouseMoveEvent(self, e):
        if self._grid:
            gx = round(e.pos().x()/self._grid_step)*self._grid_step
            gy = round(e.pos().y()/self._grid_step)*self._grid_step
            self._hover = QPoint(gx, gy)
        else:
            self._hover = e.pos()
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        gpos = e.globalPos()
        screen = QApplication.screenAt(gpos) or QApplication.primaryScreen()
        try:
            dpr = float(screen.devicePixelRatio())
        except Exception:
            dpr = 1.0
        self._finish(int(round(gpos.x()*dpr)), int(round(gpos.y()*dpr)))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(e)

    def _finish(self, x, y):
        try: self._timer.stop()
        except: pass
        self._release_all()
        self.close()
        QTimer.singleShot(0, lambda: self.picked.emit(x, y))
        QTimer.singleShot(0, self.deleteLater)

    def _cancel(self):
        try: self._timer.stop()
        except: pass
        self._release_all()
        self.close()
        QTimer.singleShot(0, self.canceled.emit)
        QTimer.singleShot(0, self.deleteLater)

    def _release_all(self):
        try: self.releaseMouse()
        except: pass
        try: self.releaseKeyboard()
        except: pass
        try: QApplication.restoreOverrideCursor()
        except: pass

class PointSelector(QWidget):
    @staticmethod
    def select_point(parent=None, timeout_ms: int = 15000, grid: bool = False, grid_step: int = 8):
        app = QApplication.instance()
        if app:
            try: app.isPickingPoint = True
            except Exception as e: err(f"Failed to set isPickingPoint: {e}")
            
        loop = QEventLoop()
        result_holder = {"pt": None}
        
        def _picked(x, y):
            result_holder["pt"] = QPoint(int(x), int(y))
            loop.quit()
            
        def _canceled():
            result_holder["pt"] = None
            loop.quit()
            
        overlay = _Overlay(timeout_ms, parent, grid, grid_step)
        overlay.picked.connect(_picked)
        overlay.canceled.connect(_canceled)
        overlay.show()
        
        loop.exec_()
        
        if app:
            try: app.isPickingPoint = False
            except Exception as e: err(f"Failed to unset isPickingPoint: {e}")
            
        return result_holder["pt"]

class _InlinePointOverlay(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setWindowOpacity(0.01)
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        try: self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        except: pass
        self._pt = None
        
        vrect = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vrect)
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pt = e.globalPos()
            self.accept()
        elif e.button() == Qt.RightButton:
            self.reject()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.reject()

    @staticmethod
    def pick(parent=None):
        dlg = _InlinePointOverlay(parent)
        loop = QEventLoop()
        try: dlg.finished.connect(lambda _res: loop.quit())
        except Exception as e: err(f"Failed to connect finished signal: {e}")
        dlg.show()
        dlg.raise_()
        loop.exec_()
        dlg.deleteLater()
        return getattr(dlg, '_pt', None)

def safe_select_point(parent=None):
    try:
        pt = PointSelector.select_point(None)
    except Exception as ex:
        err(f"PointSelector.select_point failed: {ex}. Falling back to inline overlay.")
        pt = None
        
    if pt is None:
        try:
            pt = _InlinePointOverlay.pick(parent)
        except Exception as ex2:
            err(f"Inline fallback failed: {ex2}")
            
    if parent:
        try:
            parent.show()
            parent.raise_()
            parent.activateWindow()
        except Exception as e: err(f"Failed to restore parent window: {e}")
        
    return pt

class CrosshairOverlay(QWidget):
    def __init__(self, virt_left, virt_top, virt_w, virt_h, x, y, duration_ms=300):
        super().__init__(parent=None, flags=Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(virt_left, virt_top, virt_w, virt_h)
        self._virt_left = virt_left
        self._virt_top = virt_top
        self._x = x
        self._y = y
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, int(duration_ms)))
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self.show()
        self.raise_()
        QTimer.singleShot(0, self.raise_)
        self._timer.start()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(0, 255, 0, 220))
        lx = self._x - self._virt_left
        ly = self._y - self._virt_top
        p.drawLine(lx - 10, ly, lx + 10, ly)
        p.drawLine(lx, ly - 10, lx, ly + 10)
        p.end()
