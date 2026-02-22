#!/usr/bin/env python
"""
Import 검토 스크립트
모든 app/ 디렉토리의 Python 파일을 import하여 누락된 import를 찾습니다.
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath('.'))

errors = []

modules_to_check = [
    'app.main',
    'app.core.models',
    'app.core.runner',
    'app.core.recorder',
    'app.ui.dialogs',
    'app.ui.widgets',
    'app.ui.selectors',
    'app.ui.hotkeys',
    'app.utils.common',
    'app.utils.matcher',
    'app.io.csv_loader',
]

for module_name in modules_to_check:
    try:
        print(f"Checking {module_name}...", end=' ')
        __import__(module_name)
        print("OK")
    except Exception as e:
        print(f"ERROR: {e}")
        errors.append((module_name, str(e)))

if errors:
    print("\n=== Import Errors Found ===")
    for module, error in errors:
        print(f"{module}: {error}")
    sys.exit(1)
else:
    print("\n=== All imports OK ===")
    sys.exit(0)
