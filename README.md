# Multi-Agent Task Orchestrator

An autonomous multi-agent system that monitors Slack for task requests, uses Google Gemini to decompose them into subtasks, dispatches those subtasks to specialized agents (code, file, git, test), and surfaces real-time progress on a Waveshare e-ink display. Human approval gates pause execution for destructive operations like `git push` or file deletion.

Designed to run on a Raspberry Pi with a Waveshare 7.5" V2 e-ink display, with full macOS support for local development.

---

## How It Works

```
Slack @mention
  → Bot creates a Task, acknowledges in thread
  → Gemini decomposes the task into a SubTask list
  → E-ink display shows "Task Received"
  → For each SubTask:
      → Display updates progress bar
      → If requires_approval → Block Kit buttons posted in Slack, waits for click
      → Dispatched to: CodeAgent / FileAgent / GitAgent / TestAgent
      → Result logged to audit.jsonl
  → Display shows "Complete" at 100%
  → Bot posts summary to thread
```

### Agents

| Agent | What it does |
|-------|-------------|
| **OrchestratorAgent** | Calls Gemini to decompose the task, coordinates all sub-agents |
| **CodeAgent** | Generates code via Gemini prompt |
| **FileAgent** | Reads, writes, deletes, lists files in `./workspace` with auto-backup |
| **GitAgent** | git status/add/commit/push/diff/log — AI-generated commit messages |
| **TestAgent** | Runs pytest in a subprocess, returns output |
| **DisplayAgent** | Renders progress images to the e-ink display |

---

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/docs/#installation)
- A [Google AI Studio](https://aistudio.google.com/) account (free Gemini API key)
- A Slack workspace where you can create apps
- *(Production only)* Raspberry Pi with Waveshare 7.5" V2 e-ink HAT

---

## Setup

### 1. Clone and install

```bash
git clone <your-repo-url>
cd multi_agent
poetry install
```

On macOS, the RPi-only dependencies (`spidev`, `rpi-gpio`) are automatically skipped.

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in the three required secrets:

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
GEMINI_API_KEY=...
```

Details on obtaining each are in the sections below.

### 3. (Optional) Tune config.yaml

`config.yaml` controls model settings, display dimensions, workspace paths, and log level. Environment variables in `.env` always override the YAML values for secrets.

---

## Getting API Keys

### Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Copy the key into `GEMINI_API_KEY` in your `.env`

The default model is `gemini-2.0-flash`. Change it in `config.yaml` under `gemini.model`.

### Slack App Setup

You need **two tokens**: a Bot Token (`xoxb-`) and an App-Level Token (`xapp-`).

#### Create the app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. `multi-agent`) and pick your workspace

#### Enable Socket Mode

1. In the left sidebar → **Socket Mode** → toggle **Enable Socket Mode** on
2. Under **App-Level Tokens** → **Generate Token** → name it `socket-token`, add scope `connections:write`
3. Copy the `xapp-...` token → `SLACK_APP_TOKEN` in `.env`

#### Bot scopes

1. Left sidebar → **OAuth & Permissions** → **Bot Token Scopes**, add:
   - `app_mentions:read`
   - `chat:write`
   - `channels:history`
2. Left sidebar → **Install App** → **Install to Workspace** → authorize
3. Copy the `xoxb-...` **Bot User OAuth Token** → `SLACK_BOT_TOKEN` in `.env`

#### Enable Events

1. Left sidebar → **Event Subscriptions** → toggle on
2. Under **Subscribe to bot events** → **Add Bot User Event** → `app_mention`
3. Save changes

#### Invite the bot to a channel

```
/invite @multi-agent
```

Set `SLACK_CHANNEL_ID` in `.env` to that channel's ID (right-click the channel → **Copy link** — the ID is the part after the last `/`).

---

## Running

### macOS (development)

```bash
poetry run multi-agent
```

No Slack tokens? The bot starts in **display-only mode** — the startup screen is written to `/tmp/multi_agent_display.bmp` and the process waits. Useful for testing the display subsystem without Slack.

With tokens configured, the bot connects via Socket Mode and waits for `@mention`s.

### Raspberry Pi (production)

Same command — the system auto-detects Linux and uses the real e-ink hardware driver:

```bash
poetry run multi-agent
```

To run as a background service:

```bash
# Create a systemd service
sudo nano /etc/systemd/system/multi-agent.service
```

```ini
[Unit]
Description=Multi-Agent Task Orchestrator
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/multi_agent
ExecStart=/home/pi/.local/bin/poetry run multi-agent
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/pi/multi_agent/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable multi-agent
sudo systemctl start multi-agent
sudo journalctl -u multi-agent -f   # follow logs
```

---

## Using the Bot

### Trigger a task

Mention the bot in any channel it's been invited to:

```
@multi-agent write a Python script that fetches the current Bitcoin price and saves it to btc.json
```

The bot will:
1. Reply in the thread confirming receipt
2. Call Gemini to decompose the request into subtasks
3. Execute each subtask, posting updates to the thread
4. Update the e-ink display with a progress bar throughout

### Approving destructive operations

For operations flagged as requiring approval (e.g. `git push`, file deletion), the bot posts a message with **Approve** and **Reject** buttons. The task pauses until you click one. Approval auto-times out after 5 minutes (configurable via `approval_timeout_seconds` in `config.yaml`).

---

## Project Structure

```
multi_agent/
├── pyproject.toml
├── config.yaml                     # Non-secret configuration
├── .env.example                    # Secret credential template
├── multi_agent/
│   ├── __main__.py                 # asyncio entry point
│   ├── config.py                   # YAML + .env → AppConfig
│   ├── platform_detect.py          # macOS vs RPi detection
│   ├── audit_log.py                # Async JSONL audit trail
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── orchestrator_agent.py
│   │   ├── code_agent.py
│   │   ├── file_agent.py
│   │   ├── git_agent.py
│   │   ├── test_agent.py
│   │   └── display_agent.py
│   ├── slack/
│   │   ├── bot.py                  # Socket Mode app
│   │   ├── approval_gate.py        # asyncio.Future approval waiter
│   │   └── message_builder.py      # Block Kit JSON builders
│   ├── llm/
│   │   └── gemini_client.py        # google-genai wrapper
│   ├── display/
│   │   ├── display_manager.py      # Platform-dispatching interface
│   │   ├── eink_driver.py          # RPi hardware driver
│   │   ├── macos_driver.py         # macOS fallback (saves BMP)
│   │   ├── image_builder.py        # PIL progress UI composer
│   │   └── waveshare_epd/          # Vendored Waveshare drivers
│   └── models/
│       ├── task.py                 # Task, SubTask, TaskStatus
│       └── agent_result.py         # AgentResult
├── workspace/                      # Agent working directory
├── backups/                        # Auto-backups before file writes
├── logs/                           # audit.jsonl
└── tests/
    └── test_smoke.py
```

### Key directories

| Directory | Purpose |
|-----------|---------|
| `workspace/` | All agent file operations are sandboxed here |
| `backups/` | Timestamped backup of every file before it is overwritten or deleted |
| `logs/audit.jsonl` | Append-only JSONL log of every task, subtask, and approval event |

---

## Tests

```bash
poetry run pytest tests/ -v
```

The smoke test suite covers imports, config loading, models, display image generation, the macOS BMP driver, approval gate flow (approve/reject/timeout), FileAgent read/write/path-traversal protection, and Block Kit message shape.

---

## Configuration Reference

`config.yaml` — all values can be overridden by environment variables:

```yaml
slack:
  bot_token: ""               # env: SLACK_BOT_TOKEN
  app_token: ""               # env: SLACK_APP_TOKEN
  channel_id: ""              # env: SLACK_CHANNEL_ID
  approval_timeout_seconds: 300

gemini:
  api_key: ""                 # env: GEMINI_API_KEY
  model: "gemini-2.0-flash"
  temperature: 0.7
  max_tokens: 8192

display:
  epd_model: "epd7in5_V2"
  width: 800
  height: 480

workspace:
  path: "./workspace"
  backup_path: "./backups"

log_path: "./logs/audit.jsonl"
log_level: "DEBUG"            # DEBUG | INFO | WARNING | ERROR
```

---

## E-Ink Display Layout (800×480)

```
┌─────────────────────────────────────────┐
│ Multi-Agent Orchestrator                │
├─────────────────────────────────────────┤
│ Task: write a Python script that fetc…  │
│ Agent: CODE                             │
│ Step: Generating fetch_btc.py           │
│                                         │
│                                         │
│ 42% [████████░░░░░░░░░░░░░░░░░░░░░░░░] │
└─────────────────────────────────────────┘
```

On macOS the rendered image is saved to `/tmp/multi_agent_display.bmp` instead of driving hardware.

---

## Troubleshooting

**`No module named 'aiohttp'`** — run `poetry install` again; it should be present after a fresh install.

**`ModuleNotFoundError: No module named 'RPi'` on macOS** — this is expected and safe to ignore during import; the RPi driver is only loaded at runtime when `platform.system() == "Linux"`.

**Bot doesn't respond to mentions** — confirm Socket Mode is enabled in your Slack app settings and the `xapp-` App-Level Token has the `connections:write` scope.

**Approval buttons appear but clicks do nothing** — check that `approve_action` and `reject_action` action IDs are registered. The bolt `@app.action()` handlers in `slack/bot.py` handle these automatically when the bot is running.

**Gemini returns malformed JSON** — the orchestrator retries decomposition up to 3 times (tenacity). If it keeps failing, set `log_level: DEBUG` in `config.yaml` and inspect the raw Gemini response in the logs.
