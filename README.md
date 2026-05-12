<div align="right">
  <a href="README.md"><b>English</b></a> | <a href="README_CN.md">中文</a>
</div>

# Android LLM Agent

> An ADB-powered, vision-language pipeline that reads a live Android screen via OCR and replies to chat messages using multi-provider LLMs — with a configurable persona, dynamic conversation strategy, and a 3-dimensional state machine (emotion × intent × risk).

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Device Coordinates](#device-coordinates)
  - [Persona & Style](#persona--style)
- [AI Providers](#ai-providers)
- [System Design](#system-design)
- [API Reference](#api-reference)
- [Screenshots](#screenshots)
- [Roadmap](#roadmap)

---

## Overview

**Android LLM Agent** automates conversational responses on an Android device without requiring root access or app modification. It operates entirely through the Android Debug Bridge (ADB) and computer vision.

### Use Cases

| Domain | Application |
|--------|-------------|
| 🤖 AI Agent Research | Studying LLM-driven social conversation patterns |
| 📱 Mobile Automation | Testing chat UI behavior at scale |
| 🎭 Persona Simulation | Evaluating LLM persona consistency under varied prompts |
| 🔬 NLP Research | Collecting real-world conversation strategy data |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Android LLM Agent Pipeline                       │
│                                                                          │
│   Android Device                 Host Machine (Python)                   │
│   ─────────────    ADB USB/TCP   ──────────────────────────────────────  │
│                                                                          │
│   ┌─────────┐  screencap -p   ┌──────────────┐                         │
│   │  Phone  │ ──────────────► │  Perception  │  EasyOCR (ch_sim+en)    │
│   │ Screen  │                 │    Layer     │  Left-bubble x-filter   │
│   └─────────┘                 └──────┬───────┘                         │
│                                      │ raw text lines                  │
│                               ┌──────▼───────┐                         │
│                               │ Understanding│  3D State Detection      │
│                               │    Layer     │  emotion × intent × risk │
│                               └──────┬───────┘                         │
│                                      │ state dict                      │
│                               ┌──────▼───────┐                         │
│                               │   Strategy   │  6 strategies            │
│                               │    Layer     │  history-aware selection │
│                               └──────┬───────┘                         │
│                                      │ strategy key                    │
│                               ┌──────▼───────┐                         │
│                               │    Persona   │  dynamic system prompt   │
│                               │    Layer     │  persona + few-shot style│
│                               └──────┬───────┘                         │
│                                      │ system prompt                   │
│                               ┌──────▼───────┐                         │
│                               │  Generation  │  Claude / GPT / DeepSeek │
│                               │    Layer     │  unified ask_ai() API    │
│                               └──────┬───────┘                         │
│                                      │ raw reply                       │
│                               ┌──────▼───────┐                         │
│                               │  Validation  │  sensitive regex filter  │
│                               │    Layer     │  length trim at sentence │
│                               └──────┬───────┘                         │
│                                      │ clean reply                     │
│                               ┌──────▼───────┐                         │
│   ┌─────────┐   ADB input    │  Execution   │  ADBKeyBoard (base64)   │
│   │  Phone  │ ◄──────────────│    Layer     │  Clipper (clipboard)    │
│   │ Input   │                └──────────────┘  ASCII fallback          │
│   └─────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Features

- **Zero-root, zero-app-modification** — works with any Android app via ADB
- **Multi-LLM backend** — Claude, GPT-4o, DeepSeek, or mock mode
- **3D state machine** — simultaneous emotion / intent / risk detection
- **6 conversation strategies** — casual, comfort, flirt, advance, deflect, mystery
- **Dynamic persona system** — few-shot style injection per strategy
- **Smart CJK input** — 3-tier fallback: ADBKeyBoard → Clipper → ASCII
- **OCR bubble filtering** — x-coordinate filtering prevents self-reply loops
- **Conversation history** — sliding window context passed to LLM
- **Safety validation** — regex-based PII/sensitive content filter on output

---

## Quick Start

### Prerequisites

- Python 3.11+
- Android device with USB debugging enabled
- `adb` available (installed via `setup.ps1` or manually)

### 1. Clone & Install

```bash
git clone https://github.com/your-username/android-llm-agent.git
cd android-llm-agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy and edit environment variables
cp .env.example .env

# Copy and calibrate device coordinates
cp config/device.example.json config/device.json

# Copy and customize persona (optional)
cp persona/persona.example.txt persona/persona.txt
cp persona/style.example.txt persona/style.txt
```

Edit `.env`:

```env
AI_MODE=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
```

Edit `config/device.json` with coordinates calibrated for your device's screen resolution.

### 3. Connect Device

```bash
adb devices
# Should show: <serial>  device
```

### 4. Run

```bash
python main.py
```

---

## Docker Deployment

> Note: ADB USB passthrough requires additional host configuration. See `docker-compose.yml` comments.

```bash
# Build image
docker build -t android-llm-agent .

# Run with .env file
docker run --rm -it \
  --env-file .env \
  --network host \
  android-llm-agent
```

Or with Docker Compose:

```bash
docker compose up
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AI_MODE` | No | `mock` | AI provider: `mock` \| `openai` \| `claude` \| `deepseek` |
| `OPENAI_API_KEY` | If `AI_MODE=openai` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | If `AI_MODE=claude` | — | Anthropic API key |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | Claude API base URL |
| `DEEPSEEK_API_KEY` | If `AI_MODE=deepseek` | — | DeepSeek API key |

### Device Coordinates

`config/device.json` defines the screen regions and tap targets for your specific device.

```json
{
  "chat_crop": [10, 1050, 1075, 2000],
  "input_box_tap": [453, 2237],
  "send_via_enter": false,
  "send_btn_tap": [955, 2210],
  "right_bubble_threshold": 0.55
}
```

| Field | Type | Description |
|-------|------|-------------|
| `chat_crop` | `[l, t, r, b]` | Pixel bounding box of the chat message area |
| `input_box_tap` | `[x, y]` | Coordinates to tap the message input field |
| `send_via_enter` | `bool` | Use Enter key instead of tapping the send button |
| `send_btn_tap` | `[x, y]` | Coordinates of the send button |
| `right_bubble_threshold` | `float` | x/width ratio above which a bubble is treated as outgoing |

**Calibration tip**: Run `python scripts/adb_helper.py` for an interactive coordinate finder.

### Persona & Style

| File | Purpose |
|------|---------|
| `persona/persona.txt` | Character definition injected into every system prompt |
| `persona/style.txt` | Few-shot style examples grouped by strategy (`## casual`, `## flirt`, etc.) |

See `persona/persona.example.txt` and `persona/style.example.txt` for format reference.

---

## AI Providers

| Provider | `AI_MODE` value | Model | Notes |
|----------|-----------------|-------|-------|
| Mock | `mock` | — | Dry-run, no API calls |
| OpenAI | `openai` | `gpt-4o-mini` | Standard Chat Completions |
| Anthropic | `claude` | `claude-3-5-haiku-20241022` | Messages API |
| DeepSeek | `deepseek` | `deepseek-chat` | OpenAI-compatible endpoint |

All providers share the same `ask_ai(message, history, system_prompt)` interface.

---

## System Design

### 3D State Detection

Each incoming message is classified across three independent dimensions:

```
Emotion:  neutral | positive | negative | flirt_signal
Intent:   casual  | question | venting  | relationship_advance
Risk:     low     | medium   | high
```

Risk always takes precedence — any `medium` or `high` risk triggers `deflect` regardless of emotion/intent.

### Strategy Selection (Priority Order)

```
1. risk = high / medium           → deflect
2. emotion = flirt_signal         → flirt
3. emotion = negative             → comfort  (capped at 3 consecutive → casual)
4. intent = relationship_advance,
   history contains flirt/advance → advance
5. intent = relationship_advance  → flirt
6. emotion = positive,
   intent = casual                → flirt
7. intent = question              → mystery
8. default                        → casual
```

### CJK Input Tier Fallback

```
Tier 1: ADBKeyBoard (base64 broadcast) — lossless, recommended
Tier 2: Clipper (clipboard paste)      — lossless, requires Clipper APK
Tier 3: adb input text                 — ASCII only; CJK is dropped
```

---

## API Reference

The core functions are importable for programmatic use or testing:

```python
from auto_reply import (
    detect_state,           # 3D state analysis
    select_strategy,        # strategy selection
    build_dynamic_prompt,   # persona + style prompt builder
    ask_ai,                 # unified LLM call
    validate_reply,         # post-generation safety filter
    send_reply,             # ADB execution
)

# Analyze an incoming message
state = detect_state("I've been feeling exhausted lately")
# → {"emotion": "negative", "intent": "venting", "risk": "low"}

strategy = select_strategy(state, session_state={"strategy_history": []})
# → "comfort"

prompt = build_dynamic_prompt(state, strategy)
reply  = ask_ai("I've been feeling exhausted lately", system_prompt=prompt)
reply  = validate_reply(reply)
# → "That sounds really draining. What's been on your plate lately?"
```

---

## Screenshots

> *Screenshots placeholder — add real demo images to `docs/screenshots/`*

| Pipeline Log | Chat Example |
|:---:|:---:|
| ![Pipeline log](docs/screenshots/pipeline-log.png) | ![Chat demo](docs/screenshots/chat-demo.png) |

---

## Roadmap

- [ ] **Web UI** — real-time conversation dashboard with strategy visualization
- [ ] **Multi-device** — manage multiple ADB targets in parallel
- [ ] **Webhook support** — trigger from external events (n8n, Zapier, etc.)
- [ ] **RAG memory** — long-term conversation memory via vector store
- [ ] **App profiles** — pre-configured coordinate sets for popular apps
- [ ] **Evaluation harness** — automated test suite for strategy correctness
- [ ] **Streaming input** — progressive text entry for more natural appearance
- [ ] **REST API** — HTTP control interface for headless deployment

---

## Project Structure

```
android-llm-agent/
├── main.py                    # Entry point
├── auto_reply.py              # Core agent engine (7-layer pipeline)
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
│
├── config/
│   ├── device.example.json    # Coordinate template
│   └── device.json            # ← your local config (gitignored)
│
├── persona/
│   ├── persona.example.txt
│   ├── style.example.txt
│   ├── persona.txt            # ← gitignored
│   └── style.txt              # ← gitignored
│
├── scripts/
│   ├── adb_helper.py          # Device calibration tool
│   ├── learn_style.py         # Style sample collector
│   └── test_ocr.py            # OCR accuracy tester
│
├── docs/
│   ├── architecture.md
│   └── screenshots/
│
├── tools/                     # ADB binary (gitignored)
└── tmp/                       # Runtime artifacts (gitignored)
```

---

## License

[MIT](LICENSE) © 2025
