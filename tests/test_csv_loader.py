import os
import sys
import pytest

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.io.csv_loader import load_csv

def test_bom(tmp_path):
    # Create a CSV file with BOM
    file_path = tmp_path / "test_bom.csv"
    content = "name,age\nAlice,30\nBob,25"
    
    # Write with utf-8-sig to force BOM
    with open(file_path, "w", encoding="utf-8-sig") as f:
        f.write(content)
        
    # Attempt to load
    # This should fail if the loader doesn't handle BOM, or if it handles it but returns the BOM in the key
    # The specific error mentioned is UnicodeDecodeError, but sometimes it just reads the BOM as part of the first key.
    # However, if the file is encoded as utf-8-sig and we read as utf-8, Python handles it gracefully usually?
    # Wait, 'utf-8' in Python *can* read BOM but it treats it as a character (ZWNBSP).
    # If we want to simulate UnicodeDecodeError, maybe the file has some other issue?
    # Or maybe the user meant that it reads the BOM into the header key, e.g. '\ufeffname'.
    # The user said "UnicodeDecodeError".
    # If I strictly use 'utf-8', reading a 'utf-8-sig' file is valid utf-8, it just has an extra char.
    # UNLESS the content is not valid utf-8?
    # But "BOM 포함 CSV" usually means UTF-8 with BOM.
    # Let's assume the user might be encountering a case where the BOM causes issues, or maybe they are using a different encoding default?
    # Actually, if the file is cp949 or something else but has BOM? No, BOM is specific to Unicode.
    
    # Let's stick to the user's description: "UnicodeDecodeError".
    # This happens if we try to read a non-utf8 file as utf8, OR if we have strict checking?
    # But standard BOM is valid UTF-8 bytes.
    # \xef\xbb\xbf
    
    # Maybe the user is using `encoding='utf-8'` and the file is actually `utf-16` with BOM?
    # Or maybe the user simply means the BOM character is present in the keys and they want it gone, but they *called* it UnicodeDecodeError?
    # OR, maybe they are on Windows and `open()` defaults to `cp949` (ANSI) and the BOM bytes cause a decode error in cp949?
    # Yes! On Windows, `open()` defaults to `cp1252` or `cp949`.
    # If I explicitly set `encoding='utf-8'` in my code (which I did in the naive implementation), then reading a UTF-8 BOM file is fine, just has the char.
    
    # Wait, the naive implementation I wrote:
    # with open(file_path, mode='r', encoding='utf-8') as f:
    
    # If the file has BOM, it reads `\ufeffname`.
    # This is not a UnicodeDecodeError.
    
    # Let's look at the user constraints again.
    # "ERROR LOG / REPRO: tests/test_csv_loader.py::test_bom → UnicodeDecodeError"
    
    # How to get UnicodeDecodeError with BOM?
    # If the file is UTF-16 with BOM?
    # If I save as utf-16, and read as utf-8, I get UnicodeDecodeError.
    # "BOM 포함 CSV" -> usually implies UTF-8-SIG.
    
    # Let's try to reproduce what happens if I read a UTF-8-SIG file with `encoding='utf-8'`.
    # It just reads the BOM.
    
    # Maybe the user code *didn't* specify encoding, so it used system default (cp949 on Korean Windows)?
    # If I write `open(file_path, 'r')` without encoding, and the file is UTF-8 BOM.
    # CP949 trying to read `\xef\xbb\xbf`...
    # `\xef` is not valid in some contexts or maps to something else.
    # Let's assume the naive code SHOULD NOT specify encoding, or specify a wrong one?
    # But I wrote `encoding='utf-8'` in the naive code.
import os
import pytest
from app.io.csv_loader import load_csv

def test_bom(tmp_path):
    # Create a CSV file with BOM
    file_path = tmp_path / "test_bom.csv"
    content = "name,age\nAlice,30\nBob,25"
    
    # Write with utf-8-sig to force BOM
    with open(file_path, "w", encoding="utf-8-sig") as f:
        f.write(content)
        
    # Attempt to load
    # This should fail if the loader doesn't handle BOM, or if it handles it but returns the BOM in the key
    # The specific error mentioned is UnicodeDecodeError, but sometimes it just reads the BOM as part of the first key.
    # However, if the file is encoded as utf-8-sig and we read as utf-8, Python handles it gracefully usually?
    # Wait, 'utf-8' in Python *can* read BOM but it treats it as a character (ZWNBSP).
    # If we want to simulate UnicodeDecodeError, maybe the file has some other issue?
    # Or maybe the user meant that it reads the BOM into the header key, e.g. '\ufeffname'.
    # The user said "UnicodeDecodeError".
    # If I strictly use 'utf-8', reading a 'utf-8-sig' file is valid utf-8, it just has an extra char.
    # UNLESS the content is not valid utf-8?
    # But "BOM 포함 CSV" usually means UTF-8 with BOM.
    # Let's assume the user might be encountering a case where the BOM causes issues, or maybe they are using a different encoding default?
    # Actually, if the file is cp949 or something else but has BOM? No, BOM is specific to Unicode.
    
    # Let's stick to the user's description: "UnicodeDecodeError".
    # This happens if we try to read a non-utf8 file as utf8, OR if we have strict checking?
    # But standard BOM is valid UTF-8 bytes.
    # \xef\xbb\xbf
    
    # Maybe the user is using `encoding='utf-8'` and the file is actually `utf-16` with BOM?
    # Or maybe the user simply means the BOM character is present in the keys and they want it gone, but they *called* it UnicodeDecodeError?
    # OR, maybe they are on Windows and `open()` defaults to `cp949` (ANSI) and the BOM bytes cause a decode error in cp949?
    # Yes! On Windows, `open()` defaults to `cp1252` or `cp949`.
    # If I explicitly set `encoding='utf-8'` in my code (which I did in the naive implementation), then reading a UTF-8 BOM file is fine, just has the char.
    
    # Wait, the naive implementation I wrote:
    # with open(file_path, mode='r', encoding='utf-8') as f:
    
    # If the file has BOM, it reads `\ufeffname`.
    # This is not a UnicodeDecodeError.
    
    # Let's look at the user constraints again.
    # "ERROR LOG / REPRO: tests/test_csv_loader.py::test_bom → UnicodeDecodeError"
    
    # How to get UnicodeDecodeError with BOM?
    # If the file is UTF-16 with BOM?
    # If I save as utf-16, and read as utf-8, I get UnicodeDecodeError.
    # "BOM 포함 CSV" -> usually implies UTF-8-SIG.
    
    # Let's try to reproduce what happens if I read a UTF-8-SIG file with `encoding='utf-8'`.
    # It just reads the BOM.
    
    # Maybe the user code *didn't* specify encoding, so it used system default (cp949 on Korean Windows)?
    # If I write `open(file_path, 'r')` without encoding, and the file is UTF-8 BOM.
    # CP949 trying to read `\xef\xbb\xbf`...
    # `\xef` is not valid in some contexts or maps to something else.
    # Let's assume the naive code SHOULD NOT specify encoding, or specify a wrong one?
    # But I wrote `encoding='utf-8'` in the naive code.
    
    # Let's adjust the naive code to NOT specify encoding (simulating "forgot to specify encoding"), which is a common source of bugs on Windows.
    # Then `open` uses `locale.getencoding()` -> `cp949`.
    # Then reading UTF-8 BOM bytes will likely fail or produce garbage.
    
    # Let's verify this hypothesis.
    
    success, data, error = load_csv(str(file_path))
    
    assert success, f"Failed to load CSV: {error}"
    
    # If it succeeds, check keys
    first_key = list(data[0].keys())[0]
    assert first_key == "name", f"Expected 'name', got {repr(first_key)}"
