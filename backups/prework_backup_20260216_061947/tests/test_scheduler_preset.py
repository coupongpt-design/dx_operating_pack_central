import sys
import os
import shutil
import tempfile
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTime, Qt, QSettings

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import MainWindow

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

@pytest.fixture
def window(qapp):
    # Use a temporary QSettings to avoid messing with real config
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, os.path.join(tempfile.gettempdir(), "test_settings.ini"))
    win = MainWindow()
    yield win
    win.close()

def test_scheduler_settings_save_load(window):
    """Test saving and loading of scheduler settings."""
    # Set some values
    window.sched_list.clear()
    test_time = QTime(14, 30)
    window.sched_time_edit.setTime(test_time)
    
    # Add a dummy macro to the list
    window._add_path_to_sched_list("C:/fake/path/macro1.macro")
    
    # Save
    window._save_scheduler_settings()
    
    # Clear and Load
    window.sched_list.clear()
    window.sched_time_edit.blockSignals(True)
    window.sched_time_edit.setTime(QTime(0, 0))
    window.sched_time_edit.blockSignals(False)
    window._load_scheduler_settings()
    
    # Verify
    assert window.sched_time_edit.time() == test_time
    assert window.sched_list.count() == 1
    item = window.sched_list.item(0)
    assert item.data(Qt.UserRole) == "C:/fake/path/macro1.macro"

def test_scheduler_logic_check_schedule(window, capsys):
    """Test the timer logic for triggering the schedule."""
    # Set schedule time to current time
    now = QTime.currentTime()
    window.sched_time_edit.setTime(now)
    
    # Enable scheduler
    window._add_path_to_sched_list("C:/fake/path/macro1.macro")
    window.sched_btnToggle.setChecked(True)
    assert window._sched_running is True
    
    # Mock _run_scheduled_sequence to verify it's called
    called = False
    def mock_run():
        nonlocal called
        called = True
    
    window._run_scheduled_sequence = mock_run
    
    # Trigger check
    window._check_schedule()
    
    assert called is True
    assert window._sched_ran_today is True

def test_preset_refresh(window):
    """Test refreshing the preset list from a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy macro files
        with open(os.path.join(tmpdir, "test1.macro"), "w") as f: f.write("{}")
        with open(os.path.join(tmpdir, "test2.macro"), "w") as f: f.write("{}")
        with open(os.path.join(tmpdir, "other.txt"), "w") as f: f.write("")
        
        # Mock _compute_preset_dir to return tmpdir
        window._compute_preset_dir = lambda: tmpdir
        window._preset_dir = tmpdir # Force update
        
        window._refresh_preset_list()
        
        assert window.presetList.count() == 2
        items = [window.presetList.item(i).text() for i in range(window.presetList.count())]
        assert "test1.macro" in items
        assert "test2.macro" in items
        assert "other.txt" not in items

def test_preset_load_selection(window):
    """Test loading a selected preset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        macro_path = os.path.join(tmpdir, "test_load.macro")
        # Create a valid zip macro file
        import zipfile
        import json
        with zipfile.ZipFile(macro_path, 'w') as z:
            z.writestr("scenario.json", json.dumps({"steps": []}))
            
        window._compute_preset_dir = lambda: tmpdir
        window._preset_dir = tmpdir
        window._refresh_preset_list()
        
        # Select the item
        window.presetList.setCurrentRow(0)
        
        # Mock _load_macro_from_path
        loaded_path = None
        def mock_load(path):
            nonlocal loaded_path
            loaded_path = path
            return True
        
        window._load_macro_from_path = mock_load
        
        # Trigger load
        window._load_selected_preset()
        
        assert loaded_path is not None
        assert os.path.normpath(loaded_path) == os.path.normpath(macro_path)
