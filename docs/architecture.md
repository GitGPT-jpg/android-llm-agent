# System Architecture

## Overview

Android LLM Agent is a **7-layer cognitive pipeline** that runs on a host machine and controls an Android device via ADB. Each layer transforms raw pixel data into a context-aware reply and delivers it back to the device.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Host Machine (Python)                        │
│                                                                     │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │Perception│→ │Understanding│→ │ Strategy │→ │    Generation    │  │
│  │ OCR/ADB  │  │Emotion/Risk │  │6-way sel.│  │Claude/GPT/DeepSeek│ │
│  └──────────┘  └────────────┘  └──────────┘  └──────────────────┘  │
│       ↑                                               ↓             │
│  ┌──────────┐                              ┌──────────────────────┐ │
│  │Execution │←─────── Validation ──────────│   Persona Engine     │ │
│  │ADB input │         (regex+len)          │  (dynamic prompt)    │ │
│  └──────────┘                              └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              ↕ ADB (USB / TCP)
                    ┌─────────────────────────┐
                    │     Android Device      │
                    │  Chat app (any CJK app) │
                    └─────────────────────────┘
```

---

## Layer 1 — Perception

**File**: `auto_reply.py` — `_capture_screen()`, `_extract_latest_message()`

| Step | Tool | Description |
|------|------|-------------|
| Screenshot | `adb exec-out screencap -p` | Lossless PNG capture over ADB |
| Crop | PIL / NumPy | Extracts the chat bubble region defined in `config/device.json` |
| OCR | EasyOCR (ONNX, CPU) | Detects Chinese + English text; returns bounding boxes |
| Bubble filter | Coordinate heuristic | Skips right-side bubbles (`center_x / width > 0.55`) to ignore self-sent messages |

**Design decision**: EasyOCR runs entirely on-device (CPU ONNX) — no cloud OCR calls, no privacy risk.

---

## Layer 2 — Understanding

**File**: `auto_reply.py` — `_analyse_message()`

The agent models conversation state as a **3-dimensional vector**:

```
state = {
    emotion:  negative | neutral | positive | flirty,
    intent:   question | venting | advancing | neutral,
    risk:     high | medium | low
}
```

Classification uses keyword sets (`_NEGATIVE_KW`, `_POSITIVE_KW`, etc.) — deliberately rule-based for speed and explainability.  
`risk` is computed separately via `_HIGH_RISK_KW` / `_MED_RISK_KW` to gate dangerous replies.

---

## Layer 3 — Strategy Selection

**File**: `auto_reply.py` — `_select_strategy()`

| Strategy | Trigger condition |
|----------|------------------|
| `deflect` | High-risk message detected |
| `comfort` | Negative emotion |
| `flirt` | Flirty intent |
| `answer` | Question detected |
| `empathise` | Venting intent |
| `casual` | Default / fallback |

**Anti-loop guard**: `comfort` is capped at 3 consecutive uses → auto-falls back to `casual`.

---

## Layer 4 — Persona Engine

**File**: `auto_reply.py` — `_build_system_prompt()`

The system prompt is assembled at runtime from:

1. **`persona/persona.txt`** — character definition, backstory, communication style
2. **`persona/style.txt`** — curated example lines, categorised by strategy
3. **Active strategy** — the appropriate style examples are injected

This makes the agent's voice **configurable without changing code** — drop in a new `persona.txt` to change who the agent is.

---

## Layer 5 — Generation

**File**: `auto_reply.py` — `_call_llm()`

Supports three backends, selected via `AI_MODE` env var:

| Mode | Model | Notes |
|------|-------|-------|
| `claude` | `claude-3-5-haiku-20241022` | Highest quality; via Anthropic API |
| `gpt` | `gpt-4o-mini` | OpenAI API |
| `deepseek` | `deepseek-chat` | Low cost; OpenAI-compatible endpoint |
| `mock` | — | Returns a static string; safe default for testing |

All LLM calls use the same `requests`-based HTTP client with a 15 s timeout.

---

## Layer 6 — Validation

**File**: `auto_reply.py` — `_validate_reply()`

Checks applied in order:

1. **Sensitive data regex** — strips phone numbers, WeChat IDs, URLs
2. **Length gate** — replies must be 2–80 characters
3. **Noise filter** — rejects UI strings accidentally captured by OCR (`_NOISE_RE`)
4. **Fallback** — if all checks fail, returns a safe neutral reply

---

## Layer 7 — Execution

**File**: `auto_reply.py` — `_send_reply()`

CJK text input is non-trivial over ADB. The agent uses a **3-tier fallback**:

```
Tier 1: ADBKeyBoard (base64 broadcast)
        → custom Android IME; accepts any Unicode via ADB broadcast
Tier 2: Clipper (clipboard paste)
        → pastes via clipboard; requires Clipper app installed
Tier 3: ASCII fallback
        → last resort; only works for ASCII replies
```

**Recommended**: Install [ADBKeyBoard](https://github.com/senzhk/ADBKeyBoard) on the device for reliable CJK input.

---

## Configuration

### `config/device.json`

Defines the **pixel coordinates** for each UI element on the target device. Coordinates are device-specific and must be calibrated with `scripts/adb_helper.py`.

```json
{
  "screen_width": 1080,
  "screen_height": 2340,
  "chat_list": { "crop": [0, 120, 1080, 1800] },
  "input_box": { "tap": [540, 2200] },
  "send_button": { "tap": [1000, 2200] }
}
```

### `persona/persona.txt`

Free-form character definition. Anything you write here becomes part of the LLM system prompt.

### `persona/style.txt`

Example lines, formatted as:

```
[casual]
Hey! What's up?

[empathy]
That sounds really tough. I'm here.
```

---

## Concurrency Model

The main loop is **single-threaded** with a configurable polling interval (`POLL_INTERVAL_SEC`, default 5 s). Each iteration:

1. Captures a screenshot
2. Extracts the latest message
3. Checks if the message is new (deduplication by content hash)
4. Runs the pipeline if new
5. Sleeps for `POLL_INTERVAL_SEC`

The bottleneck is OCR (~0.5–1 s on CPU). For lower latency, run on a machine with a GPU — EasyOCR will automatically use CUDA if available.

---

## Security Considerations

| Risk | Mitigation |
|------|------------|
| API key exposure | Keys in `.env` only; `.env` in `.gitignore` |
| Personal data in screenshots | `tmp/` gitignored; files auto-deleted after each cycle |
| Persona data | `persona/persona.txt` and `persona/style.txt` gitignored |
| Device coordinates | `config/device.json` gitignored; only example committed |
| Sensitive reply content | Regex validation strips phone numbers, WeChat IDs, URLs before sending |
