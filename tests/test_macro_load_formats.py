import json
import os
import types
import zipfile

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


@pytest.mark.usefixtures("qtbot")
def test_save_macro_extension_writes_zip_package(monkeypatch, tmp_path, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData

    out_path = tmp_path / "pack.macro"
    monkeypatch.setattr("app.main.QFileDialog.getSaveFileName", lambda *a, **k: (str(out_path), None))

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.steps = [StepData(id="c1", name="Comment", type="comment", comment="hello")]
    mw.save_macro()

    with zipfile.ZipFile(out_path, "r") as z:
        assert "template.json" in set(z.namelist())


@pytest.mark.usefixtures("qtbot")
def test_save_json_roundtrip_preserves_captured_relative_target(monkeypatch, tmp_path, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData

    out_path = tmp_path / "plain.json"
    monkeypatch.setattr("app.main.QFileDialog.getSaveFileName", lambda *a, **k: (str(out_path), None))

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.steps = [
        StepData(
            id="img1",
            name="Relative",
            type="image_click",
            relative_target_enabled=True,
            relative_target_png_bytes=b"target-bytes",
            relative_search_right=50,
            relative_search_bottom=20,
        )
    ]
    mw.save_macro()

    mw2 = MainWindow()
    qtbot.addWidget(mw2)
    ok = mw2._load_macro_from_path(str(out_path))

    assert ok is True
    assert len(mw2.steps) == 1
    assert mw2.steps[0].relative_target_enabled is True
    assert mw2.steps[0].relative_target_png_bytes == b"target-bytes"
    assert mw2.steps[0].relative_target_image_path in {None, ""}


@pytest.mark.usefixtures("qtbot")
def test_load_macro_zip_restores_meta_target_window(tmp_path, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData, RepeatConfig
    from app.io.macro_io import MacroIO

    macro_path = tmp_path / "target_meta.macro"
    steps = [StepData(id="s1", name="Comment", type="comment", comment="x")]
    MacroIO.save_macro(str(macro_path), steps, RepeatConfig(), meta={"target_window": "Notepad"})

    mw = MainWindow()
    qtbot.addWidget(mw)
    ok = mw._load_macro_from_path(str(macro_path))

    assert ok is True
    assert mw.edTargetTitle.text() == "Notepad"
