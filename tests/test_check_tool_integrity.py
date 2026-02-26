from __future__ import annotations

from pathlib import Path

from tools import check_tool_integrity as cti


def test_wrapper_delegation_is_accepted(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(cti.check_integrity.__globals__, "TOOL_FILES", ("demo.py",))
    root_tool = tmp_path / "tools" / "demo.py"
    dx_tool = tmp_path / "dx_operating_pack" / "tools" / "demo.py"
    root_tool.parent.mkdir(parents=True, exist_ok=True)
    dx_tool.parent.mkdir(parents=True, exist_ok=True)
    dx_tool.write_text("print('dx')\n", encoding="utf-8")
    root_tool.write_text(
        "import importlib.util\n"
        "target = 'dx_operating_pack/tools/demo.py'\n"
        "importlib.util.spec_from_file_location('x', target)\n",
        encoding="utf-8",
    )

    issues, logs = cti.check_integrity(tmp_path)
    assert issues == 0
    assert any("wrapper delegation detected" in line for line in logs)


def test_non_wrapper_hash_mismatch_is_reported(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(cti.check_integrity.__globals__, "TOOL_FILES", ("demo.py",))
    root_tool = tmp_path / "tools" / "demo.py"
    dx_tool = tmp_path / "dx_operating_pack" / "tools" / "demo.py"
    root_tool.parent.mkdir(parents=True, exist_ok=True)
    dx_tool.parent.mkdir(parents=True, exist_ok=True)
    dx_tool.write_text("print('dx')\n", encoding="utf-8")
    root_tool.write_text("print('root-changed')\n", encoding="utf-8")

    issues, logs = cti.check_integrity(tmp_path)
    assert issues == 1
    assert any("hash mismatch and wrapper not detected" in line for line in logs)
