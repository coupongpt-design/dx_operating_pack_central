import datetime
import os
import shutil


def main() -> int:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join("backups", f"prework_backup_{ts}")
    os.makedirs("backups", exist_ok=True)

    ignore = shutil.ignore_patterns(
        "backups",
        "logs",
        "__pycache__",
        ".pytest_cache",
        "*.pyc",
    )
    shutil.copytree(".", dst, ignore=ignore)
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
