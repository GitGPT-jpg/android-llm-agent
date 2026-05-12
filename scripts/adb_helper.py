"""
adb_helper.py — ADB Coordinate Calibration Tool

Usage:
  python scripts/adb_helper.py screenshot   -> Capture screen to tmp/screen_full.png
  python scripts/adb_helper.py tap 540 1500 -> Test-tap a coordinate
  python scripts/adb_helper.py type hello   -> Test text input
  python scripts/adb_helper.py info         -> Show device resolution + connected devices

Calibration workflow:
  1. python scripts/adb_helper.py screenshot
  2. Open tmp/screen_full.png in any image editor, hover to read pixel coordinates:
       - Chat bubble region corners  → config/device.json "chat_crop"
       - Message input field center  → config/device.json "input_box_tap"
       - Send button center          → config/device.json "send_btn_tap"
  3. Save coordinates to config/device.json
"""

import subprocess
import sys
from pathlib import Path

# Scripts live in scripts/; project root is one level up
BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR  = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

ADB = str(BASE_DIR / "tools" / "platform-tools" / "adb.exe")


def adb(*args):
    result = subprocess.run([ADB] + list(args), capture_output=True, text=True)
    return result.stdout.strip()


def screenshot():
    path = TMP_DIR / "screen_full.png"
    with open(path, "wb") as f:
        subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=f, stderr=subprocess.DEVNULL)
    print(f"Screenshot saved: {path}")
    print("Open in any image editor, hover to read coordinates, then update config/device.json")


def tap(x, y):
    print(f"Tapping ({x}, {y}) ...")
    adb("shell", "input", "tap", str(x), str(y))
    print("Done")


def type_text(text):
    safe = text.replace(" ", "%s")
    print(f"Typing: {text}")
    adb("shell", "input", "text", safe)
    print("Done")


def info():
    print(f"Screen resolution : {adb('shell', 'wm', 'size')}")
    print(f"DPI               : {adb('shell', 'wm', 'density')}")
    print(f"Connected devices :\n{adb('devices')}")


def usage():
    print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "screenshot":
        screenshot()
    elif cmd == "tap" and len(sys.argv) == 4:
        tap(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "type" and len(sys.argv) >= 3:
        type_text(" ".join(sys.argv[2:]))
    elif cmd == "info":
        info()
    else:
        usage()
