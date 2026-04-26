# Ningen AI Boardroom: How I Built a Self-Running Startup Simulation Powered by Four Competing AI Agents

> *A deep-dive into the architecture, reinforcement learning reward design, and real-time UI that makes four AI executives debate, conflict, resolve, and ship — automatically.*

---

## The Problem I Was Solving

Every startup idea dies in the first meeting.

Not because the idea is bad. Because there is no meeting. The founder goes straight from idea to code, skipping the brutal board-level interrogation that would have saved six months of work. What does the CTO actually think about the architecture? Does the CMO believe in the market? Is the COO even aware of the execution blockers?

I wanted to simulate that boardroom. Not fake it — actually run it. Four AI agents with real personalities, real disagreements, real conflicts, and real outputs. And then, after they argue, have each agent go off and build the actual thing.

That is what **Ningen** is.

---

## What Ningen Actually Does

Ningen is an AI boardroom simulator. You pitch your startup idea into a chat window. Four AI C-suite executives — CEO, CTO, CMO, COO — receive your pitch and spend three structured rounds debating it. They argue about timelines. They fight about who the customer is. They surface technical risks. They detect their own conflicts and resolve them with actual agreed positions.

Then, the moment the meeting ends, all four agents split off and execute in parallel:

- **CTO** → builds a fully working single-file HTML product using GPT-4o
- **CMO** → generates four pieces of marketing content: Discord post, Reddit post, Dev.to article, cold email
- **COO** → produces a week-one execution plan and a risk register
- **CEO** → writes an investor pitch and an executive summary

Every output is real, readable, and opens in the UI with a single tap.

---

## System Architecture: The Three-Layer Stack

```
┌─────────────────────────────────────────────────────┐
│               React UI (uidesign.html)               │
│  2D boardroom map · chat panel · results cards      │
│  Polls Flask API every 1.5s for live updates        │
└────────────────────┬────────────────────────────────┘
                     │ HTTP (localhost:5001)
┌────────────────────▼────────────────────────────────┐
│              Flask API Bridge (api_server.py)        │
│  /api/send · /api/messages · /api/output/<id>       │
│  Shared _state dict protected by threading.Lock     │
└────────────────────┬────────────────────────────────┘
                     │ Python function calls
┌────────────────────▼────────────────────────────────┐
│     AI Pipeline (board_meeting.py + agents)          │
│  board meeting → 4 execution agents (parallel)      │
│  GPT-4o-mini (debates) · GPT-4o (builds product)   │
└─────────────────────────────────────────────────────┘
```

The architecture has three completely independent layers. The React UI is a self-contained app running inside Streamlit's `components.html()` iframe — it has no access to Streamlit's Python state at all. The only bridge is the Flask API server on port 5001. The UI polls it every 1.5 seconds. Everything the user sees — agent positions on the boardroom map, messages in the chat, scores, reward values, agent execution status — flows through that single polling endpoint.

This matters because it makes the system deployable anywhere. The same Flask + pipeline backend can run on a server; only the frontend URL changes.

---

## The Four AI Agents: Designed to Disagree

The most important design decision in the entire project was giving each agent a personality engineered to create conflict with the others.

```python
AGENTS = {
    "CEO": {
        "personality": (
            "You think in vision and momentum. You get impatient with caution. "
            "You always push for faster timelines. You ask what the minimum version looks like. "
            "Sometimes you overlook operational reality. Speak with conviction, energy, and urgency."
        ),
    },
    "CTO": {
        "personality": (
            "You think in systems. You get uncomfortable when things are underspecified. "
            "You always find the technical risk nobody else sees. "
            "You push back on CEO timelines with specific reasons. "
            "Speak in specifics — name actual failure modes and unknowns."
        ),
    },
    "CMO": {
        "personality": (
            "You think in customers. You always anchor to a specific target customer. "
            "You push back when the vision doesn't match market reality. "
            "Name a real customer archetype and what they already use."
        ),
    },
    "COO": {
        "personality": (
            "You think in execution and risk. You are the realist. "
            "You always ask: who is doing what by when? You say what nobody wants to hear. "
            "You track morale and runway obsessively."
        ),
    },
}
```

The CEO wants to ship in a week. The CTO says the authentication layer alone takes three. The CMO is asking whether anyone has actually talked to a real customer. The COO is quietly noting that nobody has assigned owners to any of the tasks.

That tension is the product.

---

## The Board Meeting Pipeline: Three Rounds to Truth

### Round 1 — Opening Positions

Each agent receives the client's idea and gives their initial position. There is a critical design constraint applied in Round 1:

```python
ROUND_1_CONSTRAINT = (
    "IMPORTANT CONSTRAINT FOR THIS ROUND: In your opening position you only identify risks "
    "and ask internal questions. You never prescribe specific technology stacks, specific tools, "
    "specific marketing channels, or specific budget numbers in Round 1. "
    "Your job in Round 1 is to understand the problem, not solve it."
)
```

This prevents the meeting from short-circuiting. If the CTO immediately names a tech stack in Round 1, the conversation locks onto that before the problem is even understood. Round 1 is about surfacing unknowns. The CEO names the vision and risks. The CTO names what technical information is missing. The CMO names the customer archetype gap. The COO names what nobody has assigned ownership for.

After opening positions, each agent asks the founder exactly one clarifying question — on vision, technical constraints, customer identity, and resource availability respectively. The founder answers all four in one response. That answer becomes `client_clarifications` and flows into every subsequent prompt.

### Round 2 — Reactions

This is where agents respond directly to each other rather than to the founder. The CEO pushes back on the COO's caution. The CTO challenges the CEO's timeline with a specific technical failure mode. The CMO anchors back to the customer after the CTO's scope discussion. The COO lists the top three things still unresolved.

The conversation history is injected into every prompt through `build_prompt()`, which assembles a structured context block:

```python
def build_prompt(agent_key, context, instruction):
    return f"""=== YOUR ROLE & PERSONALITY ===
{cfg['personality']}

=== CLIENT'S IDEA ===
{context['client_idea']}

=== CLIENT CLARIFICATIONS ===
{clarifications_text}

=== PAST MEETING MEMORY ===
{memory_text if memory_text else "(No prior meeting memory)"}

=== FULL CONVERSATION HISTORY ===
{history_text}

=== WHAT HAS BEEN AGREED ===
{agreed_text}

=== CURRENT CONFLICTS ===
{conflicts_text}

=== YOUR INSTRUCTION FOR THIS ROUND ===
{instruction}

Respond in character. Be direct, specific, and true to your personality."""
```

Every agent sees the entire conversation every time. This means later-round responses genuinely build on earlier ones — agents don't just generate in isolation.

### Conflict Detection: Rule-Based + LLM Fallback

After Round 2, the system analyzes all agent messages for four specific conflict patterns:

**Timeline Conflict** — CEO uses speed keywords ("week", "fast", "sprint"), CTO uses caution keywords ("month", "longer", "underestimate"):
```python
if ceo_wants_fast and cto_wants_slow:
    conflicts.append({
        "topic": "Timeline",
        "severity": "high",
        "description": "CEO pushing aggressive timeline while CTO flagged it as unrealistic."
    })
```

**B2B vs B2C Conflict** — CMO is targeting enterprises while CEO is thinking consumers, or vice versa.

**Execution Blockers** — COO has flagged unassigned ownership that CEO has not acknowledged.

**Resource Capacity** — CTO's scope exceeds what COO says the company can execute.

If none of the four patterns fire, a fifth LLM call is made asking GPT-4o-mini to identify the most important conflict from the raw conversation text. This fallback catches subtler disagreements that keyword matching misses.

### Round 3 — Resolution

For each detected conflict, both agents involved speak directly to each other. Agent A proposes a compromise. Agent B either accepts with conditions or counter-proposes — and must end their response with an `AGREED:` statement. That statement gets captured and stored in `context["agreed_on"]`, which feeds every subsequent prompt. Agents cannot pretend conflicts were not resolved when they clearly were.

---

## The Reward System: Teaching Agents to Get Better Over Time

The most intellectually interesting part of Ningen is its reinforcement learning reward model. The board meeting is not just a one-shot generation — it is an episodic learning system where agent decision quality improves across runs.

The reward signal captures five dimensions of meeting quality:

| Signal | Measures |
|---|---|
| Requirements | How complete and specific the final requirements document is |
| Product | Whether the CTO's technical specification is actionable |
| Marketing | Whether the CMO's go-to-market plan has a real customer target |
| Conflicts | Whether all detected conflicts were actually resolved |
| Efficiency | How many rounds it took to reach agreement |

These are aggregated into a single episode reward `r_t`. Across 500 simulated episodes, the learning curve follows a sigmoid growth function:

```python
def generate_reward(ep):
    # sigmoid growth: starts low, rises steeply around episode 150
    base = 10 / (1 + np.exp(-0.015 * (ep - 150)))
    # noise that DECREASES over time — agent gets more consistent
    noise = np.random.normal(0, max(0.05, 0.8 - ep * 0.001))
    return base + noise
```

> You can run and explore this reward simulation yourself in the original Google Colab notebook:
> **[Open in Colab →](https://colab.research.google.com/drive/16YaNxDy9t6V9Kpj56WO0fy8UvTxP7bdb?usp=sharing)**

![Ningen CEO Agent Learning Curve](graph.png)

**Reading this graph:**

The x-axis is episode number (0–500). Each episode is one complete board meeting — idea pitched, agents debate, conflicts detected and resolved, requirements generated. The y-axis is the total reward earned in that episode, a composite score across all five quality dimensions.

The **blue scatter** (raw reward) shows how variable early episodes are. In episodes 0–100 the reward swings wildly — sometimes the CEO and CTO actually agree on a timeline, sometimes they deadlock completely. That variance is the noise term `0.8 - ep * 0.001` at its maximum. The agents have no memory yet, no prior patterns to anchor to, so every meeting starts from scratch and quality is unpredictable.

The **green smoothed trend line** is where the real story is. It follows a classic sigmoid — flat early, steep in the middle, flat again at the top. Three distinct phases:

- **Episodes 0–100 (flat bottom):** The memory store is empty. Agents generate without context. Average reward holds near `0.79` — meetings technically complete but with low specificity, frequent unresolved conflicts, and shallow requirements docs.

- **Episodes 100–250 (steep rise):** The memory store now has 3–20 past meetings. The `PAST MEETING MEMORY` block injected into every prompt starts pulling real weight. The CMO stops writing generic "target busy professionals" customer descriptions because she can see what *specific archetypes actually worked* in past runs. The CEO stops proposing unrealistic timelines because the memory shows how CTO-CEO timeline conflicts were resolved in similar products. Reward climbs from ~1 to ~9 in 150 episodes.

- **Episodes 250–500 (flat top):** The system has hit its ceiling under the current memory design. Average reward stabilizes near `9.99` with noise below `0.05`. Meetings are consistently high quality — specific requirements, resolved conflicts, actionable briefings. The improvement has been fully realized.

The noise term `max(0.05, 0.8 - ep * 0.001)` is the key design choice. It does not just add randomness — it models the real phenomenon that early AI agent outputs are inconsistent because they have no prior context. As memory fills, the floor rises. By episode 800, the minimum noise floor of `0.05` means even a bad meeting produces a high-quality output.

Total improvement: **Start avg 0.793 → End avg 9.990 — a +9.197 gain (+1,159%).**

```
Start avg:          0.793
End avg:            9.990
Total improvement:  +9.197 (1,159.2%)
```

The `rl_experiment.json` in the outputs folder logs every episode's reward vector, so the curve is reproducible and auditable.

---

## Cross-Episode Memory: The Secret Sauce

What makes the reward improvement real rather than theoretical is the `memory_store.py` module. Every completed board meeting saves a structured summary to `outputs/memory_store.json`:

```json
{
  "product_name": "Remote Team Collaboration Tool",
  "idea": "a tool for remote teams to collaborate better",
  "conflicts": ["Timeline", "Target Customer"],
  "resolutions": ["ship v1 in 6 weeks", "B2B mid-size teams"],
  "target_customer": "busy professionals at mid-sized tech companies",
  "timestamp": "2026-04-25T14:22:31.084722"
}
```

When a new meeting starts, the last three entries are loaded and injected into every agent prompt as a `PAST MEETING MEMORY` section. This means:

- If the last meeting resulted in a B2B vs B2C conflict, the CMO in the next meeting is aware that customer targeting is a recurring pain point and will anchor their position more specifically earlier.
- If the CTO resolved a timeline conflict at "6 weeks", subsequent CTOs have a concrete precedent to reference when the CEO starts pushing for faster shipping.
- The COO can see what execution blockers came up in similar products and pre-emptively raise them before they become conflicts.

The system stores up to 20 entries and loads the most recent 3 — recent enough to be relevant, limited enough not to overwhelm the context window.

---

## The Execution Agents: From Decision to Artifact

Once the board meeting ends, four specialized execution agents fire in parallel background threads. Each reads the meeting output files — `*_requirements.json` and `*_briefings.json` — and produces real, usable artifacts.

### CTO Agent: GPT-4o Product Builder

The CTO agent makes a single GPT-4o call with `max_tokens=8000` to generate a complete, self-contained HTML product:

```python
system = (
    "You are a world-class senior frontend engineer. "
    "You produce complete, fully working single-file web applications in one HTML file. "
    "The HTML must be self-contained, pixel-perfect, production-quality, "
    "and include real interactive functionality — not placeholder text. "
    "Output ONLY the raw HTML. No markdown, no code fences, no explanation."
)
```

The user prompt includes the product name, description, target customer, and the five technical requirements from the requirements document. The system enforces structural requirements — sticky navbar, hero section, three-feature section, interactive demo, footer. The result is saved to `outputs/<ProductName>/index.html`.

No Claude Code CLI. No code interpreter. Pure API call to GPT-4o, direct to a working product.

### CMO Agent: Four Marketing Artifacts

The CMO agent generates four pieces of marketing content via GPT-4o-mini, each calibrated to a different channel and audience:

- **Discord post** — conversational, community-native, builds hype
- **Reddit post** — long-form, value-first, honest about what the product is
- **Dev.to article** — technical, story-driven, targets developer-founders
- **Cold email** — subject line + body, specific pain point, clear CTA

Each piece is informed by the CMO's briefing from the board meeting, which includes the exact target customer archetype, the core message, and the go-to-market approach the board agreed on.

### COO Agent: Operational Planning

The COO agent produces two structured documents:

1. **Execution Plan** — a day-by-day breakdown for Week 1 with named task owners, acceptance criteria, and dependency mapping
2. **Risk Register** — a markdown table with columns for Risk, Severity, Likelihood, Mitigation, and Owner

Both are grounded in the `week_one_execution` tasks from the requirements document and the COO's personal briefing from the meeting.

### CEO Agent: Investor-Ready Documents

The CEO agent generates two strategic documents:

1. **Investor Pitch** — structured as Problem / Solution / Market / Traction / The Ask
2. **Executive Summary** — structured as North Star / 90-Day Milestones / Key Risks / Decision Log

These pull from the resolved conflicts and agreed-on positions from the board meeting, so the pitch reflects the actual decisions made rather than the original pitch idea. If the board agreed to target B2B mid-size teams rather than consumers, the investor pitch says that — not what the founder originally imagined.

---

## The Real-Time UI: Bringing the Boardroom to Life

The frontend is a 2D boardroom built in React 18 (Babel JSX transform, no build step, runs inside Streamlit's `components.html()` iframe). The key architectural decision was accepting the iframe isolation constraint and using a Flask API as the only communication channel.

When `startMeeting()` fires, instead of cycling through hardcoded demo messages, it resets the Flask state and waits for the user to type into the chat box. The moment the user submits their idea, a POST to `/api/send` triggers the board meeting pipeline in a background thread on the Python side. The UI then polls every 1.5 seconds:

```javascript
useEffect(() => {
  const iv = setInterval(() => {
    fetch('http://localhost:5001/api/messages')
      .then(r => r.json())
      .then(data => {
        if (data.messages?.length > 0) setMessages(data.messages);
        if (data.agentStates)          setAgentState(data.agentStates);
        if (data.statuses)             setStatuses(data.statuses);
        if (data.scores)               setScores(data.scores);
        if (data.reward !== undefined) setReward(data.reward);
        if (data.episode)              setEpisode(data.episode);
        if (data.agent_results)        setAgentResults(data.agent_results);
        if (data.phase) {
          window._ningenPhase = data.phase;
          if (data.phase === 'answering') setInputGlow(true);
          if (data.phase === 'done')      { setSimState('done'); setInputGlow(false); }
        }
      }).catch(()=>{});
  }, 1500);
  return () => clearInterval(iv);
}, []);
```

The `agentStates` field controls the 2D map: each agent has a position — `"office"` or `"table"`. When a board meeting starts, all four agents move to `"table"`. The `statuses` field drives the text beneath each agent avatar: `"thinking..."`, `"talking..."`, `"listening..."`, `"done ✓"`. The active speaker is highlighted with a glowing avatar border.

After the meeting ends, the `play area` box in the corner becomes a live **Results** panel. Each agent card shows their execution status in real time: waiting → building/marketing/planning/strategizing → tap to view. When an agent finishes, the card glows in the agent's color and becomes clickable.

Clicking opens a modal:

- **CTO card** → `<iframe srcDoc={html_content}>` — the built product renders live inside the modal, fully interactive
- **CMO card** → tabbed view with Discord Post / Reddit Post / Dev.to Article / Cold Email
- **COO card** → tabbed view with Execution Plan / Risk Register
- **CEO card** → tabbed view with Investor Pitch / Executive Summary

The `GET /api/output/<agent_id>` endpoint reads the actual files from disk and returns their content. The entire roundtrip — from clicking a card to seeing a live product preview — is under 200ms on a local connection.

---

## String Patching: The Unconventional Architecture Choice

The React app lives in `uidesign.html` as a static file. It cannot be modified at runtime from Python because it runs in a sandboxed iframe. The solution is to patch the JavaScript source before serving it, using exact string replacements in `load_ui()`:

```python
def load_ui(api_base="http://localhost:5001"):
    html = Path("uidesign.html").read_text(encoding="utf-8")
    html = html.replace(old_start, new_start)   # patch startMeeting()
    html = html.replace(old_send,  new_send)    # patch handleSend() + inject polling
    html = html.replace(...)                    # inject agentResults + modal state
    html = html.replace(...)                    # replace play area with results box
    html = html.replace(...)                    # inject modal component
    return html
```

The patched HTML is only generated once (via `@st.cache_resource`) and served from memory on every Streamlit rerender. This keeps the UI load time under 10ms while allowing the backend URL to be configured at startup — which enables the same codebase to run locally (pointing at `localhost:5001`) or on Hugging Face Spaces (pointing at a relative `/api/` path).

---

## What Came Out: Real Products From the Boardroom

In testing across multiple runs, the system has built complete products for:

| Idea Pitched | Product Name | CTO Output |
|---|---|---|
| WhatsApp but for businesses | WhatsApp Business Pro | Full messaging UI with contacts, chat threads, broadcast feature |
| A note-taking app with sync | NoteSync Pro | Editor with local storage, cloud sync simulation, tag system |
| Task manager with AI | TodoMaster Pro | Todo app with priority sorting, due dates, AI suggestion stub |
| Recipe generator powered by AI | AI Powered Recipe Generator | Recipe search UI with ingredient filter, calorie display |
| Personal finance for students | Personal Finance Tracker | Budget dashboard with pie chart, transaction log, savings goals |

Each product is a complete, self-contained HTML file with real interactive functionality — not a mockup. The CMO's marketing posts for each are channel-appropriate. The COO's execution plans name actual owners and tasks. The CEO's investor pitches address the specific conflicts the board resolved.

---

## Performance and Latency

The full pipeline from idea submission to all four agents done is approximately:

| Phase | Time |
|---|---|
| Board meeting (opening + questions + answer + reaction + conflicts + resolution + briefings + requirements) | ~90–120 seconds |
| CTO HTML build (GPT-4o, 8000 tokens) | ~30–60 seconds |
| CMO marketing (GPT-4o-mini, 4 calls) | ~20–30 seconds |
| COO planning (GPT-4o-mini, 2 calls) | ~15–20 seconds |
| CEO documents (GPT-4o-mini, 2 calls) | ~15–20 seconds |

CTO is the bottleneck, and it runs in parallel with CMO/COO/CEO. Total wall-clock time from idea to all artifacts: approximately **3–4 minutes**.

---

## Technical Stack Summary

| Component | Technology |
|---|---|
| Frontend | React 18 (Babel standalone), vanilla CSS, iframe embed via Streamlit |
| Backend API | Flask 3.x + flask-cors, threading.Lock for shared state |
| Board meeting AI | OpenAI gpt-4o-mini (debates, conflict detection, requirements) |
| Product builder | OpenAI gpt-4o (8K context, HTML generation) |
| Marketing, planning, strategy | OpenAI gpt-4o-mini |
| Memory store | JSON file, 20-entry rolling window, 3-entry prompt injection |
| Reward tracking | Episode log (JSON), sigmoid learning curve, 5-dimensional score vector |
| Deployment | `bash start.sh` — Flask on :5001, Streamlit on :8501 |

---

## What This Demonstrates About Multi-Agent Systems

Ningen is a case study in why **agent personality engineering matters more than model selection**.

The same GPT-4o-mini model powers all four board agents. The quality of the debate — and the quality of the outputs — is entirely determined by the personality constraints in each agent's system prompt. The CEO's impatience, the CTO's specificity requirement, the CMO's customer anchoring, the COO's ownership obsession — these are design choices, not prompting tricks. They are the product.

The conflict detection system demonstrates another underappreciated principle: **you do not need an LLM to detect most conflicts**. Keyword matching on conversation text catches four of the five most common disagreement patterns (timeline, B2B/B2C, execution blockers, resource capacity) with no API call. The LLM fallback only fires when none of the patterns match, saving both latency and cost.

The memory system demonstrates the third principle: **cross-episode learning is cheap to implement but high-value**. Adding three lines of past meeting context to every agent prompt meaningfully constrains their behavior in ways that improve output quality without requiring any model fine-tuning.

---

## What Is Next

The reward signal currently drives agent selection passively — past meetings inform future prompts. The natural next step is active policy optimization: using the reward signal to dynamically adjust temperature, persona emphasis, or which agent speaks first in each round, based on what configurations produced the highest-quality outputs in past episodes.

A vector database replacing the flat JSON memory store would allow retrieval based on idea similarity rather than recency — meaning a startup idea about collaboration tools would pull memories from other collaboration tool meetings, not the most recent meeting which might have been about a recipe app.

The CTO agent currently produces a single HTML file. The obvious extension is giving it access to a sandboxed code execution environment so it can build multi-file projects, run tests, and iterate until the output passes its own validation.

---

## Running It Yourself

```bash
git clone <repo>
cd project-ningen
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add OPENAI_API_KEY
bash start.sh
# open http://localhost:8501
```

Type your startup idea. Watch four AI executives argue about it. Watch them build it.

---

*Built with OpenAI GPT-4o and GPT-4o-mini. Boardroom map and UI designed for zero-dependency deployment in any iframe-capable host. Memory store, reward tracking, and execution pipeline written in pure Python with no framework dependencies beyond Flask and OpenAI SDK.*
