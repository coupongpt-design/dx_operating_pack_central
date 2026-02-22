import csv
import io
from typing import List, Dict, Any, Tuple, Optional

def load_csv(file_path: str) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Loads a CSV file and returns a list of dictionaries.
    Tries multiple encodings to handle various file formats (e.g., BOM, Korean encodings).
    
    Returns:
        (success, data, error_message)
    """
    encodings_to_try = ["utf-8-sig", "cp949", "euc-kr", "latin-1"]
    raw_text = None
    used_encoding = None

    for enc in encodings_to_try:
        try:
            with open(file_path, "r", encoding=enc, newline="") as f:
                raw_text = f.read()
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return False, None, f"File read error: {e}"
    
    if raw_text is None:
        return False, None, "Failed to decode file with supported encodings."

    try:
        # Use io.StringIO to parse the string content
        reader = csv.DictReader(io.StringIO(raw_text))
        data = list(reader)
        return True, data, None
    except Exception as e:
        return False, None, f"CSV parse error: {e}"
