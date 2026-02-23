from pathlib import Path

import pytest

from app.core.excel_io import ExcelDataLoader, ExcelResultExporter


def _create_sample_xlsx(path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.cell(row=1, column=1, value="name")
    ws.cell(row=1, column=2, value="age")
    ws.cell(row=2, column=1, value="alice")
    ws.cell(row=2, column=2, value=20)
    ws.cell(row=3, column=1, value=None)   # completely empty row -> should be skipped
    ws.cell(row=3, column=2, value=None)
    ws.cell(row=4, column=1, value="bob")
    ws.cell(row=4, column=2, value=30)
    wb.save(str(path))
    wb.close()


def test_excel_data_loader_maps_headers_and_skips_empty(tmp_path):
    xlsx_path = tmp_path / "input.xlsx"
    _create_sample_xlsx(xlsx_path)

    rows = ExcelDataLoader.load_rows(str(xlsx_path))
    assert rows == [
        (2, {"name": "alice", "age": 20}),
        (4, {"name": "bob", "age": 30}),
    ]


def test_excel_result_exporter_appends_status_and_error_reason(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")

    input_path = tmp_path / "input.xlsx"
    output_path = tmp_path / "result.xlsx"
    _create_sample_xlsx(input_path)

    # Step1-style aggregator summary format (row_index is data-row order, 0-based among non-empty rows)
    summary = {
        "rows": [
            {"row_index": 0, "status": "success", "error_reason": ""},
            {"row_index": 1, "status": "failed", "error_reason": "timeout: 5s"},
        ]
    }

    saved = ExcelResultExporter.export_with_results(
        str(input_path),
        str(output_path),
        summary,
    )
    assert Path(saved).exists()

    wb = openpyxl.load_workbook(str(output_path), data_only=True)
    try:
        ws = wb.active
        # original columns: A(name), B(age) -> appended C(_status), D(_error_reason)
        assert ws.cell(row=1, column=3).value == "_status"
        assert ws.cell(row=1, column=4).value == "_error_reason"

        # row 2 (alice)
        assert ws.cell(row=2, column=3).value == "SUCCESS"
        assert ws.cell(row=2, column=4).value in ("", None)

        # row 3 is empty row in source, should remain untagged
        assert ws.cell(row=3, column=3).value in ("", None)
        assert ws.cell(row=3, column=4).value in ("", None)

        # row 4 (bob)
        assert ws.cell(row=4, column=3).value == "FAILED"
        assert ws.cell(row=4, column=4).value == "timeout: 5s"
    finally:
        wb.close()

