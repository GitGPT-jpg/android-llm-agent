<div align="right">
  <a href="README.md">English</a> | <a href="README_CN.md"><b>中文</b></a>
</div>

# Android LLM Agent

> 一个基于 ADB 的视觉-语言自动化 Agent，通过 OCR 实时读取 Android 屏幕内容，并使用多模型 LLM 自动生成聊天回复。具备可配置人格、动态对话策略，以及「情绪 × 意图 × 风险」三维状态机。

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [快速启动](#快速启动)
- [Docker 部署](#docker-部署)
- [配置说明](#配置说明)
  - [环境变量](#环境变量)
  - [设备坐标](#设备坐标)
  - [人格与风格](#人格与风格)
- [AI 模型支持](#ai-模型支持)
- [系统设计](#系统设计)
- [API 参考](#api-参考)
- [项目截图](#项目截图)
- [Roadmap](#roadmap)

---

## 项目简介

**Android LLM Agent** 无需 Root 权限，无需修改任何 App，完全通过 ADB（Android Debug Bridge）和计算机视觉控制 Android 设备，实现智能聊天自动回复。

### 适用场景

| 领域 | 应用场景 |
|------|---------|
| 🤖 AI Agent 研究 | 研究 LLM 驱动的社交对话模式 |
| 📱 移动端自动化 | 大规模测试聊天 UI 行为 |
| 🎭 人格模拟 | 评估 LLM 在不同 Prompt 下的人格一致性 |
| 🔬 NLP 研究 | 采集真实对话策略数据 |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       Android LLM Agent 处理管道                          │
│                                                                          │
│   Android 设备                   宿主机 (Python)                          │
│   ─────────────    ADB USB/TCP   ──────────────────────────────────────  │
│                                                                          │
│   ┌─────────┐  screencap -p   ┌──────────────┐                         │
│   │  手机   │ ──────────────► │   感知层     │  EasyOCR (中英文)        │
│   │  屏幕   │                 │  Perception  │  左侧气泡 x 坐标过滤     │
│   └─────────┘                 └──────┬───────┘                         │
│                                      │ 原始文本行                       │
│                               ┌──────▼───────┐                         │
│                               │   理解层     │  三维状态检测             │
│                               │Understanding │  情绪 × 意图 × 风险      │
│                               └──────┬───────┘                         │
│                                      │ 状态字典                         │
│                               ┌──────▼───────┐                         │
│                               │   策略层     │  6 种对话策略             │
│                               │   Strategy   │  历史感知选择            │
│                               └──────┬───────┘                         │
│                                      │ 策略键                          │
│                               ┌──────▼───────┐                         │
│                               │   人格层     │  动态系统 Prompt          │
│                               │    Persona   │  人格 + 少样本风格注入    │
│                               └──────┬───────┘                         │
│                                      │ 系统 Prompt                     │
│                               ┌──────▼───────┐                         │
│                               │   生成层     │  Claude / GPT / DeepSeek │
│                               │  Generation  │  统一 ask_ai() 接口      │
│                               └──────┬───────┘                         │
│                                      │ 原始回复                         │
│                               ┌──────▼───────┐                         │
│                               │   验证层     │  敏感信息正则过滤         │
│                               │  Validation  │  长度截断（按句边界）    │
│                               └──────┬───────┘                         │
│                                      │ 清洁回复                         │
│                               ┌──────▼───────┐                         │
│   ┌─────────┐   ADB 输入     │   执行层     │  ADBKeyBoard (base64)   │
│   │  手机   │ ◄──────────────│  Execution   │  Clipper (剪贴板)       │
│   │  输入框 │                └──────────────┘  ASCII 兜底              │
│   └─────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 核心功能

- **零 Root，零改包** — 任何 Android App 均可通过 ADB 接入
- **多模型后端** — Claude、GPT-4o、DeepSeek，或 mock 模式
- **三维状态机** — 同时检测情绪 / 意图 / 风险
- **6 种对话策略** — 日常、安慰、调情、推进、转移、神秘
- **动态人格系统** — 按策略注入少样本风格示例
- **智能中文输入** — 三级兜底：ADBKeyBoard → Clipper → ASCII
- **气泡过滤** — x 坐标过滤防止回复自己消息
- **对话历史** — 滑动窗口上下文传入 LLM
- **安全验证** — 输出前正则过滤手机号、微信号等敏感信息

---

## 快速启动

### 前置条件

- Python 3.11+
- 开启 USB 调试的 Android 设备
- `adb` 可用（通过 `setup.ps1` 或手动安装）

### 1. 克隆并安装

```bash
git clone https://github.com/GitGPT-jpg/android-llm-agent.git
cd android-llm-agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制并编辑环境变量
cp .env.example .env

# 复制并标定设备坐标
cp config/device.example.json config/device.json

# 复制并自定义人格（可选）
cp persona/persona.example.txt persona/persona.txt
cp persona/style.example.txt persona/style.txt
```

编辑 `.env`：

```env
AI_MODE=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
```

根据你的设备屏幕分辨率编辑 `config/device.json` 中的坐标值。

### 3. 连接设备

```bash
adb devices
# 应显示：<serial>  device
```

### 4. 启动

```bash
python main.py
```

---

## Docker 部署

> 注意：ADB USB 直通需要额外的宿主机配置，详见 `docker-compose.yml` 注释。

```bash
# 构建镜像
docker build -t android-llm-agent .

# 使用 .env 文件运行
docker run --rm -it \
  --env-file .env \
  --network host \
  android-llm-agent
```

或使用 Docker Compose：

```bash
docker compose up
```

---

## 配置说明

### 环境变量

| 变量 | 是否必填 | 默认值 | 说明 |
|------|---------|--------|------|
| `AI_MODE` | 否 | `mock` | AI 提供商：`mock` \| `openai` \| `claude` \| `deepseek` |
| `OPENAI_API_KEY` | `AI_MODE=openai` 时必填 | — | OpenAI API Key |
| `ANTHROPIC_API_KEY` | `AI_MODE=claude` 时必填 | — | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | 否 | `https://api.anthropic.com` | Claude API 基础地址 |
| `DEEPSEEK_API_KEY` | `AI_MODE=deepseek` 时必填 | — | DeepSeek API Key |

### 设备坐标

`config/device.json` 定义了目标设备的屏幕区域和点击坐标。

```json
{
  "chat_crop": [10, 1050, 1075, 2000],
  "input_box_tap": [453, 2237],
  "send_via_enter": false,
  "send_btn_tap": [955, 2210],
  "right_bubble_threshold": 0.55
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `chat_crop` | `[left, top, right, bottom]` | 聊天消息区域的像素边界框 |
| `input_box_tap` | `[x, y]` | 点击输入框的坐标 |
| `send_via_enter` | `bool` | 是否用回车键代替点击发送按钮 |
| `send_btn_tap` | `[x, y]` | 发送按钮坐标 |
| `right_bubble_threshold` | `float` | x/宽度比超过此值的气泡视为自己发出的消息 |

**标定技巧**：运行 `python scripts/adb_helper.py` 进行交互式坐标查找。

### 人格与风格

| 文件 | 用途 |
|------|------|
| `persona/persona.txt` | 人格定义，注入每次系统 Prompt |
| `persona/style.txt` | 按策略分组的少样本风格示例（`## casual`、`## flirt` 等） |

格式参考见 `persona/persona.example.txt` 和 `persona/style.example.txt`。

---

## AI 模型支持

| 提供商 | `AI_MODE` 值 | 模型 | 备注 |
|--------|------------|------|------|
| Mock | `mock` | — | 空运行，不调用 API |
| OpenAI | `openai` | `gpt-4o-mini` | 标准 Chat Completions |
| Anthropic | `claude` | `claude-3-5-haiku-20241022` | Messages API |
| DeepSeek | `deepseek` | `deepseek-chat` | OpenAI 兼容端点 |

所有提供商共享同一 `ask_ai(message, history, system_prompt)` 接口。

---

## 系统设计

### 三维状态检测

每条传入消息在三个独立维度上同时分类：

```
情绪 Emotion:  neutral | positive | negative | flirt_signal
意图 Intent:   casual  | question | venting  | relationship_advance
风险 Risk:     low     | medium   | high
```

风险优先级最高 — 任何 `medium` 或 `high` 风险都会触发 `deflect` 策略，无视情绪和意图。

### 策略选择（优先级顺序）

```
1. risk = high / medium              → deflect（转移）
2. emotion = flirt_signal            → flirt（调情）
3. emotion = negative                → comfort（安慰，连续 3 次后降级为 casual）
4. intent = relationship_advance,
   历史包含 flirt/advance            → advance（推进）
5. intent = relationship_advance     → flirt（调情）
6. emotion = positive, intent=casual → flirt（调情）
7. intent = question                 → mystery（神秘）
8. 默认                              → casual（日常）
```

### CJK 输入三级兜底

```
一级：ADBKeyBoard（base64 广播）— 无损，推荐
二级：Clipper（剪贴板粘贴）    — 无损，需安装 Clipper APK
三级：adb input text           — 仅支持 ASCII；中文会被丢弃
```

---

## API 参考

核心函数均可直接导入，便于编程调用或测试：

```python
from auto_reply import (
    detect_state,           # 三维状态分析
    select_strategy,        # 策略选择
    build_dynamic_prompt,   # 人格 + 风格 Prompt 构建
    ask_ai,                 # 统一 LLM 调用
    validate_reply,         # 生成后安全过滤
    send_reply,             # ADB 执行
)

# 分析传入消息
state = detect_state("最近真的好累啊")
# → {"emotion": "negative", "intent": "venting", "risk": "low"}

strategy = select_strategy(state, session_state={"strategy_history": []})
# → "comfort"

prompt = build_dynamic_prompt(state, strategy)
reply  = ask_ai("最近真的好累啊", system_prompt=prompt)
reply  = validate_reply(reply)
# → "听起来你最近压力很大，跟我说说发生什么了？"
```

---

## 项目截图

> *截图占位 — 将实际演示图片放入 `docs/screenshots/`*

| 管道日志 | 聊天示例 |
|:---:|:---:|
| ![Pipeline log](docs/screenshots/pipeline-log.png) | ![Chat demo](docs/screenshots/chat-demo.png) |

---

## Roadmap

- [ ] **Web 控制台** — 实时对话面板 + 策略可视化
- [ ] **多设备支持** — 并行管理多个 ADB 目标
- [ ] **Webhook 集成** — 支持 n8n、Zapier 等外部触发
- [ ] **RAG 长期记忆** — 通过向量存储实现跨会话记忆
- [ ] **App 预设配置** — 为主流 App 提供开箱即用的坐标配置
- [ ] **评估框架** — 策略正确性自动化测试套件
- [ ] **流式输入** — 逐字符输入，外观更接近真人
- [ ] **REST API** — HTTP 控制接口，支持无头部署

---

## 项目结构

```
android-llm-agent/
├── main.py                    # 启动入口
├── auto_reply.py              # 核心 Agent 引擎（7 层管道）
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
│
├── config/
│   ├── device.example.json    # 坐标模板
│   └── device.json            # ← 本地配置（gitignored）
│
├── persona/
│   ├── persona.example.txt
│   ├── style.example.txt
│   ├── persona.txt            # ← gitignored
│   └── style.txt              # ← gitignored
│
├── scripts/
│   ├── adb_helper.py          # 设备标定工具
│   ├── learn_style.py         # 风格样本采集
│   └── test_ocr.py            # OCR 精度测试
│
├── docs/
│   ├── architecture.md
│   └── screenshots/
│
├── tools/                     # ADB 二进制（gitignored）
└── tmp/                       # 运行时临时文件（gitignored）
```

---

## License

[MIT](LICENSE) © 2025
