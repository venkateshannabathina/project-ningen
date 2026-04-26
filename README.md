---
title: Project Ningen
emoji: 🏢
colorFrom: blue
colorTo: red
sdk: docker
pinned: false
---
# Ningen (人間)

AI boardroom that turns a startup idea into requirements, product output, marketing assets, operations docs, and strategy docs.

## What It Does

Ningen runs a 4-agent board meeting (CEO, CTO, CMO, COO), then executes downstream agents on the latest generated requirements.

- **Board meeting engine** in `board_meeting.py`:
  - Round 1: opening positions
  - Client clarifications
  - Round 2: reactions
  - Conflict detection and resolution
  - Final briefings + requirements generation
- **Execution agents**:
  - `execute_cto.py`: generates a build prompt and runs Claude Code to create product output
  - `execute_cmo.py`: generates/publishes marketing artifacts
  - `execute_coo.py`: generates `execution_plan.md` and `risk_register.md`
  - `execute_ceo.py`: generates `investor_pitch.md` and `executive_summary.md`
- **Memory layer** in `memory_store.py`: stores summaries of recent runs in `outputs/memory_store.json`

## Current Entry Points

- `run_all.py`: full autonomous pipeline (board meeting + CTO + CMO + COO + CEO)
- `app.py`: Streamlit frontend (embedded UI) that talks to `api_server.py`
- `start.sh`: convenience launcher for API + Streamlit together
- `dashboard/app.py`: terminal-style board meeting flow
- `ningen_env.py`: RL-style experiment runner and reward logging

## Project Layout

```text
project-ningen/
├── board_meeting.py
├── api_server.py
├── app.py
├── run_all.py
├── execute_cto.py
├── execute_cmo.py
├── execute_coo.py
├── execute_ceo.py
├── memory_store.py
├── ningen_env.py
├── start.sh
├── dashboard/
│   └── app.py
├── outputs/
└── requirements.txt
```

## Setup

### 1) Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2) Create `.env`

At minimum:

```env
OPENAI_API_KEY=your_openai_key
```

Optional (used by marketing publishing paths):

```env
RESEND_API_KEY=your_resend_key
RESEND_FROM_EMAIL=you@domain.com
RESEND_SUBSCRIBER_EMAILS=user1@example.com,user2@example.com
DEVTO_API_KEY=your_devto_key
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 3) Install Claude Code CLI (for CTO build path)

```bash
npm install -g @anthropic-ai/claude-code
```

## Usage

### Run everything in one command

```bash
python3 run_all.py "AI-powered invoicing assistant for freelancers"
```

Without an argument, it prompts for an idea interactively.

### Run only the board meeting

```bash
python3 dashboard/app.py
```

### Run web UI (Streamlit + Flask API)

```bash
./start.sh
```

Or manually:

```bash
streamlit run app.py
```

### Run individual execution agents

```bash
python3 execute_cto.py
python3 execute_cmo.py
python3 execute_coo.py
python3 execute_ceo.py
```

### Run RL baseline experiment

```bash
python3 ningen_env.py
```

## Outputs

Board meeting outputs are stored per generated product folder under `outputs/`:

- `outputs/<ProductName>/<ProductName>_requirements.json`
- `outputs/<ProductName>/<ProductName>_briefings.json`

Execution artifacts are written to `outputs/` root, including:

- `index.html`
- `cto_claude_prompt.txt`
- `cold_email.md`
- `devto_article.md`
- `discord_post.md`
- `reddit_post.md`
- `execution_plan.md`
- `risk_register.md`
- `investor_pitch.md`
- `executive_summary.md`
- `memory_store.json`
- `episode_log.json`
- `rl_experiment.json`

## Notes

- Several files in this repository are generated outputs and may change often.
- Execution agents read the **latest** available requirements/briefings from `outputs/`.
