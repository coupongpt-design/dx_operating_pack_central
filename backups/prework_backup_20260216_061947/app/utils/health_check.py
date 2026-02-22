import os
import sys
import tempfile
import traceback


def _print(status, title, detail=""):
    tag = "[OK]" if status else "[FAIL]"
    if detail:
        print(f"{tag} {title}: {detail}")
    else:
        print(f"{tag} {title}")


def check_tesseract():
    title = "Tesseract OCR"
    try:
        import pytesseract
        import numpy as np
        import cv2

        # Allow env override
        env_cmd = os.getenv("TESSERACT_CMD")
        if env_cmd:
            pytesseract.pytesseract.tesseract_cmd = env_cmd
        else:
            default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path

        # Check executable path
        cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
        exists = os.path.exists(cmd) or cmd == "tesseract"

        # Create tiny test image and run OCR
        img = np.zeros((40, 80, 3), dtype=np.uint8)
        cv2.putText(img, "HI", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmpfile_path = tmpfile.name
        tmpfile.close()  # close handle to avoid Windows lock
        try:
            cv2.imwrite(tmpfile_path, img)
            text = pytesseract.image_to_string(tmpfile_path, lang="eng")
            _print(True, title, f"path set: {exists}, result: {text.strip()!r}")
        finally:
            try:
                os.unlink(tmpfile_path)
            except Exception as cleanup_error:
                print(f"[WARN] {title}: temp file cleanup failed: {cleanup_error}")
    except Exception as e:
        _print(False, title, f"{e}. Tip: ensure Tesseract is installed and pytesseract is configured.")


def check_mss():
    title = "Screen Capture (mss)"
    try:
        import mss

        with mss.mss() as sct:
            mon = sct.monitors[0]
            region = {"left": mon["left"], "top": mon["top"], "width": 10, "height": 10}
            shot = sct.grab(region)
            ok = shot.width == 10 and shot.height == 10
            _print(ok, title, f"captured {shot.width}x{shot.height}")
    except Exception as e:
        _print(False, title, f"{e}. Tip: check screen capture permissions.")


def check_pyautogui():
    title = "pyautogui Permission"
    try:
        import pyautogui

        pos = pyautogui.position()
        failsafe = getattr(pyautogui, "FAILSAFE", None)
        _print(True, title, f"position={pos}, FAILSAFE={failsafe}")
    except Exception as e:
        _print(False, title, f"{e}. Tip: some OS require accessibility permission for input.")


def check_filesystem():
    title = "Filesystem Write"
    try:
        base = tempfile.mkdtemp(prefix="health_check_")
        path = os.path.join(base, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("health check")
        os.remove(path)
        os.rmdir(base)
        _print(True, title, f"temp dir: {base}")
    except Exception as e:
        _print(False, title, f"{e}. Tip: verify write permission to working directories.")


def main():
    print("=== Environment Health Check ===")
    check_tesseract()
    check_mss()
    check_pyautogui()
    check_filesystem()


if __name__ == "__main__":
    main()
