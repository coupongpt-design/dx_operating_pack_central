import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.io.data_loader import inspect_data_file, load_data_rows


def test_load_data_rows_csv_skips_empty_rows(tmp_path):
    csv_path = tmp_path / "users.csv"
    csv_path.write_text("name,email\nalice,a@test.com\n,\nbob,b@test.com\n", encoding="utf-8")

    success, rows, error = load_data_rows(str(csv_path))
    assert success, error
    assert rows == [
        {"name": "alice", "email": "a@test.com"},
        {"name": "bob", "email": "b@test.com"},
    ]

    ok, info, err = inspect_data_file(str(csv_path))
    assert ok, err
    assert info["columns"] == ["name", "email"]
    assert int(info["row_count"]) == 2
    assert int(info["empty_row_count"]) == 1


def test_load_data_rows_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "level"])
    ws.append(["alice", 10])
    ws.append([None, None])  # empty row
    ws.append(["bob", 20])
    xlsx_path = tmp_path / "users.xlsx"
    wb.save(str(xlsx_path))
    wb.close()

    success, rows, error = load_data_rows(str(xlsx_path))
    assert success, error
    assert rows == [
        {"name": "alice", "level": "10"},
        {"name": "bob", "level": "20"},
    ]

    ok, info, err = inspect_data_file(str(xlsx_path))
    assert ok, err
    assert info["columns"] == ["name", "level"]
    assert int(info["row_count"]) == 2
    assert int(info["empty_row_count"]) == 1
