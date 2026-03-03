from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


class ExcelDataLoader:
    @staticmethod
    def _is_empty_row(values: Iterable[Any]) -> bool:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            return False
        return True

    @classmethod
    def _build_headers(cls, raw_headers: Iterable[Any]) -> list[str]:
        headers: list[str] = []
        seen: dict[str, int] = {}
        for idx, raw in enumerate(raw_headers, start=1):
            name = str(raw).strip() if raw is not None else ""
            if not name:
                name = f"column_{idx}"
            count = seen.get(name, 0) + 1
            seen[name] = count
            if count > 1:
                headers.append(f"{name}_{count}")
            else:
                headers.append(name)
        return headers

    @classmethod
    def iter_rows(cls, xlsx_path: str, *, sheet_name: str | None = None):
        openpyxl = __import__("openpyxl")
        wb = openpyxl.load_workbook(filename=xlsx_path, data_only=True)
        try:
            ws = wb[sheet_name] if sheet_name else wb.active
            max_col = int(ws.max_column or 0)
            if max_col <= 0:
                return
            headers_raw = [ws.cell(row=1, column=col).value for col in range(1, max_col + 1)]
            headers = cls._build_headers(headers_raw)
            for excel_row_idx in range(2, int(ws.max_row or 0) + 1):
                values = [ws.cell(row=excel_row_idx, column=col).value for col in range(1, max_col + 1)]
                if cls._is_empty_row(values):
                    continue
                payload = {headers[i]: values[i] for i in range(len(headers))}
                yield (excel_row_idx, payload)
        finally:
            wb.close()

    @classmethod
    def load_rows(cls, xlsx_path: str, *, sheet_name: str | None = None) -> list[tuple[int, dict[str, Any]]]:
        return list(cls.iter_rows(xlsx_path, sheet_name=sheet_name))


class ExcelResultExporter:
    @staticmethod
    def _is_empty_row(values: Iterable[Any]) -> bool:
        return ExcelDataLoader._is_empty_row(values)

    @classmethod
    def _collect_data_excel_rows(cls, worksheet) -> list[int]:
        rows: list[int] = []
        max_col = int(worksheet.max_column or 0)
        for excel_row_idx in range(2, int(worksheet.max_row or 0) + 1):
            values = [worksheet.cell(row=excel_row_idx, column=col).value for col in range(1, max_col + 1)]
            if cls._is_empty_row(values):
                continue
            rows.append(excel_row_idx)
        return rows

    @staticmethod
    def _status_text(value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in {"SUCCESS", "SUCCEEDED", "OK", "DONE"}:
            return "SUCCESS"
        if text in {"FAILED", "FAIL", "ERROR"}:
            return "FAILED"
        return text or ""

    @classmethod
    def _normalize_results_to_excel_rows(cls, results: Any, worksheet) -> dict[int, dict[str, str]]:
        excel_row_map: dict[int, dict[str, str]] = {}
        data_rows = cls._collect_data_excel_rows(worksheet)

        rows_obj: list[dict[str, Any]] = []
        if isinstance(results, dict) and isinstance(results.get("rows"), list):
            rows_obj = [r for r in results["rows"] if isinstance(r, dict)]
        elif isinstance(results, list):
            rows_obj = [r for r in results if isinstance(r, dict)]
        elif isinstance(results, dict):
            # direct mapping: {excel_row_index: {"status":..., "error_reason":...}}
            for k, v in results.items():
                if not isinstance(v, dict):
                    continue
                try:
                    row_idx = int(k)
                except Exception:
                    continue
                if row_idx < 2:
                    continue
                excel_row_map[row_idx] = {
                    "status": cls._status_text(v.get("status")),
                    "error_reason": str(v.get("error_reason") or ""),
                }
            return excel_row_map

        for row_info in rows_obj:
            if "excel_row_index" in row_info:
                try:
                    excel_row_idx = int(row_info.get("excel_row_index"))
                except Exception:
                    continue
            else:
                try:
                    data_idx = int(row_info.get("row_index"))
                except Exception:
                    continue
                if data_idx < 0 or data_idx >= len(data_rows):
                    continue
                excel_row_idx = data_rows[data_idx]
            if excel_row_idx < 2:
                continue
            excel_row_map[excel_row_idx] = {
                "status": cls._status_text(row_info.get("status")),
                "error_reason": str(row_info.get("error_reason") or ""),
            }
        return excel_row_map

    @classmethod
    def export_with_results(
        cls,
        input_xlsx_path: str,
        output_xlsx_path: str,
        results: Any,
        *,
        sheet_name: str | None = None,
    ) -> str:
        openpyxl = __import__("openpyxl")
        wb = openpyxl.load_workbook(filename=input_xlsx_path)
        try:
            ws = wb[sheet_name] if sheet_name else wb.active
            write_map = cls._normalize_results_to_excel_rows(results, ws)

            status_col = int(ws.max_column or 0) + 1
            reason_col = status_col + 1
            ws.cell(row=1, column=status_col, value="_status")
            ws.cell(row=1, column=reason_col, value="_error_reason")

            for excel_row_idx in sorted(write_map.keys()):
                row_data = write_map[excel_row_idx]
                ws.cell(row=excel_row_idx, column=status_col, value=row_data.get("status", ""))
                ws.cell(row=excel_row_idx, column=reason_col, value=row_data.get("error_reason", ""))

            out_path = Path(output_xlsx_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            wb.save(str(out_path))
            return str(out_path)
        finally:
            wb.close()

