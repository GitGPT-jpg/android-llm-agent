"""
learn_style.py — Extract your own messages from chat screenshots (right-side bubbles)

Usage:
  python scripts/learn_style.py              # Capture current screen, extract right-side messages
  python scripts/learn_style.py scan 20      # Capture 20 screens with scrolling, batch extract

Extracted messages are appended to persona/style.txt and used by the agent
to mirror your personal messaging style via few-shot examples.
"""

import subprocess
import sys
import time
from pathlib import Path

# Scripts live in scripts/; project root is one level up
BASE_DIR   = Path(__file__).resolve().parent.parent
TMP_DIR    = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

ADB        = str(BASE_DIR / "tools" / "platform-tools" / "adb.exe")
STYLE_FILE = BASE_DIR / "persona" / "style.txt"

# Messages on the right side are sent by you; x > this threshold = your message
RIGHT_THRESHOLD = 0.55


def adb(*args):
    return subprocess.run([ADB] + list(args), capture_output=True)


def screenshot(path: str = None) -> str:
    path = path or str(TMP_DIR / "screen_learn.png")
    with open(path, "wb") as f:
        subprocess.run([ADB, "exec-out", "screencap", "-p"],
                       stdout=f, stderr=subprocess.DEVNULL)
    return path


def extract_my_messages(img_path: str) -> list[str]:
    """提取屏幕右侧（自己发的）消息文字"""
    import easyocr
    from PIL import Image

    img = Image.open(img_path)
    w, _ = img.size
    threshold_x = int(w * RIGHT_THRESHOLD)

    reader = easyocr.Reader(["ch_sim", "en"], verbose=False)
    result = reader.readtext(img_path, detail=True)

    my_msgs = []
    for (bbox, text, conf) in result:
        if conf < 0.6:
            continue
        x_left = min(pt[0] for pt in bbox)
        if x_left >= threshold_x and len(text.strip()) > 1:
            my_msgs.append(text.strip())

    return my_msgs


def save_to_style(messages: list[str]):
    STYLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if STYLE_FILE.exists():
        existing = set(STYLE_FILE.read_text(encoding="utf-8").splitlines())

    new_msgs = [m for m in messages if m not in existing and not m.startswith("#")]
    if new_msgs:
        with open(STYLE_FILE, "a", encoding="utf-8") as f:
            for m in new_msgs:
                f.write(m + "\n")
        print(f"  Added {len(new_msgs)} new samples")
    else:
        print("  No new samples found")


def scroll_up():
    """向上滚动一屏（查看更多历史消息）"""
    adb("shell", "input", "swipe", "540", "400", "540", "1600", "300")
    time.sleep(0.8)


def run_scan(count: int = 10):
    print(f"Starting scan of {count} screens...")
    total = []
    for i in range(count):
        print(f"  Screen {i+1}/{count}", end=" ")
        path = screenshot()
        msgs = extract_my_messages(path)
        print(f"-> {len(msgs)} messages detected")
        save_to_style(msgs)
        total.extend(msgs)
        scroll_up()
    print(f"\nScan complete. Processed {len(total)} messages total.")
    print(f"Style file: {STYLE_FILE}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "scan":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        run_scan(count)
    else:
        print("Capturing current screen...")
        path = screenshot()
        msgs = extract_my_messages(path)
        print(f"Detected {len(msgs)} right-side messages:")
        for m in msgs:
            print(f"  {m}")
        save_to_style(msgs)
