import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path

from macro.config import CONFIG

PANDAS_AVAILABLE = importlib.util.find_spec("pandas") is not None
OPENPYXL_AVAILABLE = importlib.util.find_spec("openpyxl") is not None
PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None

if PANDAS_AVAILABLE:
    from macro.data_handler import DataHandler


class ConfigOverride:
    def __init__(self, **updates):
        self.updates = updates
        self.originals = {}

    def __enter__(self):
        for key, value in self.updates.items():
            self.originals[key] = CONFIG.get(key)
            CONFIG[key] = value
        return self

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.originals.items():
            CONFIG[key] = value


class FakeResponse:
    def __init__(self, ok=True, status=200, body=b""):
        self.ok = ok
        self.status = status
        self._body = body

    def body(self):
        return self._body


class FakeRequest:
    def __init__(self, response):
        self._response = response

    def get(self, url, timeout=None):
        return self._response


class FakeContext:
    def __init__(self, response):
        self.request = FakeRequest(response)


class FakePage:
    def __init__(self, data_bytes=b"data"):
        self._data = data_bytes
        self._cache = {}
        self.context = FakeContext(FakeResponse(body=data_bytes))

    def evaluate(self, script, arg=None):
        if isinstance(arg, str):
            if "delete" in script:
                self._cache.pop(arg, None)
                return None
            blob_id = "blob_test"
            self._cache[blob_id] = self._data
            return {"id": blob_id, "size": len(self._data)}
        if isinstance(arg, dict):
            blob_id = arg.get("id")
            start = int(arg.get("start", 0))
            end = int(arg.get("end", 0))
            chunk = self._cache.get(blob_id, b"")[start:end]
            if not chunk:
                return None
            return base64.b64encode(chunk).decode("ascii")
        return None


@unittest.skipUnless(PANDAS_AVAILABLE, "pandas not installed")
class TestDataHandler(unittest.TestCase):
    def test_sanitize_filename(self):
        name = DataHandler.sanitize_filename("a<>b:/c", "fallback")
        self.assertEqual(name, "a_b_c")

    def test_build_attachment_filename(self):
        from datetime import datetime
        dt = datetime(2024, 1, 2, 3, 4, 5)
        fname = DataHandler.build_attachment_filename(dt, 7, "img", "x.jpg", ".jpg")
        self.assertTrue(fname.startswith("20240102_030405_img"))
        self.assertTrue(fname.endswith(".jpg"))

    def test_save_blob_data_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.txt"
            data_url = "data:text/plain;base64,SGVsbG8="
            ok = DataHandler.save_blob_to_file(None, data_url, path)
            self.assertTrue(ok)
            self.assertEqual(path.read_text(encoding="utf-8"), "Hello")

    def test_save_blob_http_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.bin"
            page = FakePage(data_bytes=b"abc")
            ok = DataHandler.save_blob_to_file(page, "https://example.com/x", path)
            self.assertTrue(ok)
            self.assertEqual(path.read_bytes(), b"abc")

    def test_save_blob_chunked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob.bin"
            page = FakePage(data_bytes=b"chunked-data")
            with ConfigOverride(BLOB_CHUNK_SIZE=4):
                ok = DataHandler.save_blob_to_file(page, "blob:123", path)
            self.assertTrue(ok)
            self.assertEqual(path.read_bytes(), b"chunked-data")

    def test_create_template_and_get_targets(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            target_path = Path(tmp) / "targets.xlsx"
            with ConfigOverride(EXCEL_FILE=str(target_path)):
                DataHandler.create_template()
                self.assertTrue(target_path.exists())
                df = DataHandler.get_targets()
            self.assertIsInstance(df, pd.DataFrame)
            self.assertIn("이름", df.columns)
            self.assertIn("전화번호", df.columns)

    @unittest.skipUnless(OPENPYXL_AVAILABLE and PIL_AVAILABLE, "openpyxl or pillow not installed")
    def test_embed_images_to_excel(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            excel_path = tmp_path / "chat_log.xlsx"
            image_path = tmp_path / "img_1.png"

            # 1x1 png
            png_bytes = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
                "ASsJTYQAAAAASUVORK5CYII="
            )
            image_path.write_bytes(png_bytes)

            df = pd.DataFrame(
                [{"날짜": "2024-01-01 12:00", "보낸 사람": "나", "내용": "test", "첨부파일": ""}]
            )
            df.to_excel(excel_path, index=False)

            chat_data = [{
                "날짜": "2024-01-01 12:00",
                "보낸 사람": "나",
                "내용": "test",
                "첨부파일": "",
                "이미지목록": [image_path.name]
            }]

            DataHandler.embed_images_to_excel(excel_path, tmp_path, chat_data)
            self.assertTrue(excel_path.exists())
