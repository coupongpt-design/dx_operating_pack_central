import json
import os
import types

import pytest


@pytest.mark.usefixtures("qtbot")
def test_load_macro_json_formatted_macro_extension(monkeypatch, tmp_path, qtbot):
    """
    JSON으로 저장된 .macro 파일이 MacroIO zip 로드 실패 시에도
    JSON 재시도를 통해 정상 로드되는지 확인한다.
    """
    from app.main import MainWindow

    # 준비: JSON 내용을 .macro 확장자로 저장
    steps = [{"id": "s1", "name": "Test", "type": "comment", "comment": "note"}]
    payload = {"steps": steps, "repeat": {}, "meta": {"target_window": "TestWin"}}
    macro_file = tmp_path / "sample.macro"
    macro_file.write_text(json.dumps(payload), encoding="utf-8")

    # MacroIO.load_macro가 zip 에러를 내도록 모킹
    def fake_load_macro(path):
        raise Exception("File is not a zip file")

    monkeypatch.setattr("app.main.MacroIO.load_macro", fake_load_macro)

    mw = MainWindow()
    qtbot.addWidget(mw)

    ok = mw._load_macro_from_path(str(macro_file))

    assert ok is True
    assert len(mw.steps) == 1
    assert mw.steps[0].name == "Test"
    assert getattr(mw.steps[0], "comment", "") == "note"
    assert getattr(mw, "edTargetTitle", None) is None or mw.edTargetTitle.text() == "TestWin"
