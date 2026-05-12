"""
test_ocr.py — Validate OCR recognition on the current device screen

Usage:
  1. Open a chat screen on your Android device
  2. python scripts/test_ocr.py

First run will download EasyOCR language models (~300 MB).
"""

import json
import subprocess
from pathlib import Path
from PIL import Image

# Scripts live in scripts/; project root is one level up
BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR  = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

ADB = str(BASE_DIR / "tools" / "platform-tools" / "adb.exe")

# Load device coordinate config
_conf_path = BASE_DIR / "config" / "device.json"
_conf = json.loads(_conf_path.read_text(encoding="utf-8")) if _conf_path.exists() else {}
CHAT_CROP = _conf.get("chat_crop", [0, 0, 1076, 1620])

# 截图
print("Capturing screen...")
screen_path = TMP_DIR / "screen_full.png"
with open(screen_path, "wb") as f:
    subprocess.run([ADB, "exec-out", "screencap", "-p"],
                   stdout=f, stderr=subprocess.DEVNULL)
print(f"Saved: {screen_path}\n")

# 裁剪聊天区域
img = Image.open(screen_path)
l, t, r, b = CHAT_CROP
cropped = img.crop((l, t, r, b))
crop_path = TMP_DIR / "screen_crop.png"
cropped.save(crop_path)

# OCR 识别（首次运行自动下载模型，约300MB）
import easyocr
print("Running OCR (first run downloads models, ~300 MB)...\n")
reader = easyocr.Reader(["ch_sim", "en"], verbose=False)
result = reader.readtext(str(crop_path), detail=0)

print("=" * 40)
print("OCR Results:")
print("=" * 40)
if result:
    for line in result:
        print(line)
else:
    print("No text detected. Check that the screen has visible text and crop region is correct.")
