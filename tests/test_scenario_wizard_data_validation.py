import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.scenario_wizard import plan_template


def test_plan_template_reports_missing_data_column(tmp_path):
    csv_path = tmp_path / "users.csv"
    csv_path.write_text("name\nalice\nbob\n", encoding="utf-8")

    planned = plan_template(
        "csv_text_submit_loop",
        {
            "data_file_path": str(csv_path),
            "text_pattern": "{email}",
        },
    )

    assert any("데이터 컬럼 누락" in msg for msg in planned["errors"])


def test_plan_template_warns_on_empty_data_rows(tmp_path):
    csv_path = tmp_path / "users.csv"
    csv_path.write_text("name,email\nalice,a@test.com\n,\nbob,b@test.com\n", encoding="utf-8")

    planned = plan_template(
        "csv_text_submit_loop",
        {
            "data_file_path": str(csv_path),
            "text_pattern": "{name}:{email}",
        },
    )

    assert not planned["errors"]
    assert any("빈 행" in msg for msg in planned["warnings"])


def test_plan_template_accepts_xlsx_data_file(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "email"])
    ws.append(["alice", "a@test.com"])
    ws.append(["bob", "b@test.com"])
    xlsx_path = tmp_path / "users.xlsx"
    wb.save(str(xlsx_path))
    wb.close()

    planned = plan_template(
        "csv_text_submit_loop",
        {
            "data_file_path": str(xlsx_path),
            "text_pattern": "{name}:{email}",
        },
    )

    assert not planned["errors"]
