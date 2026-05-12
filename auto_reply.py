"""
auto_reply.py — Android LLM Agent core engine

Pipeline: screenshot → OCR → new-message detection → AI reply → ADB send

Prerequisites:
  1. `adb devices` shows your device
  2. Update config/device.json with your device's screen coordinates
  3. Set API keys in .env (see .env.example)
  4. Set AI_MODE env var: mock (dry-run) | openai | claude | deepseek
"""

import collections
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

# ─────────────────────────────────────────────
#  PATHS — all relative paths expand from here
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TMP_DIR  = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


# ─────────────────────────────────────────────
#  DEVICE CONFIG LOADER
# ─────────────────────────────────────────────
def _load_device_conf(name: str = "device") -> dict:
    path = BASE_DIR / "config" / f"{name}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_comment", None)
        return data
    return {}

_dev = _load_device_conf()


# ─────────────────────────────────────────────
#  CONFIG — override any value via environment variables or config/device.json
# ─────────────────────────────────────────────
CONFIG = {
    # ADB binary (installed by setup.ps1 to tools/platform-tools/adb.exe)
    "adb": str(BASE_DIR / "tools" / "platform-tools" / "adb.exe"),

    # Runtime artifacts
    "screenshot": str(TMP_DIR / "screen.png"),
    "crop_tmp":   str(TMP_DIR / "_crop_tmp.png"),

    # Device coordinates — loaded from config/device.json; fallback defaults below
    "chat_crop":      _dev.get("chat_crop",         [0, 0, 1076, 1620]),
    "input_box_tap":  tuple(_dev.get("input_box_tap",     [439, 2231])),
    "send_via_enter": _dev.get("send_via_enter",    False),
    "send_btn_tap":   tuple(_dev.get("send_btn_tap",      [980, 1288])),

    # AI provider: 'mock' | 'openai' | 'claude' | 'deepseek'
    "ai_mode": os.environ.get("AI_MODE", "mock"),

    # OpenAI
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    "openai_model":   "gpt-4o-mini",
    "openai_system":  "You are a helpful, concise conversational assistant. Reply naturally in 1-2 short sentences.",

    # DeepSeek (OpenAI-compatible API)
    "deepseek_api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    "deepseek_model":   "deepseek-chat",

    # Claude
    "claude_api_key":  os.environ.get("ANTHROPIC_API_KEY", ""),
    "claude_base_url": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    "claude_model":    "claude-3-5-haiku-20241022",
    "claude_system":   (
        "You are assisting with chat replies. Rules:\n"
        "1. Sound like a real person; never reveal you are AI\n"
        "2. Keep replies short: 1-2 sentences\n"
        "3. Use a casual, natural tone\n"
        "4. End with a light question to keep conversation going\n"
        "5. If asked for personal info (location, real name, contact), deflect naturally"
    ),

    # Conversation context window (N turns = N user + N assistant messages)
    "history_turns": 5,

    # Polling interval in seconds
    "poll_interval": 3,
}


# ─────────────────────────────────────────────
#  ADB HELPERS
# ─────────────────────────────────────────────
def adb(*args, check: bool = False) -> str:
    """Run an adb command and return stdout. Raises RuntimeError if check=True and exit code != 0."""
    cmd = [CONFIG["adb"]] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"adb {' '.join(str(a) for a in args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def screenshot() -> str:
    """Capture a screenshot and save to tmp/screen.png. Returns the file path."""
    path = CONFIG["screenshot"]
    with open(path, "wb") as f:
        subprocess.run(
            [CONFIG["adb"], "exec-out", "screencap", "-p"],
            stdout=f, stderr=subprocess.DEVNULL,
        )
    return path


def tap(x: int, y: int):
    adb("shell", "input", "tap", str(x), str(y))


# ─────────────────────────────────────────────
#  CJK INPUT DETECTION (lazy, detected once)
# ─────────────────────────────────────────────
_HAS_ADBKEYBOARD: bool | None = None
_HAS_CLIPPER:     bool | None = None


def _has_adbkeyboard() -> bool:
    global _HAS_ADBKEYBOARD
    if _HAS_ADBKEYBOARD is None:
        _HAS_ADBKEYBOARD = "com.android.adbkeyboard" in adb(
            "shell", "pm", "list", "packages", "com.android.adbkeyboard"
        )
    return _HAS_ADBKEYBOARD


def _has_clipper() -> bool:
    global _HAS_CLIPPER
    if _HAS_CLIPPER is None:
        _HAS_CLIPPER = "com.majeur.clipper" in adb(
            "shell", "pm", "list", "packages", "com.majeur.clipper"
        )
    return _HAS_CLIPPER


def send_reply(reply: str):
    """Activate input box → type reply → tap send button."""
    if not reply or not reply.strip():
        return

    x, y = CONFIG["input_box_tap"]
    tap(x, y)
    time.sleep(0.5)

    typed = False

    if _has_adbkeyboard():
        import base64
        b64 = base64.b64encode(reply.encode("utf-8")).decode()
        adb("shell", "am", "broadcast", "-a", "ADB_INPUT_B64", "--es", "msg", b64)
        time.sleep(0.3)
        typed = True

    elif _has_clipper():
        adb("shell", "am", "broadcast", "-a", "clipper.set", "--es", "text", reply)
        time.sleep(0.3)
        adb("shell", "input", "keyevent", "KEYCODE_PASTE")
        time.sleep(0.3)
        typed = True

    else:
        print(
            "[WARN] ADBKeyBoard and Clipper not detected — CJK characters may be dropped.\n"
            "       Install ADBKeyBoard: https://github.com/senzhk/ADBKeyBoard/releases\n"
            "       Then set it as default keyboard in Settings → Language & Input"
        )
        # Fallback: ASCII input (CJK will be lost, but prevents an empty send)
        safe = reply.replace(" ", "%s")
        adb("shell", "input", "text", safe)
        # If the message is entirely CJK, 'input text' produces nothing — skip send
        has_ascii = any(ord(c) < 128 for c in reply)
        typed = has_ascii

    if not typed:
        # Nothing in the input box — dismiss keyboard and abort
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        return

    if CONFIG["send_via_enter"]:
        adb("shell", "input", "keyevent", "66")  # KEYCODE_ENTER
    else:
        bx, by = CONFIG["send_btn_tap"]
        tap(bx, by)
    time.sleep(0.5)


# ─────────────────────────────────────────────
#  OCR (EasyOCR — Chinese simplified + English)
# ─────────────────────────────────────────────
_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        import easyocr
        _ocr = easyocr.Reader(["ch_sim", "en"], verbose=False)
    return _ocr


def extract_chat_text(img_path: str) -> str:
    """Crop the chat region and OCR it. Returns only left-side bubble text (incoming messages).
    Right-side bubbles (sent by the user) are filtered out by x-coordinate to prevent self-replies.
    """
    img = Image.open(img_path)
    l, t, r, b = CONFIG["chat_crop"]
    cropped = img.crop((l, t, r, b))
    crop_w = r - l  # crop region width, used to compute relative bubble position
    crop_path = CONFIG["crop_tmp"]
    cropped.save(crop_path)
    try:
        reader = get_ocr()
        results = reader.readtext(crop_path, detail=1)
        threshold = CONFIG.get("right_bubble_threshold", 0.55)
        lines = []
        for (bbox, text, _conf) in results:
            # bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            xs = [p[0] for p in bbox]
            center_x = (min(xs) + max(xs)) / 2
            if center_x / crop_w > threshold:
                # Right-side bubble = sent by user, skip
                continue
            lines.append(text)
        return "\n".join(lines)
    finally:
        try:
            os.remove(crop_path)
        except FileNotFoundError:
            pass


# ─────────────────────────────────────────────
#  NEW MESSAGE DETECTION
# ─────────────────────────────────────────────
_NOISE_RE = re.compile(
    r"^\d{1,2}:\d{2}$"           # timestamp "12:30"
    r"|^[今昨前]\w{0,3}$"        # 今天/昨天/前天 (today/yesterday/day-before-yesterday)
    r"|对方撤回了|你撤回了"       # "message retracted" system notice
    r"|^\[.+\]$"                  # [system prompt]
    r"|^下一个$"                  # Soul app "Next" swipe button
    r"|^查看主页$|^关注$"         # Soul profile buttons
    r"|^交换答案$|^桌球$|^礼物$"  # Soul quick-reply buttons
    r"|^友善交友|^坟明聊天"       # Soul input placeholder text
)


def _is_noise(line: str) -> bool:
    return len(line.strip()) <= 1 or bool(_NOISE_RE.search(line))


def collect_new_lines(
    current_text: str,
    last_text: str,
    sent_messages: set,
) -> list[str]:
    """Collect all newly appeared non-noise message lines (used for richer context in state detection)."""
    prev_lines = {l.strip() for l in last_text.splitlines() if l.strip()}
    new_lines = []
    for line in current_text.splitlines():
        line = line.strip()
        if not line or _is_noise(line):
            continue
        if line in sent_messages:
            continue
        if line not in prev_lines:
            new_lines.append(line)
    return new_lines


def detect_new_message(
    current_text: str,
    last_text: str,
    sent_messages: set,
) -> str | None:
    """
    Returns the latest new, non-self, non-noise message line; None if no new message.
    sent_messages: set of messages the bot has already sent, used to filter OCR echo-back.
    """
    prev_lines = {l.strip() for l in last_text.splitlines() if l.strip()}
    for line in reversed(current_text.splitlines()):
        line = line.strip()
        if not line or _is_noise(line):
            continue
        if line in sent_messages:
            continue
        if line not in prev_lines:
            return line
    return None


# ─────────────────────────────────────────────
#  UNDERSTANDING LAYER — 3D State Detection (emotion × intent × risk)
# ─────────────────────────────────────────────
_NEGATIVE_KW   = {"难过", "哭", "累", "烦", "崩", "绝望", "伤心", "难受", "压力", "好累",
                   "好烦", "心情不好", "不想", "丧", "憋", "没意思", "无聊死了"}
_POSITIVE_KW   = {"开心", "高兴", "棒", "厉害", "哈哈", "嘻嘻", "嘿嘿", "好玩", "有趣", "喜欢"}
_FLIRT_KW      = {"喜欢你", "好感", "心动", "想见", "想你", "暧昧", "在意", "喜欢和你", "有点喜欢"}
_VENT_KW       = {"最近", "一直", "总是", "好难", "其实", "说实话", "不知道怎么"}
_ADVANCE_KW    = {"见面", "认识", "加微信", "多了解", "出来", "约", "线下", "要不要见"}
_QUESTION_KW   = {"你是", "你有", "你会", "你喜欢", "你觉得", "你平时", "你一般", "你咋", "你怎么"}
_HIGH_RISK_KW  = {"地址", "你家", "哪个小区", "电话", "手机号", "微信号", "加我", "加你", "真实姓名", "身份证"}
_MED_RISK_KW   = {"见面", "见见", "约", "出来玩", "你在哪", "哪个城市"}


def detect_state(msg: str) -> dict:
    """
    Understanding layer: analyze message across 3 dimensions — emotion / intent / risk.
    Returns: {"emotion": str, "intent": str, "risk": str}
    """
    # Risk detection (highest priority)
    if any(kw in msg for kw in _HIGH_RISK_KW):
        risk = "high"
    elif any(kw in msg for kw in _MED_RISK_KW):
        risk = "medium"
    else:
        risk = "low"

    # Emotion detection
    if any(kw in msg for kw in _FLIRT_KW):
        emotion = "flirt_signal"   # explicit romantic signal, independent of positive/negative
    elif any(kw in msg for kw in _NEGATIVE_KW):
        emotion = "negative"
    elif any(kw in msg for kw in _POSITIVE_KW):
        emotion = "positive"
    else:
        emotion = "neutral"

    # Intent detection
    if any(kw in msg for kw in _ADVANCE_KW) and risk == "low":
        intent = "relationship_advance"
    elif any(kw in msg for kw in _VENT_KW) and emotion == "negative":
        intent = "venting"
    elif any(kw in msg for kw in _QUESTION_KW):
        intent = "question"
    else:
        intent = "casual"

    return {"emotion": emotion, "intent": intent, "risk": risk}


# ─────────────────────────────────────────────
#  STRATEGY LAYER — definitions + selection logic
# ─────────────────────────────────────────────
STRATEGY_PROMPTS: dict[str, str] = {
    "casual": (
        "Strategy: casual chat\n"
        "Rules: keep it light and natural; short and relaxed; end with a gentle question or topic; "
        "stay engaged but not over-eager."
    ),
    "comfort": (
        "Strategy: empathetic support\n"
        "Rules: empathize first, advise less; listen with warmth but maintain emotional boundaries; "
        "don't over-invest; say 'I kind of get it' rather than 'I totally understand'."
    ),
    "flirt": (
        "Strategy: light flirt\n"
        "Rules: keep it ambiguous; hint at interest without committing; "
        "make the other person feel noticed but unsure; take it slow."
    ),
    "advance": (
        "Strategy: relationship deepening\n"
        "Rules: natural and unhurried; lightly suggest 'we can talk more'; "
        "no promises, no premature declarations; control the pace."
    ),
    "deflect": (
        "Strategy: topic deflection\n"
        "Rules: never answer sensitive questions directly; deflect gracefully; "
        "quickly pivot to another aspect of their message; never reveal location, real name, or contact info."
    ),
    "mystery": (
        "Strategy: cultivate mystery\n"
        "Rules: say less but make each word count; leave gaps for the other person to fill; "
        "use phrasing like 'you'll know eventually'; spark curiosity and follow-up questions."
    ),
}

STRATEGY_STYLE_MAP: dict[str, str] = {
    "casual":   "casual",
    "comfort":  "empathy",
    "flirt":    "flirt",
    "advance":  "relationship",
    "deflect":  "deflect",
    "mystery":  "mystery",
}


def select_strategy(state: dict, session_state: dict | None = None) -> str:
    """
    Strategy layer: choose a conversation strategy based on current state + session history.
    session_state shape: {"strategy_history": list[str]}
    """
    emotion = state["emotion"]
    intent  = state["intent"]
    risk    = state["risk"]
    history = (session_state or {}).get("strategy_history", [])

    # Risk gates — always deflect on sensitive requests
    if risk in ("high", "medium"):
        return "deflect"

    # Explicit romantic signal (only when risk is low)
    if emotion == "flirt_signal":
        return "flirt"

    # Negative emotion → comfort (but cap at 3 consecutive comfort turns to avoid an echo chamber)
    if emotion == "negative":
        if history.count("comfort") >= 3:
            return "casual"
        return "comfort"

    # Relationship-advance intent
    if intent == "relationship_advance":
        if "flirt" in history or "advance" in history:
            return "advance"
        return "flirt"

    # Positive emotion + casual intent → light flirt
    if emotion == "positive" and intent == "casual":
        return "flirt"

    # Question intent → mystery
    if intent == "question":
        return "mystery"

    return "casual"


# ─────────────────────────────────────────────
#  PERSONA LAYER — persona definition + style samples + dynamic prompt builder
# ─────────────────────────────────────────────
_persona_cache: str | None = None


def load_persona() -> str:
    """Load persona definition from persona/persona.txt (cached after first read)"""
    global _persona_cache
    if _persona_cache is None:
        path = BASE_DIR / "persona" / "persona.txt"
        if path.exists():
            lines = [
                l for l in path.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")
            ]
            _persona_cache = "\n".join(lines).strip()
        else:
            _persona_cache = ""
    return _persona_cache


def load_style_by_category(category: str, max_count: int = 15) -> str:
    """
    Load style samples from persona/style.txt filtered by ## category label.
    Falls back to all samples if the requested category is not found.
    """
    import random
    path = BASE_DIR / "persona" / "style.txt"
    if not path.exists():
        return ""

    raw = path.read_text(encoding="utf-8").splitlines()
    sections: dict[str, list[str]] = {}
    current_section = "_all"
    for line in raw:
        if line.startswith("##"):
            current_section = line.lstrip("#").strip()
        elif line.strip() and not line.startswith("#"):
            sections.setdefault("_all", []).append(line.strip())
            sections.setdefault(current_section, []).append(line.strip())

    pool = sections.get(category) or sections.get("_all", [])
    samples = random.sample(pool, min(max_count, len(pool)))
    return "\n".join(samples)


def build_dynamic_prompt(state: dict, strategy: str) -> str:
    """
    Persona layer: combine strategy rules + persona definition + style examples into a full system prompt.
    """
    parts: list[str] = []

    parts.append(STRATEGY_PROMPTS.get(strategy, STRATEGY_PROMPTS["casual"]))

    persona = load_persona()
    if persona:
        parts.append(f"Persona:\n{persona}")

    style_category = STRATEGY_STYLE_MAP.get(strategy, "casual")
    examples = load_style_by_category(style_category, max_count=12)
    if examples:
        parts.append(f"Style examples ({style_category}) — mimic this tone:\n{examples}")

    parts.append(
        "Core constraints (always apply):\n"
        "- Sound like a real person; never reveal AI identity\n"
        "- Keep replies short: 1-2 sentences\n"
        "- Use natural conversational particles and fillers\n"
        "- Jump straight into the conversation — no greetings, no preamble\n"
        "- If asked for location / meetup / real name / contact info, deflect gracefully"
    )

    return "\n\n".join(parts)


def load_style_examples(max_count: int = 40) -> str:
    """Compatibility shim: load all style samples."""
    return load_style_by_category("_all", max_count)


def build_system_prompt() -> str:
    """Compatibility shim: use claude_system config + all style samples."""
    examples = load_style_examples()
    base = CONFIG["claude_system"]
    if examples:
        base += f"\n\nStyle reference — messages written in the target voice:\n{examples}"
    return base


# ─────────────────────────────────────────────
#  VALIDATION LAYER — post-generation safety filter
# ─────────────────────────────────────────────
_SENSITIVE_RE = re.compile(
    r"\d{7,}"          # phone / ID numbers
    r"|1[3-9]\d{9}"    # Chinese mobile number pattern
    r"|@\w+"           # @username
    r"|微信\s*[:：]"   # WeChat ID lead-in
)


def validate_reply(reply: str) -> str:
    """
    Post-generation validation: flatten to single line, truncate at sentence boundary, redact sensitive content.
    """
    reply = reply.replace("\n", " ").replace("\r", "").strip()

    if _SENSITIVE_RE.search(reply):
        return "Haha let's talk about something else — what time do you usually sleep?"

    if len(reply) > 50:
        for punct in ["。", "？", "！", "?", "!"]:
            idx = reply.find(punct)
            if 0 < idx <= 50:
                return reply[:idx + 1]
        return reply[:50]

    return reply


# ─────────────────────────────────────────────
#  GENERATION LAYER — unified AI call interface
# ─────────────────────────────────────────────
def _resolve_system_prompt(override: str | None) -> str:
    """Return override system prompt if provided, else fall back to configured default."""
    return override if override else build_system_prompt()


def ask_ai(
    message: str,
    history: list[dict] | None = None,
    system_prompt: str | None = None,
) -> str:
    """
    Generation layer: call the configured AI provider and return the reply text.
    system_prompt: injected by the strategy/persona layer; falls back to claude_system if None.
    history: [{"role": "user/assistant", "content": "..."}]
    """
    mode    = CONFIG["ai_mode"]
    history = history or []
    sys_p   = _resolve_system_prompt(system_prompt)

    if mode == "mock":
        return "[AUTO] Got your message, will reply shortly~"

    if mode == "openai":
        api_key = CONFIG["openai_api_key"]
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set — add it to .env")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = [{"role": "system", "content": sys_p}]
        messages += history
        messages.append({"role": "user", "content": message})
        body = {
            "model":      CONFIG["openai_model"],
            "messages":   messages,
            "max_tokens": 200,
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json=body, headers=headers, timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    if mode == "deepseek":
        api_key = CONFIG["deepseek_api_key"]
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set — add it to .env")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = [{"role": "system", "content": sys_p}]
        messages += history
        messages.append({"role": "user", "content": message})
        body = {
            "model":      CONFIG["deepseek_model"],
            "messages":   messages,
            "max_tokens": 80,
        }
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=body, headers=headers, timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    if mode == "claude":
        api_key = CONFIG["claude_api_key"]
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set — add it to .env")
        headers = {
            "x-api-key":          api_key,
            "anthropic-version":  "2023-06-01",
            "Content-Type":       "application/json",
        }
        messages = list(history) + [{"role": "user", "content": message}]
        body = {
            "model":      CONFIG["claude_model"],
            "max_tokens": 200,
            "system":     sys_p,
            "messages":   messages,
        }
        resp = requests.post(
            f"{CONFIG['claude_base_url']}/v1/messages",
            json=body, headers=headers, timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()

    raise ValueError(f"Unknown ai_mode: {mode!r}. Allowed values: mock / openai / claude / deepseek")


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
def run():
    print("=== Android LLM Agent — Starting ===")
    print(f"  AI provider  : {CONFIG['ai_mode']}")
    print(f"  Poll interval: {CONFIG['poll_interval']}s")
    print("  Press Ctrl+C to stop\n")

    devices = adb("devices")
    print(f"[ADB] {devices}")
    if "device" not in devices:
        print("❌ No device detected. Connect your Android device and enable USB debugging.")
        return

    last_text:            str                        = ""
    sent_messages:        set                        = set()
    replied_to:           collections.OrderedDict    = collections.OrderedDict()
    conversation_history: list[dict]                 = []
    session_state:        dict                       = {"strategy_history": []}

    while True:
        try:
            # 1. Capture screenshot
            img_path = screenshot()

            # 2. OCR — extract visible chat text
            current_text = extract_chat_text(img_path)

            # 3. Detect new incoming message (trigger line only)
            new_msg = detect_new_message(current_text, last_text, sent_messages)

            if new_msg and new_msg not in replied_to:
                ts = time.strftime("%H:%M:%S")

                # 3b. Collect all new lines for richer context (multi-line merge)
                ctx_lines = collect_new_lines(current_text, last_text, sent_messages)
                ctx_text  = " ".join(ctx_lines) if ctx_lines else new_msg
                print(f"\n[{ts}][NEW] {new_msg}")

                # 4. Understanding layer — detect 3D state (emotion × intent × risk)
                state    = detect_state(ctx_text)

                # 5. Strategy layer — pick conversation strategy
                strategy = select_strategy(state, session_state)
                print(f"[{ts}][STATE] emotion={state['emotion']} intent={state['intent']} risk={state['risk']} → {strategy}")

                # 6. Persona layer — build dynamic system prompt
                sys_prompt = build_dynamic_prompt(state, strategy)

                # 7. Generation layer — call AI
                reply = ask_ai(new_msg, history=conversation_history, system_prompt=sys_prompt)

                # 8. Validation layer — safety filter + length trim
                reply = validate_reply(reply)
                print(f"[{ts}][AI]  {reply}")

                # 9. Execution layer — send via ADB
                send_reply(reply)
                print(f"[{ts}][SENT] ✓")

                # Dedup ring buffer: keep last 50 messages
                replied_to[new_msg] = None
                if len(replied_to) > 50:
                    replied_to.popitem(last=False)

                # Track sent messages to prevent OCR echo triggering a second reply
                sent_messages.add(reply)
                if len(sent_messages) > 100:
                    sent_messages.clear()

                # Update conversation history (sliding window of history_turns)
                conversation_history.append({"role": "user",      "content": new_msg})
                conversation_history.append({"role": "assistant",  "content": reply})
                max_msgs = CONFIG["history_turns"] * 2
                if len(conversation_history) > max_msgs:
                    del conversation_history[:-max_msgs]

                # Update session state — track last 10 strategy choices
                session_state["strategy_history"].append(strategy)
                if len(session_state["strategy_history"]) > 10:
                    session_state["strategy_history"].pop(0)

            last_text = current_text
            time.sleep(CONFIG["poll_interval"])

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(CONFIG["poll_interval"])


if __name__ == "__main__":
    run()
