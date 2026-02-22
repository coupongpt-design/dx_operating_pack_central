import pyautogui
import time

# 잠시 대기 후 스크린샷
time.sleep(1)
screenshot = pyautogui.screenshot()
screenshot.save('ui_screenshot.png')
print("Screenshot saved to ui_screenshot.png")
