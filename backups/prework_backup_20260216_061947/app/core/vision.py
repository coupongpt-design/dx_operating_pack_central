import re
import os
import logging
from functools import lru_cache
import cv2
import numpy as np
import pytesseract

LOGGER = logging.getLogger(__name__)


class ImageProcessor:
    def __init__(self, scale_factor: float = 2.0, invert: bool = False, threshold_mode: str = "otsu"):
        self.scale_factor = max(1.0, float(scale_factor))
        self.invert = invert
        self.threshold_mode = threshold_mode
        self._ensure_tesseract_path()

    def _ensure_tesseract_path(self):
        """Set pytesseract command if env or default path exists."""
        env_cmd = os.getenv("TESSERACT_CMD")
        if env_cmd and os.path.exists(env_cmd):
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            return
        default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_path):
            pytesseract.pytesseract.tesseract_cmd = default_path

    def preprocess_for_ocr(self, image: np.ndarray, psm_mode: int = 6) -> np.ndarray:
        """Grayscale, scale up, threshold, optional invert."""
        if image is None or not hasattr(image, "shape"):
            raise ValueError("Invalid image input")

        # Grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Scale up to help small fonts
        if self.scale_factor != 1.0:
            h, w = gray.shape[:2]
            new_w = int(w * self.scale_factor)
            new_h = int(h * self.scale_factor)
            gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        mode = str(self.threshold_mode or "otsu").lower()
        processed = gray
        if mode in ("none", "no", "off"):
            processed = gray
        elif mode in ("blur", "gaussian"):
            processed = cv2.GaussianBlur(gray, (3, 3), 0)
            _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        elif mode in ("adaptive", "adapt"):
            processed = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            # Default to Otsu for "thresh", "otsu", or unknown tokens.
            _, processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        # Invert if background is dark
        if self.invert:
            processed = cv2.bitwise_not(processed)

        return processed

    def extract_number(self, image: np.ndarray, psm_mode: int = 6) -> float | None:
        """Run OCR and return the first numeric value (int/float/percent) or None."""
        pre = self.preprocess_for_ocr(image, psm_mode=psm_mode)
        config = f"--psm {int(psm_mode)} -c tessedit_char_whitelist=0123456789.%"
        try:
            text = pytesseract.image_to_string(pre, lang="eng", config=config)
        except Exception:
            text = ""
        if not text:
            return None

        # Normalize common thousands separators so OCR like "1,234" becomes "1234".
        text = re.sub(r"(?<=\d)[, ](?=\d)", "", text)

        matches = re.findall(r"\d+\.?\d*%?", text)
        if not matches:
            # Fallback: first numeric substring
            m = re.search(r"\d+(\.\d+)?%?", text)
            if not m:
                return None
            token = m.group(0)
        else:
            token = matches[0]
        token = token.rstrip("%")
        try:
            val = float(token)
            return val
        except ValueError:
            return None

    # --- Template caching for disk-loaded images -------------------------
    @lru_cache(maxsize=50)
    def _load_template_from_disk(self, path: str) -> np.ndarray | None:
        """Cached loader to reduce disk I/O for repeated template usage."""
        try:
            if not path or not os.path.exists(path):
                return None
            with open(path, "rb") as f:
                data = f.read()
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def clear_cache(self) -> None:
        """Clear cached templates (call after templates on disk change)."""
        try:
            self._load_template_from_disk.cache_clear()
        except Exception as e:
            LOGGER.debug("Template cache clear failed (non-fatal): %s", e)
