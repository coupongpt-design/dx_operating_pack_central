import subprocess
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from app.core.commands import AddStepCommand
from app.core.models import StepData
from app.main import MainWindow


def run_selected_tests(repo_root: Path):
    targets = [
        "tests/test_simulation.py",
        "tests/test_stress.py",
        "tests/test_actions.py",
        "tests/test_ocr_pipeline.py",
        "tests/test_branching_and_loops.py",
        "tests/test_macro_io_compat.py",
        "tests/test_drag_drop_undo.py",
    ]
    cmd = [sys.executable, "-m", "pytest", *targets, "-q"]
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output


def ui_integrity_check():
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        for i in range(50):
            step = StepData(id=f"auto{i}", name=f"Auto {i}", type="comment")
            win._push_command(AddStepCommand(win.steps, step))
        for _ in range(50):
            win.undo_stack.undo()
        return len(win.steps) == 0
    finally:
        win.close()
        app.quit()


def main():
    repo_root = Path(__file__).resolve().parent
    tests_ok, log_output = run_selected_tests(repo_root)
    if log_output:
        print(log_output, end="")
    ui_ok = ui_integrity_check()

    if tests_ok and ui_ok:
        # Keep ASCII-only output so Windows cp949 consoles do not crash.
        print("[OK] CERTIFIED STABLE")
        sys.exit(0)

    if not tests_ok:
        print("[FAIL] Tests failed during simulation suite.", file=sys.stderr)
    if not ui_ok:
        print("[FAIL] UI integrity check failed.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
