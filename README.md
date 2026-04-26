---
title: Project Ningen
emoji: 🏢
colorFrom: blue
colorTo: red
sdk: docker
pinned: false
---

# Ningen (人間) — AI Boardroom

Four AI executives debate your startup idea, detect conflicts, resolve them, then automatically build the product, write the marketing, plan execution, and draft the investor pitch.

---

## How It Works

1. You type a startup idea into the chat window
2. CEO, CTO, CMO, COO each give opening positions and ask you one clarifying question
3. You answer all four questions in one message
4. Agents react to each other, surface conflicts, and resolve them
5. Meeting ends — all four execution agents fire in parallel
6. Click any result card to see the output (live product preview, marketing posts, docs)

---

## Architecture

```
React UI (uidesign.html)
  └─ polls Flask API every 1.5s
       └─ Flask (api_server.py) on :5001
            └─ board_meeting.py  →  execute_cto/cmo/coo/ceo.py
```

- **Frontend**: React 18 + Babel (no build step), runs inside Streamlit iframe
- **API bridge**: Flask + flask-cors, shared state via `threading.Lock`
- **Board meeting**: GPT-4o-mini for all agent debate, conflict detection, requirements
- **CTO product build**: GPT-4o (8K tokens) → single-file HTML product
- **CMO / COO / CEO**: GPT-4o-mini → marketing posts, execution plan, investor pitch
- **Memory**: `memory_store.json` — last 3 meetings injected into every agent prompt

---

## Setup

```bash
git clone <repo>
cd project-ningen
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```env
OPENAI_API_KEY=your_openai_key
```

Optional (for CMO publishing):

```env
RESEND_API_KEY=your_resend_key
DEVTO_API_KEY=your_devto_key
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## Running

**Web UI (recommended):**

```bash
bash start.sh
# opens http://localhost:8501
```

**CLI — full pipeline:**

```bash
python3 run_all.py "your startup idea"
```

**Individual agents (after a board meeting has run):**

```bash
python3 execute_cto.py   # builds HTML product
python3 execute_cmo.py   # generates marketing content
python3 execute_coo.py   # generates execution plan + risk register
python3 execute_ceo.py   # generates investor pitch + exec summary
```

---

## Project Layout

```
project-ningen/
├── app.py                  # Streamlit entry point + HTML patcher
├── api_server.py           # Flask API bridge
├── board_meeting.py        # 3-round debate engine
├── execute_cto.py          # GPT-4o product builder
├── execute_cmo.py          # CMO marketing agent
├── execute_coo.py          # COO planning agent
├── execute_ceo.py          # CEO strategy agent
├── memory_store.py         # Cross-episode learning store
├── run_all.py              # Master CLI runner
├── ningen_env.py           # RL experiment runner
├── uidesign.html           # React boardroom UI
├── start.sh                # Launch script (Flask + Streamlit)
└── outputs/
    ├── <ProductName>/
    │   ├── index.html          # Built product (CTO)
    │   ├── *_requirements.json
    │   └── *_briefings.json
    ├── cold_email.md
    ├── devto_article.md
    ├── discord_post.md
    ├── reddit_post.md
    ├── execution_plan.md
    ├── risk_register.md
    ├── investor_pitch.md
    ├── executive_summary.md
    ├── memory_store.json
    └── episode_log.json
```

---

## Outputs

| Agent | Output Files |
|---|---|
| CTO | `outputs/<ProductName>/index.html` — working HTML product |
| CMO | `cold_email.md`, `discord_post.md`, `reddit_post.md`, `devto_article.md` |
| COO | `execution_plan.md`, `risk_register.md` |
| CEO | `investor_pitch.md`, `executive_summary.md` |

---

## Deep Dive

See [BLOG.md](BLOG.md) for a full technical writeup covering the reward system, conflict detection architecture, memory design, and string-patching approach.
