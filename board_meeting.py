#!/usr/bin/env python3
"""
Board Meeting System
Simulates a board meeting with CEO, CTO, CMO, COO agents using OpenAI gpt-4o-mini.
The client pitches their idea; agents deliberate across three rounds and produce personal briefings.
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ─── ANSI Colors ───────────────────────────────────────────────────────────────
RESET        = "\033[0m"
BOLD         = "\033[1m"
CEO_COLOR    = "\033[33m"    # amber
CTO_COLOR    = "\033[34m"    # blue
CMO_COLOR    = "\033[31m"    # coral/red
COO_COLOR    = "\033[32m"    # green
CONFLICT_COLOR = "\033[1;31m"  # red bold
AGREE_COLOR    = "\033[1;32m"  # green bold
HEADER_COLOR   = "\033[1;37m"  # white bold
DIM          = "\033[2m"

# ─── Agent Configs ─────────────────────────────────────────────────────────────
ROUND_1_CONSTRAINT = (
    "IMPORTANT CONSTRAINT FOR THIS ROUND: In your opening position you only identify risks "
    "and ask internal questions. You never prescribe specific technology stacks, specific tools, "
    "specific marketing channels, or specific budget numbers in Round 1. "
    "Your job in Round 1 is to understand the problem, not solve it."
)

AGENTS = {
    "CEO": {
        "color": CEO_COLOR,
        "role": "Chief Executive Officer",
        "personality": (
            "You are the CEO. You think in vision and momentum. You get impatient with caution. "
            "You always push for faster timelines. You ask what the minimum version looks like. "
            "Sometimes you overlook operational reality. You speak with conviction, energy, and urgency. "
            "Keep responses to 3-5 focused sentences."
        ),
    },
    "CTO": {
        "color": CTO_COLOR,
        "role": "Chief Technology Officer",
        "personality": (
            "You are the CTO. You think in systems. You get uncomfortable when things are underspecified. "
            "You always find the technical risk nobody else sees. You push back on CEO timelines with specific reasons. "
            "You speak in specifics, not generalities — name actual failure modes and unknowns. "
            "Keep responses to 3-5 focused sentences."
        ),
    },
    "CMO": {
        "color": CMO_COLOR,
        "role": "Chief Marketing Officer",
        "personality": (
            "You are the CMO. You think in customers. You always anchor to a specific target customer. "
            "You push back when the vision doesn't match market reality. "
            "You always ask: who specifically is this for, and why would they pay for it right now? "
            "Name a real customer archetype and what they already use. Keep responses to 3-5 focused sentences."
        ),
    },
    "COO": {
        "color": COO_COLOR,
        "role": "Chief Operating Officer",
        "personality": (
            "You are the COO. You think in execution and risk. You are the realist. "
            "You always ask: who is doing what by when? You say what nobody wants to hear. "
            "You track morale and runway obsessively. You flag blockers before they become crises. "
            "Keep responses to 3-5 focused sentences."
        ),
    },
}

# ─── OpenAI Client ─────────────────────────────────────────────────────────────
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")
    return OpenAI(api_key=api_key)

OAI_CLIENT = get_openai_client()

# ─── Helpers ───────────────────────────────────────────────────────────────────
def separator(char="─", width=70, color=DIM):
    print(f"{color}{char * width}{RESET}")

def print_header(title):
    separator("═", 70, HEADER_COLOR)
    print(f"{HEADER_COLOR}  {title}{RESET}")
    separator("═", 70, HEADER_COLOR)
    print()

def print_agent_message(agent_key, message, msg_type=""):
    cfg = AGENTS[agent_key]
    color = cfg["color"]
    role = cfg["role"]
    tag = f" [{msg_type.upper()}]" if msg_type else ""
    print(f"\n{color}{BOLD}▌ {agent_key} — {role}{tag}{RESET}")
    separator("─", 60, color)
    for line in message.strip().split("\n"):
        print(f"{color}{line}{RESET}")
    separator("─", 60, color)

def format_conversation_history(conversation):
    """Format conversation list as plain readable text."""
    if not conversation:
        return "(No prior conversation)"
    lines = []
    for entry in conversation:
        speaker = entry.get("speaker", "?")
        msg = entry.get("message", "")
        msg_type = entry.get("type", "")
        lines.append(f"[{speaker} - {msg_type}]: {msg}")
    return "\n\n".join(lines)

def format_agreed(agreed_on):
    if not agreed_on:
        return "(Nothing agreed yet)"
    return "\n".join(f"• {a}" for a in agreed_on)

def format_conflicts(conflicts):
    if not conflicts:
        return "(No conflicts identified yet)"
    lines = []
    for c in conflicts:
        lines.append(
            f"• [{c['severity'].upper()}] {c['topic']} — {c['description']} "
            f"(Agents: {', '.join(c['agents_involved'])})"
        )
    return "\n".join(lines)

def format_clarifications(clarifications):
    if not clarifications:
        return "(No client clarifications yet)"
    return clarifications

# ─── LLM Call with Retry ───────────────────────────────────────────────────────
FALLBACK_RESPONSES = {
    "CEO": "We need to move fast and capture the market. Let's understand what the minimum version looks like before we decide on timelines.",
    "CTO": "The architecture needs more specification before I can assess risk. What systems already exist that we need to integrate with?",
    "CMO": "We need to understand who the client thinks their customer is before we can validate market fit.",
    "COO": "Nobody has assigned owners or deadlines yet. We need to know resources and timeline before we can plan execution.",
}

def call_llm(prompt: str, agent_key: str, fallback: str = None, max_tokens: int = 400) -> str:
    """Call OpenAI API with one retry and a hardcoded fallback."""
    for attempt in range(2):
        try:
            response = OAI_CLIENT.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt == 0:
                print(f"{DIM}  [Retry {agent_key}: {e}]{RESET}")
                time.sleep(2)
            else:
                fb = fallback or FALLBACK_RESPONSES.get(agent_key, "I need more information before responding.")
                print(f"{DIM}  [Fallback used for {agent_key}]{RESET}")
                return fb

# ─── Prompt Builder ────────────────────────────────────────────────────────────
def build_prompt(agent_key: str, context: dict, instruction: str) -> str:
    cfg = AGENTS[agent_key]
    history_text = format_conversation_history(context["conversation"])
    agreed_text = format_agreed(context["agreed_on"])
    conflicts_text = format_conflicts(context["conflicts"])
    clarifications_text = format_clarifications(context.get("client_clarifications", ""))

    prompt = f"""=== YOUR ROLE & PERSONALITY ===
{cfg['personality']}

=== CLIENT'S IDEA ===
{context['client_idea']}

=== CLIENT CLARIFICATIONS ===
{clarifications_text}

=== FULL CONVERSATION HISTORY ===
{history_text}

=== WHAT HAS BEEN AGREED ===
{agreed_text}

=== CURRENT CONFLICTS ===
{conflicts_text}

=== YOUR INSTRUCTION FOR THIS ROUND ===
{instruction}

Respond in character. Be direct, specific, and true to your personality."""
    return prompt

# ─── Round 1: Opening Positions ────────────────────────────────────────────────
def run_round_1(context: dict):
    print_header("ROUND 1 — OPENING POSITIONS")

    clarifications_text = format_clarifications(context.get("client_clarifications", ""))

    # CEO
    instruction = (
        "Read the client's idea carefully. State your position: what is the vision you see here, "
        "what risks concern you about the vision, and what internal questions do you have before committing? "
        "Be bold but remember: understand the problem first.\n\n"
        + ROUND_1_CONSTRAINT
    )
    prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CEO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== YOUR INSTRUCTION ===\n{instruction}"
    )
    msg = call_llm(prompt, "CEO")
    context["ceo_position"] = msg
    context["conversation"].append({
        "speaker": "CEO", "message": msg,
        "type": "opening", "responding_to": "client_idea"
    })
    print_agent_message("CEO", msg, "opening")

    # CTO
    instruction = (
        "Read the client's idea and the CEO's position. Identify the most critical technical risk "
        "nobody else has mentioned yet. Ask the internal questions you need answered before you can assess feasibility.\n\n"
        + ROUND_1_CONSTRAINT
    )
    prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CTO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== CEO POSITION ===\n{context['ceo_position']}\n\n"
        f"=== YOUR INSTRUCTION ===\n{instruction}"
    )
    msg = call_llm(prompt, "CTO")
    context["cto_position"] = msg
    context["conversation"].append({
        "speaker": "CTO", "message": msg,
        "type": "opening", "responding_to": "ceo_position"
    })
    print_agent_message("CTO", msg, "opening")

    # CMO
    instruction = (
        "Read the client's idea and what the CEO and CTO said. "
        "Identify the market risks and customer unknowns. Ask the internal questions you need answered "
        "before you can validate whether this idea has a real market.\n\n"
        + ROUND_1_CONSTRAINT
    )
    prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CMO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== CEO POSITION ===\n{context['ceo_position']}\n\n"
        f"=== CTO POSITION ===\n{context['cto_position']}\n\n"
        f"=== YOUR INSTRUCTION ===\n{instruction}"
    )
    msg = call_llm(prompt, "CMO")
    context["cmo_position"] = msg
    context["conversation"].append({
        "speaker": "CMO", "message": msg,
        "type": "opening", "responding_to": "cto_position"
    })
    print_agent_message("CMO", msg, "opening")

    # COO
    instruction = (
        "Read everything above. What is the single biggest execution risk right now? "
        "Who should own what? What can go wrong that nobody is talking about? "
        "Ask the internal questions you need answered before you can plan execution.\n\n"
        + ROUND_1_CONSTRAINT
    )
    msg = call_llm(build_prompt("COO", context, instruction), "COO")
    context["coo_position"] = msg
    context["conversation"].append({
        "speaker": "COO", "message": msg,
        "type": "opening", "responding_to": "all_positions"
    })
    print_agent_message("COO", msg, "opening")

# ─── Client Questions Round ─────────────────────────────────────────────────────
def run_client_questions(context: dict):
    print_header("CLIENT QUESTIONS ROUND")
    print(f"{DIM}Each agent has one clarifying question for the client.{RESET}\n")

    clarifications_text = format_clarifications(context.get("client_clarifications", ""))
    history_text = format_conversation_history(context["conversation"])

    questions = {}

    # CEO question — vision and success definition
    ceo_q_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CEO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== CONVERSATION SO FAR ===\n{history_text}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Generate exactly ONE clarifying question for the client. "
        "Your question must be about vision and success definition: "
        "What does success look like to them in 90 days, and how will they know the product has won? "
        "Ask only one focused, specific question. No preamble."
    )
    ceo_q = call_llm(ceo_q_prompt, "CEO", max_tokens=100)
    questions["CEO"] = ceo_q

    # CTO question — technical constraints or existing systems
    cto_q_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CTO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== CONVERSATION SO FAR ===\n{history_text}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Generate exactly ONE clarifying question for the client. "
        "Your question must be about technical constraints or existing systems: "
        "What technical infrastructure already exists, and what hard technical constraints must we work within? "
        "Ask only one focused, specific question. No preamble."
    )
    cto_q = call_llm(cto_q_prompt, "CTO", max_tokens=100)
    questions["CTO"] = cto_q

    # CMO question — who the client thinks their customer is
    cmo_q_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CMO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== CONVERSATION SO FAR ===\n{history_text}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Generate exactly ONE clarifying question for the client. "
        "Your question must be about who the client thinks their customer is: "
        "Who specifically is the first customer, and why would that person pay for this today? "
        "Ask only one focused, specific question. No preamble."
    )
    cmo_q = call_llm(cmo_q_prompt, "CMO", max_tokens=100)
    questions["CMO"] = cmo_q

    # COO question — timeline expectations and resources available
    coo_q_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['COO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications_text}\n\n"
        f"=== CONVERSATION SO FAR ===\n{history_text}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Generate exactly ONE clarifying question for the client. "
        "Your question must be about timeline expectations and resources available: "
        "What is the hard deadline if any, and what budget and headcount is currently available to execute? "
        "Ask only one focused, specific question. No preamble."
    )
    coo_q = call_llm(coo_q_prompt, "COO", max_tokens=100)
    questions["COO"] = coo_q

    # Print all four questions
    for agent_key, question in questions.items():
        color = AGENTS[agent_key]["color"]
        role = AGENTS[agent_key]["role"]
        print(f"\n{color}{BOLD}▌ {agent_key} — {role} [QUESTION FOR CLIENT]{RESET}")
        separator("─", 60, color)
        print(f"{color}{question}{RESET}")
        separator("─", 60, color)

    # Client answers all four in one response
    print(f"\n{HEADER_COLOR}{BOLD}━━━ YOUR TURN, CLIENT ━━━{RESET}")
    print(f"{DIM}Answer all four questions above in one response. Take your time.{RESET}\n")
    client_answer = input(f"{BOLD}> {RESET}").strip()
    if not client_answer:
        client_answer = "(Client provided no additional clarifications)"

    # Store in context
    context["client_clarifications"] = (
        f"CEO asked: {questions['CEO']}\n"
        f"CTO asked: {questions['CTO']}\n"
        f"CMO asked: {questions['CMO']}\n"
        f"COO asked: {questions['COO']}\n\n"
        f"Client's answer: {client_answer}"
    )

    context["conversation"].append({
        "speaker": "CLIENT",
        "message": context["client_clarifications"],
        "type": "clarification",
        "responding_to": "agent_questions"
    })

    print(f"\n{AGREE_COLOR}✓ Clarifications noted. Continuing meeting...{RESET}\n")
    time.sleep(0.5)

# ─── Round 2: Reactions ─────────────────────────────────────────────────────────
def run_round_2(context: dict):
    print_header("ROUND 2 — REACTIONS")

    # CEO reacts to COO
    coo_last = next(
        (e["message"] for e in reversed(context["conversation"]) if e["speaker"] == "COO"), ""
    )
    instruction = (
        f"The COO said: '{coo_last}'\n"
        "React directly to what the COO said. Push back on the caution. "
        "Restate why speed matters more than perfection here. What does the MVP look like in your mind?"
    )
    msg = call_llm(build_prompt("CEO", context, instruction), "CEO")
    context["conversation"].append({
        "speaker": "CEO", "message": msg,
        "type": "reaction", "responding_to": "COO"
    })
    print_agent_message("CEO", msg, "reaction")

    # CTO reacts to CEO timeline with specific technical pushback
    ceo_last = next(
        (e["message"] for e in reversed(context["conversation"]) if e["speaker"] == "CEO"), ""
    )
    instruction = (
        f"The CEO just said: '{ceo_last}'\n"
        "Push back on the proposed timeline with ONE specific technical reason. "
        "Name the exact system, integration, or failure mode that makes the timeline unrealistic. "
        "Propose a concrete alternative."
    )
    msg = call_llm(build_prompt("CTO", context, instruction), "CTO")
    context["conversation"].append({
        "speaker": "CTO", "message": msg,
        "type": "reaction", "responding_to": "CEO"
    })
    print_agent_message("CTO", msg, "reaction")

    # CMO reacts to CTO constraints, anchors to specific customer
    cto_last = next(
        (e["message"] for e in reversed(context["conversation"]) if e["speaker"] == "CTO"), ""
    )
    instruction = (
        f"The CTO said: '{cto_last}'\n"
        "Acknowledge the technical constraints but anchor back to the customer. "
        "Name your target customer archetype. "
        "What does that customer need on Day 1 — and does the CTO's scope cover it?"
    )
    msg = call_llm(build_prompt("CMO", context, instruction), "CMO")
    context["conversation"].append({
        "speaker": "CMO", "message": msg,
        "type": "reaction", "responding_to": "CTO"
    })
    print_agent_message("CMO", msg, "reaction")

    # COO identifies what is still unresolved
    instruction = (
        "Look at the entire conversation so far, including the client's clarifications. "
        "List the top 3 things that are STILL unresolved after this round of reactions. "
        "Be blunt. What will derail us if we don't decide today?"
    )
    msg = call_llm(build_prompt("COO", context, instruction), "COO")
    context["conversation"].append({
        "speaker": "COO", "message": msg,
        "type": "reaction", "responding_to": "all"
    })
    print_agent_message("COO", msg, "reaction")

# ─── Conflict Detection ─────────────────────────────────────────────────────────
def detect_conflicts(context: dict):
    print_header("CONFLICT DETECTION")

    conflicts = []

    ceo_msgs = [e["message"] for e in context["conversation"] if e["speaker"] == "CEO"]
    cto_msgs = [e["message"] for e in context["conversation"] if e["speaker"] == "CTO"]
    cmo_msgs = [e["message"] for e in context["conversation"] if e["speaker"] == "CMO"]
    coo_msgs = [e["message"] for e in context["conversation"] if e["speaker"] == "COO"]

    ceo_text = " ".join(ceo_msgs).lower()
    cto_text = " ".join(cto_msgs).lower()
    cmo_text = " ".join(cmo_msgs).lower()
    coo_text = " ".join(coo_msgs).lower()

    # 1. Timeline conflict
    timeline_keywords_speed = ["week", "days", "fast", "quick", "asap", "immediately", "sprint"]
    timeline_keywords_caution = ["month", "longer", "minimum", "realistic", "underestimate", "complex"]
    ceo_wants_fast = any(k in ceo_text for k in timeline_keywords_speed)
    cto_wants_slow = any(k in cto_text for k in timeline_keywords_caution)
    if ceo_wants_fast and cto_wants_slow:
        conflicts.append({
            "agents_involved": ["CEO", "CTO"],
            "topic": "Timeline",
            "severity": "high",
            "description": "CEO is pushing an aggressive timeline while CTO has flagged it as technically unrealistic."
        })

    # 2. Customer conflict
    b2b_keywords = ["b2b", "enterprise", "business", "company", "team", "manager", "professional"]
    b2c_keywords = ["consumer", "individual", "personal", "user", "people", "anyone", "everyone"]
    cmo_b2b = any(k in cmo_text for k in b2b_keywords)
    ceo_b2c = any(k in ceo_text for k in b2c_keywords)
    cmo_b2c = any(k in cmo_text for k in b2c_keywords)
    ceo_b2b = any(k in ceo_text for k in b2b_keywords)
    if (cmo_b2b and ceo_b2c) or (cmo_b2c and ceo_b2b):
        conflicts.append({
            "agents_involved": ["CEO", "CMO"],
            "topic": "Target Customer",
            "severity": "high",
            "description": "CEO's market vision and CMO's identified customer archetype appear misaligned (B2B vs B2C)."
        })

    # 3. Execution conflict
    blocker_keywords = ["nobody owns", "no owner", "unclear", "unassigned", "missing", "blocker",
                        "nobody", "not assigned", "no one", "who is doing"]
    coo_has_blockers = any(k in coo_text for k in blocker_keywords)
    if coo_has_blockers:
        conflicts.append({
            "agents_involved": ["CEO", "COO"],
            "topic": "Execution Blockers",
            "severity": "medium",
            "description": "COO has identified execution blockers (unassigned ownership, missing resources) that CEO has not addressed."
        })

    # 4. Resource conflict
    resource_keywords = ["runway", "budget", "hire", "headcount", "capacity", "bandwidth", "can't do", "not enough"]
    scope_keywords = ["build", "launch", "ship", "integrate", "develop", "implement", "design"]
    coo_resource_constrained = any(k in coo_text for k in resource_keywords)
    cto_big_scope = any(k in cto_text for k in scope_keywords)
    if coo_resource_constrained and cto_big_scope:
        conflicts.append({
            "agents_involved": ["CTO", "COO"],
            "topic": "Resource Capacity",
            "severity": "medium",
            "description": "CTO's technical scope may exceed the resources and capacity COO says are available."
        })

    # LLM fallback if none detected
    if not conflicts:
        prompt = (
            f"Review this board meeting conversation:\n\n"
            f"{format_conversation_history(context['conversation'])}\n\n"
            "Identify the single most important conflict between the board members. "
            "Return JSON only with keys: agents_involved (list), topic (string), severity (high/medium/low), description (string)."
        )
        try:
            raw = call_llm(prompt, "CEO", fallback=None)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                detected = json.loads(raw[start:end])
                conflicts.append(detected)
        except Exception:
            conflicts.append({
                "agents_involved": ["CEO", "CTO"],
                "topic": "Alignment",
                "severity": "medium",
                "description": "General misalignment between vision and technical feasibility."
            })

    context["conflicts"] = conflicts

    for c in conflicts:
        print(f"\n{CONFLICT_COLOR}⚠ CONFLICT DETECTED: {c['topic']} [{c['severity'].upper()}]{RESET}")
        print(f"{CONFLICT_COLOR}  Agents: {', '.join(c['agents_involved'])}{RESET}")
        print(f"{CONFLICT_COLOR}  {c['description']}{RESET}")
        separator("─", 60, CONFLICT_COLOR)

    return conflicts

# ─── Round 3: Resolution ────────────────────────────────────────────────────────
def run_round_3(context: dict):
    print_header("ROUND 3 — CONFLICT RESOLUTION")

    for conflict in context["conflicts"]:
        agents = conflict["agents_involved"]
        topic = conflict["topic"]

        print(f"\n{BOLD}Resolving: {topic} between {' & '.join(agents)}{RESET}\n")

        agent_a = agents[0]
        agent_b = agents[1]

        instruction_a = (
            f"There is a conflict between you ({agent_a}) and {agent_b} on the topic of: {topic}\n"
            f"Conflict description: {conflict['description']}\n\n"
            "Speak DIRECTLY to the other agent. Propose a specific compromise or resolution. "
            "Be concrete — name numbers, dates, or customer segments. Don't just agree to agree."
        )
        msg_a = call_llm(build_prompt(agent_a, context, instruction_a), agent_a)
        context["conversation"].append({
            "speaker": agent_a, "message": msg_a,
            "type": "resolution", "responding_to": agent_b
        })
        print_agent_message(agent_a, msg_a, "resolution")

        instruction_b = (
            f"There is a conflict between you ({agent_b}) and {agent_a} on the topic of: {topic}\n"
            f"Conflict description: {conflict['description']}\n\n"
            f"{agent_a} just said: '{msg_a}'\n\n"
            "Respond DIRECTLY to their proposal. Either accept with specific conditions, "
            "or counter-propose something concrete. End with a clear agreement statement starting with 'AGREED:'."
        )
        msg_b = call_llm(build_prompt(agent_b, context, instruction_b), agent_b)
        context["conversation"].append({
            "speaker": agent_b, "message": msg_b,
            "type": "resolution", "responding_to": agent_a
        })
        print_agent_message(agent_b, msg_b, "resolution")

        agreement_text = f"{topic}: {agent_a} and {agent_b} resolution — "
        if "AGREED:" in msg_b.upper():
            idx = msg_b.upper().find("AGREED:")
            agreement_text += msg_b[idx:].strip()
        else:
            agreement_text += f"{msg_a[:100]}... resolved with {msg_b[:100]}..."

        context["agreed_on"].append(agreement_text)
        print(f"\n{AGREE_COLOR}✓ AGREEMENT REACHED: {topic}{RESET}")
        print(f"{AGREE_COLOR}  {agreement_text[:200]}...{RESET}")
        separator("─", 60, AGREE_COLOR)

# ─── Final Agent Briefings ──────────────────────────────────────────────────────
def run_final_briefings(context: dict) -> dict:
    print_header("FINAL AGENT BRIEFINGS")
    print(f"{DIM}Each agent produces their personal mission statement for this project.{RESET}\n")

    history = format_conversation_history(context["conversation"])
    agreed = format_agreed(context["agreed_on"])
    clarifications = format_clarifications(context.get("client_clarifications", ""))

    briefings = {}

    # ── CEO Briefing ──────────────────────────────────────────────────────────
    ceo_briefing_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CEO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications}\n\n"
        f"=== FULL MEETING CONVERSATION ===\n{history}\n\n"
        f"=== WHAT WAS AGREED ===\n{agreed}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Produce your personal CEO mission briefing for this project. This is YOUR internal document — "
        "your memory of what was decided and what you must do. Include exactly these four items:\n"
        "1. COMPANY MISSION: One sentence describing what this company does and why it exists.\n"
        "2. NORTH STAR METRIC: The single metric you will obsess over to know if we are winning.\n"
        "3. SUCCESS IN 90 DAYS: What does success look like in 90 days — be specific.\n"
        "4. WEEKLY MONITOR: What will you personally check every week to stay on track.\n\n"
        "Format your response with these exact headers. Be direct and specific."
    )
    ceo_briefing = call_llm(ceo_briefing_prompt, "CEO", max_tokens=500)
    briefings["ceo_briefing"] = ceo_briefing
    print_agent_message("CEO", ceo_briefing, "briefing")

    # ── CTO Briefing ──────────────────────────────────────────────────────────
    cto_briefing_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CTO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications}\n\n"
        f"=== FULL MEETING CONVERSATION ===\n{history}\n\n"
        f"=== WHAT WAS AGREED ===\n{agreed}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Produce your personal CTO mission briefing for this project. This is YOUR internal document. Include exactly:\n"
        "1. TECHNICAL APPROACH: Three bullet points describing the technical approach.\n"
        "2. BIGGEST RISK & MITIGATION: The biggest technical risk and your specific mitigation plan.\n"
        "3. WEEK ONE BUILD: What exactly you are building in week one.\n"
        "4. NEEDS FROM CMO & COO: What you need from CMO and COO to proceed — be specific.\n\n"
        "Format your response with these exact headers. Be direct and specific."
    )
    cto_briefing = call_llm(cto_briefing_prompt, "CTO", max_tokens=500)
    briefings["cto_briefing"] = cto_briefing
    print_agent_message("CTO", cto_briefing, "briefing")

    # ── CMO Briefing ──────────────────────────────────────────────────────────
    cmo_briefing_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CMO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications}\n\n"
        f"=== FULL MEETING CONVERSATION ===\n{history}\n\n"
        f"=== WHAT WAS AGREED ===\n{agreed}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Produce your personal CMO mission briefing for this project. This is YOUR internal document. Include exactly:\n"
        "1. TARGET CUSTOMER: One specific sentence describing the exact target customer — job title, company type, pain point.\n"
        "2. CORE MESSAGE: One sentence that is the core message to that customer.\n"
        "3. GO TO MARKET: Three bullet points describing the go-to-market approach.\n"
        "4. NEEDS FROM CTO: What you need from CTO to start marketing — be specific.\n\n"
        "Format your response with these exact headers. Be direct and specific."
    )
    cmo_briefing = call_llm(cmo_briefing_prompt, "CMO", max_tokens=500)
    briefings["cmo_briefing"] = cmo_briefing
    print_agent_message("CMO", cmo_briefing, "briefing")

    # ── COO Briefing ──────────────────────────────────────────────────────────
    coo_briefing_prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['COO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clarifications}\n\n"
        f"=== FULL MEETING CONVERSATION ===\n{history}\n\n"
        f"=== WHAT WAS AGREED ===\n{agreed}\n\n"
        "=== YOUR INSTRUCTION ===\n"
        "Produce your personal COO mission briefing for this project. This is YOUR internal document. Include exactly:\n"
        "1. WEEK ONE EXECUTION PLAN: A numbered list of tasks with one named owner for each task.\n"
        "2. TOP THREE RISKS: The top three risks to execution, in order of severity.\n"
        "3. DECISIONS NEEDED: What decisions must be made before work starts — list them.\n"
        "4. COMPANY HEALTH: Current company health assessment — morale, runway, capacity.\n\n"
        "Format your response with these exact headers. Be direct and specific."
    )
    coo_briefing = call_llm(coo_briefing_prompt, "COO", max_tokens=500)
    briefings["coo_briefing"] = coo_briefing
    print_agent_message("COO", coo_briefing, "briefing")

    return briefings

# ─── Save Agent Briefings ───────────────────────────────────────────────────────
def save_briefings(briefings: dict, context: dict):
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "agent_briefings.json"

    briefings_doc = {
        "client_idea": context["client_idea"],
        "client_clarifications": context.get("client_clarifications", ""),
        "ceo_briefing": briefings.get("ceo_briefing", ""),
        "cto_briefing": briefings.get("cto_briefing", ""),
        "cmo_briefing": briefings.get("cmo_briefing", ""),
        "coo_briefing": briefings.get("coo_briefing", ""),
    }

    with open(output_path, "w") as f:
        json.dump(briefings_doc, f, indent=2)

    print(f"\n{AGREE_COLOR}{BOLD}✓ Agent briefings saved to: {output_path}{RESET}")
    return output_path

# ─── Final Requirements Document ───────────────────────────────────────────────
def generate_requirements(context: dict) -> dict:
    print_header("GENERATING FINAL REQUIREMENTS DOCUMENT")

    history = format_conversation_history(context["conversation"])
    agreed = format_agreed(context["agreed_on"])
    clarifications = format_clarifications(context.get("client_clarifications", ""))

    # Product name + description
    prompt_name = (
        f"Based on this board meeting about: {context['client_idea']}\n"
        f"Client clarifications: {clarifications}\n\n"
        "Return JSON only with two keys: product_name (string), one_sentence_description (string). "
        "Be creative but grounded in what was discussed."
    )
    name_raw = call_llm(prompt_name, "CEO", fallback='{"product_name": "Startup MVP", "one_sentence_description": "A product built on this idea."}')
    try:
        start = name_raw.find("{")
        end = name_raw.rfind("}") + 1
        name_data = json.loads(name_raw[start:end])
    except Exception:
        name_data = {"product_name": "Startup MVP", "one_sentence_description": context["client_idea"][:100]}

    # Technical requirements from CTO
    prompt_tech = (
        f"You are the CTO. Based on this board meeting:\n{history}\n\n"
        "List exactly 5 specific technical requirements for the MVP. "
        "Return JSON only: {\"technical_requirements\": [\"req1\", \"req2\", \"req3\", \"req4\", \"req5\"]}"
    )
    tech_raw = call_llm(prompt_tech, "CTO", fallback='{"technical_requirements": ["Backend API", "Database setup", "Auth system", "Frontend", "Deployment"]}')
    try:
        start = tech_raw.find("{")
        end = tech_raw.rfind("}") + 1
        tech_data = json.loads(tech_raw[start:end])
    except Exception:
        tech_data = {"technical_requirements": ["Backend API", "Database setup", "Auth system", "Frontend", "Deployment pipeline"]}

    # Go-to-market from CMO
    prompt_gtm = (
        f"You are the CMO. Based on this board meeting:\n{history}\n\n"
        "Write exactly 3 go-to-market bullet points. "
        "Return JSON only: {\"go_to_market\": [\"bullet1\", \"bullet2\", \"bullet3\"]}"
    )
    gtm_raw = call_llm(prompt_gtm, "CMO", fallback='{"go_to_market": ["Identify target customer", "Build outreach list", "Launch beta"]}')
    try:
        start = gtm_raw.find("{")
        end = gtm_raw.rfind("}") + 1
        gtm_data = json.loads(gtm_raw[start:end])
    except Exception:
        gtm_data = {"go_to_market": ["Identify and segment target customers", "Build initial outreach and waitlist", "Launch private beta with 10 design partners"]}

    # Week 1 execution from COO — plain strings
    prompt_exec = (
        f"You are the COO. Based on this board meeting:\n{history}\n\nAgreed: {agreed}\n\n"
        "List exactly 5 specific Week 1 execution tasks. Each task must be a single plain string "
        "that includes the task description and the owner name in parentheses. "
        "Return JSON only: {\"week_one_execution\": [\"Task description (Owner)\", ...]}"
    )
    exec_raw = call_llm(prompt_exec, "COO", fallback='{"week_one_execution": ["Set up repo (CTO)", "Define MVP scope (CEO)", "Assign roles (COO)", "Set up weekly cadence (COO)", "Begin customer interviews (CMO)"]}')
    try:
        start = exec_raw.find("{")
        end = exec_raw.rfind("}") + 1
        exec_data = json.loads(exec_raw[start:end])
    except Exception:
        exec_data = {"week_one_execution": [
            "Set up development repository (CTO)",
            "Define MVP feature list (CEO + CTO)",
            "Identify 5 design partner candidates (CMO)",
            "Set weekly all-hands cadence (COO)",
            "Open questions review meeting (All)"
        ]}

    # Open questions
    prompt_oq = (
        f"Based on this board meeting:\n{history}\n\n"
        "List the 3 most important unresolved questions that need answering before next meeting. "
        "Return JSON only: {\"open_questions\": [\"q1\", \"q2\", \"q3\"]}"
    )
    oq_raw = call_llm(prompt_oq, "COO", fallback='{"open_questions": ["Who is the exact customer?", "What is the real timeline?", "What is the budget?"]}')
    try:
        start = oq_raw.find("{")
        end = oq_raw.rfind("}") + 1
        oq_data = json.loads(oq_raw[start:end])
        context["open_questions"] = oq_data.get("open_questions", [])
    except Exception:
        oq_data = {"open_questions": ["Who is the primary customer?", "What is the realistic timeline?", "What is available budget/runway?"]}
        context["open_questions"] = oq_data["open_questions"]

    # Next step
    prompt_next = (
        f"Based on this entire board meeting about: {context['client_idea']}\n"
        f"Agreements: {agreed}\n\n"
        "What is the single most important next action the client must take in the next 24 hours? "
        "Return JSON only: {\"next_step\": \"one clear action\"}"
    )
    next_raw = call_llm(prompt_next, "CEO", fallback='{"next_step": "Schedule follow-up meeting and assign all open action items."}')
    try:
        start = next_raw.find("{")
        end = next_raw.rfind("}") + 1
        next_data = json.loads(next_raw[start:end])
    except Exception:
        next_data = {"next_step": "Schedule follow-up with all board members and assign owners to Week 1 execution items."}

    doc = {
        "product_name": name_data.get("product_name", "Startup MVP"),
        "one_sentence_description": name_data.get("one_sentence_description", context["client_idea"][:100]),
        "technical_requirements": tech_data.get("technical_requirements", []),
        "go_to_market": gtm_data.get("go_to_market", []),
        "week_one_execution": exec_data.get("week_one_execution", []),
        "resolved_conflicts": context["agreed_on"],
        "open_questions": context["open_questions"],
        "next_step": next_data.get("next_step", ""),
        "full_conversation": context["conversation"],
    }

    return doc

# ─── Save Requirements ──────────────────────────────────────────────────────────
def save_output(doc: dict):
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "board_meeting_result.json"
    with open(output_path, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"\n{AGREE_COLOR}{BOLD}✓ Requirements saved to: {output_path}{RESET}")
    return output_path

# ─── Print Final Summary ────────────────────────────────────────────────────────
def print_summary(doc: dict):
    print_header(f"FINAL REQUIREMENTS: {doc['product_name']}")

    print(f"{BOLD}📌 {doc['one_sentence_description']}{RESET}\n")

    print(f"{CTO_COLOR}{BOLD}TECHNICAL REQUIREMENTS (CTO){RESET}")
    for i, req in enumerate(doc["technical_requirements"], 1):
        print(f"  {i}. {req}")

    print(f"\n{CMO_COLOR}{BOLD}GO-TO-MARKET (CMO){RESET}")
    for bullet in doc["go_to_market"]:
        print(f"  • {bullet}")

    print(f"\n{COO_COLOR}{BOLD}WEEK 1 EXECUTION (COO){RESET}")
    for i, task in enumerate(doc["week_one_execution"], 1):
        # Handle both plain strings and legacy dict format
        if isinstance(task, dict):
            task_str = task.get("task", str(task))
            owner = task.get("owner", "")
            print(f"  {i}. {task_str}" + (f" ({owner})" if owner else ""))
        else:
            print(f"  {i}. {task}")

    print(f"\n{AGREE_COLOR}{BOLD}RESOLVED CONFLICTS{RESET}")
    for item in doc["resolved_conflicts"]:
        print(f"  ✓ {item[:120]}")

    print(f"\n{CTO_COLOR}{BOLD}OPEN QUESTIONS{RESET}")
    for q in doc["open_questions"]:
        print(f"  ? {q}")

    print(f"\n{CONFLICT_COLOR}{BOLD}NEXT STEP → {doc['next_step']}{RESET}")
    separator("═", 70, HEADER_COLOR)

# ─── Main ───────────────────────────────────────────────────────────────────────
def main():
    separator("═", 70, HEADER_COLOR)
    print(f"{HEADER_COLOR}{BOLD}")
    print("  ███╗   ██╗██╗███╗   ██╗ ██████╗ ███████╗███╗   ██╗")
    print("  ████╗  ██║██║████╗  ██║██╔════╝ ██╔════╝████╗  ██║")
    print("  ██╔██╗ ██║██║██╔██╗ ██║██║  ███╗█████╗  ██╔██╗ ██║")
    print("  ██║╚██╗██║██║██║╚██╗██║██║   ██║██╔══╝  ██║╚██╗██║")
    print("  ██║ ╚████║██║██║ ╚████║╚██████╔╝███████╗██║ ╚████║")
    print("  ╚═╝  ╚═══╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝")
    print(f"{RESET}")
    print(f"{HEADER_COLOR}          AI BOARD MEETING SYSTEM — gpt-4o-mini{RESET}")
    separator("═", 70, HEADER_COLOR)
    print()

    client_idea = input(f"{BOLD}🚀 Client, describe your startup idea:\n> {RESET}").strip()
    if not client_idea:
        print("No idea entered. Exiting.")
        return

    print(f"\n{DIM}Idea received. Convening the board...{RESET}\n")
    time.sleep(1)

    # Initialize shared context
    context = {
        "client_idea": client_idea,
        "conversation": [],
        "ceo_position": "",
        "cto_position": "",
        "cmo_position": "",
        "coo_position": "",
        "client_clarifications": "",
        "agreed_on": [],
        "conflicts": [],
        "open_questions": [],
    }

    # Run the meeting
    run_round_1(context)
    print(f"\n{DIM}Round 1 complete. Agents have questions for the client...{RESET}\n")
    time.sleep(0.5)

    run_client_questions(context)
    print(f"\n{DIM}Client clarifications noted. Moving to reactions...{RESET}\n")
    time.sleep(0.5)

    run_round_2(context)
    print(f"\n{DIM}Round 2 complete. Running conflict detection...{RESET}\n")
    time.sleep(0.5)

    detect_conflicts(context)
    print(f"\n{DIM}Conflicts identified. Moving to resolution...{RESET}\n")
    time.sleep(0.5)

    run_round_3(context)
    print(f"\n{DIM}Resolution complete. Generating final briefings...{RESET}\n")
    time.sleep(0.5)

    briefings = run_final_briefings(context)
    save_briefings(briefings, context)

    print(f"\n{DIM}Briefings complete. Generating requirements document...{RESET}\n")
    time.sleep(0.5)

    doc = generate_requirements(context)
    save_output(doc)
    print_summary(doc)

    separator("═", 70, AGREE_COLOR)
    print(f"{AGREE_COLOR}{BOLD}  Board meeting complete. Agents are briefed and ready to execute.{RESET}")
    separator("═", 70, AGREE_COLOR)


# ══════════════════════════════════════════════════════════════════════════════
# API FUNCTIONS — used by the Gradio interface (app.py)
# Each function returns structured data instead of printing to terminal.
# Terminal mode (main) is unaffected.
# ══════════════════════════════════════════════════════════════════════════════

def initialize_context(client_idea: str) -> dict:
    """Initialise a fresh shared context dict for a new board meeting."""
    return {
        "client_idea": client_idea,
        "conversation": [],
        "ceo_position": "",
        "cto_position": "",
        "cmo_position": "",
        "coo_position": "",
        "client_clarifications": "",
        "agreed_on": [],
        "conflicts": [],
        "open_questions": [],
    }


def api_run_opening_round(context: dict):
    """Generator — Round 1 opening positions. Yields message dicts, mutates context."""
    clr = format_clarifications(context.get("client_clarifications", ""))

    # CEO ──────────────────────────────────────────────────────────────────────
    instr = (
        "Read the client's idea carefully. State your position: "
        "what is the vision you see, what risks concern you, and what internal questions "
        "do you have before committing? Be bold — but understand the problem first.\n\n"
        + ROUND_1_CONSTRAINT
    )
    prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CEO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clr}\n\n"
        f"=== YOUR INSTRUCTION ===\n{instr}"
    )
    msg = call_llm(prompt, "CEO")
    context["ceo_position"] = msg
    context["conversation"].append({"speaker": "CEO", "message": msg, "type": "opening", "responding_to": "client_idea"})
    yield {"speaker": "CEO", "role": AGENTS["CEO"]["role"], "message": msg, "type": "opening"}

    # CTO ──────────────────────────────────────────────────────────────────────
    instr = (
        "Read the client's idea and the CEO's position. Identify the most critical technical risk. "
        "Ask the internal questions you need answered before assessing feasibility.\n\n"
        + ROUND_1_CONSTRAINT
    )
    prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CTO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clr}\n\n"
        f"=== CEO POSITION ===\n{context['ceo_position']}\n\n"
        f"=== YOUR INSTRUCTION ===\n{instr}"
    )
    msg = call_llm(prompt, "CTO")
    context["cto_position"] = msg
    context["conversation"].append({"speaker": "CTO", "message": msg, "type": "opening", "responding_to": "ceo_position"})
    yield {"speaker": "CTO", "role": AGENTS["CTO"]["role"], "message": msg, "type": "opening"}

    # CMO ──────────────────────────────────────────────────────────────────────
    instr = (
        "Identify the market risks and customer unknowns. Ask the internal questions you need "
        "before validating whether this idea has a real market.\n\n" + ROUND_1_CONSTRAINT
    )
    prompt = (
        f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS['CMO']['personality']}\n\n"
        f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
        f"=== CLIENT CLARIFICATIONS ===\n{clr}\n\n"
        f"=== CEO POSITION ===\n{context['ceo_position']}\n\n"
        f"=== CTO POSITION ===\n{context['cto_position']}\n\n"
        f"=== YOUR INSTRUCTION ===\n{instr}"
    )
    msg = call_llm(prompt, "CMO")
    context["cmo_position"] = msg
    context["conversation"].append({"speaker": "CMO", "message": msg, "type": "opening", "responding_to": "cto_position"})
    yield {"speaker": "CMO", "role": AGENTS["CMO"]["role"], "message": msg, "type": "opening"}

    # COO ──────────────────────────────────────────────────────────────────────
    instr = (
        "What is the biggest execution risk right now? Who should own what? "
        "What can go wrong that nobody is talking about?\n\n" + ROUND_1_CONSTRAINT
    )
    msg = call_llm(build_prompt("COO", context, instr), "COO")
    context["coo_position"] = msg
    context["conversation"].append({"speaker": "COO", "message": msg, "type": "opening", "responding_to": "all_positions"})
    yield {"speaker": "COO", "role": AGENTS["COO"]["role"], "message": msg, "type": "opening"}


def api_generate_questions(context: dict):
    """Generate one clarifying question per agent. Returns (context, messages, questions_dict)."""
    clr = format_clarifications(context.get("client_clarifications", ""))
    history = format_conversation_history(context["conversation"])

    roles_and_instructions = {
        "CEO": (
            "Generate exactly ONE clarifying question for the client about "
            "vision and success definition: what does success look like in 90 days "
            "and how will they know the product has won? One question only. No preamble."
        ),
        "CTO": (
            "Generate exactly ONE clarifying question about technical constraints or "
            "existing systems: what infrastructure already exists and what hard constraints "
            "must be worked within? One question only. No preamble."
        ),
        "CMO": (
            "Generate exactly ONE clarifying question about who the client thinks their "
            "customer is: who specifically is the first customer and why would they pay today? "
            "One question only. No preamble."
        ),
        "COO": (
            "Generate exactly ONE clarifying question about timeline and resources: "
            "what is the hard deadline if any, and what budget and headcount is available? "
            "One question only. No preamble."
        ),
    }

    questions = {}
    messages = []
    for agent_key, instr in roles_and_instructions.items():
        prompt = (
            f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS[agent_key]['personality']}\n\n"
            f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
            f"=== CLIENT CLARIFICATIONS ===\n{clr}\n\n"
            f"=== CONVERSATION SO FAR ===\n{history}\n\n"
            f"=== YOUR INSTRUCTION ===\n{instr}"
        )
        q = call_llm(prompt, agent_key, max_tokens=100)
        questions[agent_key] = q
        messages.append({"speaker": agent_key, "role": AGENTS[agent_key]["role"], "message": q, "type": "question"})

    return context, messages, questions


def api_apply_clarifications(context: dict, answer: str, questions: dict) -> dict:
    """Store the client's answers in context and add to conversation."""
    context["client_clarifications"] = (
        f"CEO asked: {questions.get('CEO', '')}\n"
        f"CTO asked: {questions.get('CTO', '')}\n"
        f"CMO asked: {questions.get('CMO', '')}\n"
        f"COO asked: {questions.get('COO', '')}\n\n"
        f"Client's answer: {answer}"
    )
    context["conversation"].append({
        "speaker": "CLIENT",
        "message": context["client_clarifications"],
        "type": "clarification",
        "responding_to": "agent_questions",
    })
    return context


def api_run_reaction_round(context: dict):
    """Generator — Round 2 reactions. Yields message dicts, mutates context."""
    # CEO reacts to COO
    coo_last = next((e["message"] for e in reversed(context["conversation"]) if e["speaker"] == "COO"), "")
    instr = (
        f"The COO said: '{coo_last}'\n"
        "React directly. Push back on the caution. Restate why speed matters. What does the MVP look like in your mind?"
    )
    msg = call_llm(build_prompt("CEO", context, instr), "CEO")
    context["conversation"].append({"speaker": "CEO", "message": msg, "type": "reaction", "responding_to": "COO"})
    yield {"speaker": "CEO", "role": AGENTS["CEO"]["role"], "message": msg, "type": "reaction"}

    # CTO pushes back on CEO
    ceo_last = next((e["message"] for e in reversed(context["conversation"]) if e["speaker"] == "CEO"), "")
    instr = (
        f"The CEO just said: '{ceo_last}'\n"
        "Push back on the timeline with ONE specific technical reason. Name the system or failure mode. Propose an alternative."
    )
    msg = call_llm(build_prompt("CTO", context, instr), "CTO")
    context["conversation"].append({"speaker": "CTO", "message": msg, "type": "reaction", "responding_to": "CEO"})
    yield {"speaker": "CTO", "role": AGENTS["CTO"]["role"], "message": msg, "type": "reaction"}

    # CMO anchors to customer
    cto_last = next((e["message"] for e in reversed(context["conversation"]) if e["speaker"] == "CTO"), "")
    instr = (
        f"The CTO said: '{cto_last}'\n"
        "Acknowledge constraints but anchor back to the customer. Name your target archetype. Does the CTO's scope cover Day 1 customer needs?"
    )
    msg = call_llm(build_prompt("CMO", context, instr), "CMO")
    context["conversation"].append({"speaker": "CMO", "message": msg, "type": "reaction", "responding_to": "CTO"})
    yield {"speaker": "CMO", "role": AGENTS["CMO"]["role"], "message": msg, "type": "reaction"}

    # COO lists what is unresolved
    instr = (
        "Look at the full conversation including client clarifications. "
        "List the top 3 things STILL unresolved. Be blunt. What will derail us if not decided today?"
    )
    msg = call_llm(build_prompt("COO", context, instr), "COO")
    context["conversation"].append({"speaker": "COO", "message": msg, "type": "reaction", "responding_to": "all"})
    yield {"speaker": "COO", "role": AGENTS["COO"]["role"], "message": msg, "type": "reaction"}


def api_detect_conflicts_return(context: dict):
    """Detect conflicts and return (context, list-of-conflict-message-dicts)."""
    conflicts = []
    ceo_t = " ".join(e["message"] for e in context["conversation"] if e["speaker"] == "CEO").lower()
    cto_t = " ".join(e["message"] for e in context["conversation"] if e["speaker"] == "CTO").lower()
    cmo_t = " ".join(e["message"] for e in context["conversation"] if e["speaker"] == "CMO").lower()
    coo_t = " ".join(e["message"] for e in context["conversation"] if e["speaker"] == "COO").lower()

    spd = ["week", "days", "fast", "quick", "asap", "immediately", "sprint"]
    slw = ["month", "longer", "minimum", "realistic", "underestimate", "complex"]
    if any(k in ceo_t for k in spd) and any(k in cto_t for k in slw):
        conflicts.append({"agents_involved": ["CEO", "CTO"], "topic": "Timeline", "severity": "high",
                          "description": "CEO is pushing an aggressive timeline while CTO flagged it as technically unrealistic."})

    b2b = ["b2b", "enterprise", "business", "company", "team", "manager", "professional"]
    b2c = ["consumer", "individual", "personal", "user", "people", "anyone", "everyone"]
    if (any(k in cmo_t for k in b2b) and any(k in ceo_t for k in b2c)) or \
       (any(k in cmo_t for k in b2c) and any(k in ceo_t for k in b2b)):
        conflicts.append({"agents_involved": ["CEO", "CMO"], "topic": "Target Customer", "severity": "high",
                          "description": "CEO's market vision and CMO's customer archetype are misaligned (B2B vs B2C)."})

    blk = ["nobody owns", "no owner", "unclear", "unassigned", "missing", "blocker", "nobody", "not assigned"]
    if any(k in coo_t for k in blk):
        conflicts.append({"agents_involved": ["CEO", "COO"], "topic": "Execution Blockers", "severity": "medium",
                          "description": "COO identified execution blockers that CEO has not addressed."})

    res = ["runway", "budget", "hire", "headcount", "capacity", "bandwidth", "not enough"]
    scp = ["build", "launch", "ship", "integrate", "develop", "implement", "design"]
    if any(k in coo_t for k in res) and any(k in cto_t for k in scp):
        conflicts.append({"agents_involved": ["CTO", "COO"], "topic": "Resource Capacity", "severity": "medium",
                          "description": "CTO's technical scope may exceed the resources COO says are available."})

    if not conflicts:
        prompt = (
            f"Review this board meeting:\n{format_conversation_history(context['conversation'])}\n\n"
            "Identify the single most important conflict. Return JSON only: "
            "{\"agents_involved\": [], \"topic\": \"\", \"severity\": \"\", \"description\": \"\"}"
        )
        try:
            raw = call_llm(prompt, "CEO", fallback=None)
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s != -1 and e > s:
                conflicts.append(json.loads(raw[s:e]))
        except Exception:
            conflicts.append({"agents_involved": ["CEO", "CTO"], "topic": "Alignment", "severity": "medium",
                              "description": "General misalignment between vision and technical feasibility."})

    context["conflicts"] = conflicts
    msgs = []
    for c in conflicts:
        msgs.append({
            "speaker": "SYSTEM", "role": "Conflict Detector", "type": "conflict",
            "message": f"⚠ {c['topic']} [{c['severity'].upper()}]: {c['description']} (Agents: {', '.join(c['agents_involved'])})",
            "conflict_data": c,
        })
    return context, msgs


def api_run_resolution_round(context: dict):
    """Generator — Round 3 resolution. Yields message dicts, mutates context."""
    for conflict in context["conflicts"]:
        agents = conflict["agents_involved"]
        topic = conflict["topic"]
        agent_a, agent_b = agents[0], agents[1]

        yield {"speaker": "SYSTEM", "role": "Resolution Chair", "type": "resolution_header",
               "message": f"Resolving: {topic} between {' & '.join(agents)}"}

        instr_a = (
            f"Conflict between you ({agent_a}) and {agent_b} on: {topic}\n"
            f"Description: {conflict['description']}\n\n"
            "Speak DIRECTLY to the other agent. Propose a specific compromise. Be concrete — numbers, dates, customer segments."
        )
        msg_a = call_llm(build_prompt(agent_a, context, instr_a), agent_a)
        context["conversation"].append({"speaker": agent_a, "message": msg_a, "type": "resolution", "responding_to": agent_b})
        yield {"speaker": agent_a, "role": AGENTS[agent_a]["role"], "message": msg_a, "type": "resolution"}

        instr_b = (
            f"Conflict between you ({agent_b}) and {agent_a} on: {topic}\n"
            f"Description: {conflict['description']}\n\n"
            f"{agent_a} just said: '{msg_a}'\n\n"
            "Respond DIRECTLY. Accept with conditions or counter-propose. End with 'AGREED:' and a clear statement."
        )
        msg_b = call_llm(build_prompt(agent_b, context, instr_b), agent_b)
        context["conversation"].append({"speaker": agent_b, "message": msg_b, "type": "resolution", "responding_to": agent_a})
        yield {"speaker": agent_b, "role": AGENTS[agent_b]["role"], "message": msg_b, "type": "resolution"}

        agreement_text = f"{topic}: {agent_a} & {agent_b} — "
        if "AGREED:" in msg_b.upper():
            idx = msg_b.upper().find("AGREED:")
            agreement_text += msg_b[idx:].strip()
        else:
            agreement_text += f"{msg_a[:80]}… resolved → {msg_b[:80]}…"
        context["agreed_on"].append(agreement_text)

        yield {"speaker": "SYSTEM", "role": "Agreement", "type": "agreement", "message": agreement_text}


def api_run_briefings(context: dict):
    """Generator — final personal briefings. Yields message dicts."""
    history = format_conversation_history(context["conversation"])
    agreed  = format_agreed(context["agreed_on"])
    clr     = format_clarifications(context.get("client_clarifications", ""))

    briefing_instructions = {
        "CEO": (
            "Produce your CEO mission briefing. Include exactly:\n"
            "1. COMPANY MISSION: One sentence.\n"
            "2. NORTH STAR METRIC: The single metric you obsess over.\n"
            "3. SUCCESS IN 90 DAYS: Specific, measurable.\n"
            "4. WEEKLY MONITOR: What you personally check every week.\n"
            "Use these exact headers."
        ),
        "CTO": (
            "Produce your CTO mission briefing. Include exactly:\n"
            "1. TECHNICAL APPROACH: Three bullet points.\n"
            "2. BIGGEST RISK & MITIGATION: Risk + specific mitigation plan.\n"
            "3. WEEK ONE BUILD: Exactly what you build in week one.\n"
            "4. NEEDS FROM CMO & COO: What you need from them — be specific.\n"
            "Use these exact headers."
        ),
        "CMO": (
            "Produce your CMO mission briefing. Include exactly:\n"
            "1. TARGET CUSTOMER: One specific sentence (job title, company type, pain point).\n"
            "2. CORE MESSAGE: One sentence to that customer.\n"
            "3. GO TO MARKET: Three bullet points.\n"
            "4. NEEDS FROM CTO: What you need from CTO to start marketing.\n"
            "Use these exact headers."
        ),
        "COO": (
            "Produce your COO mission briefing. Include exactly:\n"
            "1. WEEK ONE EXECUTION PLAN: Numbered list, one owner per task.\n"
            "2. TOP THREE RISKS: In order of severity.\n"
            "3. DECISIONS NEEDED: Before work starts.\n"
            "4. COMPANY HEALTH: Morale, runway, capacity assessment.\n"
            "Use these exact headers."
        ),
    }

    for agent_key, instr in briefing_instructions.items():
        prompt = (
            f"=== YOUR ROLE & PERSONALITY ===\n{AGENTS[agent_key]['personality']}\n\n"
            f"=== CLIENT'S IDEA ===\n{context['client_idea']}\n\n"
            f"=== CLIENT CLARIFICATIONS ===\n{clr}\n\n"
            f"=== FULL MEETING CONVERSATION ===\n{history}\n\n"
            f"=== WHAT WAS AGREED ===\n{agreed}\n\n"
            f"=== YOUR INSTRUCTION ===\n{instr}"
        )
        briefing = call_llm(prompt, agent_key, max_tokens=600)
        yield {"speaker": agent_key, "role": AGENTS[agent_key]["role"], "message": briefing, "type": "briefing"}


def api_generate_requirements(context: dict):
    """Generate the final requirements document. Returns (context, doc_dict)."""
    history = format_conversation_history(context["conversation"])
    agreed  = format_agreed(context["agreed_on"])
    clr     = format_clarifications(context.get("client_clarifications", ""))

    def safe_json(raw, fallback):
        try:
            s, e = raw.find("{"), raw.rfind("}") + 1
            return json.loads(raw[s:e]) if s != -1 and e > s else fallback
        except Exception:
            return fallback

    name_raw = call_llm(
        f"Based on this board meeting about: {context['client_idea']}\nClient clarifications: {clr}\n\n"
        "Return JSON only: {\"product_name\": \"...\", \"one_sentence_description\": \"...\"}",
        "CEO", fallback='{"product_name":"Startup MVP","one_sentence_description":"A product built on this idea."}'
    )
    name_data = safe_json(name_raw, {"product_name": "Startup MVP", "one_sentence_description": context["client_idea"][:100]})

    tech_raw = call_llm(
        f"You are the CTO. Based on:\n{history}\nList 5 specific technical requirements for the MVP. "
        "Return JSON only: {\"technical_requirements\":[\"r1\",\"r2\",\"r3\",\"r4\",\"r5\"]}",
        "CTO", fallback='{"technical_requirements":["Backend API","Database","Auth","Frontend","Deployment"]}'
    )
    tech_data = safe_json(tech_raw, {"technical_requirements": ["Backend API", "Database", "Auth", "Frontend", "Deployment"]})

    gtm_raw = call_llm(
        f"You are the CMO. Based on:\n{history}\nWrite 3 go-to-market bullet points. "
        "Return JSON only: {\"go_to_market\":[\"b1\",\"b2\",\"b3\"]}",
        "CMO", fallback='{"go_to_market":["Identify target customer","Build outreach list","Launch beta"]}'
    )
    gtm_data = safe_json(gtm_raw, {"go_to_market": ["Identify target customer", "Build outreach list", "Launch beta"]})

    exec_raw = call_llm(
        f"You are the COO. Based on:\n{history}\nAgreed: {agreed}\n"
        "List 5 Week 1 tasks as plain strings with owner in parentheses. "
        "Return JSON only: {\"week_one_execution\":[\"Task (Owner)\",...]}",
        "COO", fallback='{"week_one_execution":["Set up repo (CTO)","Define MVP scope (CEO)","Assign roles (COO)","Set weekly cadence (COO)","Customer interviews (CMO)"]}'
    )
    exec_data = safe_json(exec_raw, {"week_one_execution": ["Set up repo (CTO)", "Define MVP scope (CEO)", "Assign roles (COO)", "Weekly cadence (COO)", "Customer interviews (CMO)"]})

    oq_raw = call_llm(
        f"Based on:\n{history}\nList 3 most important unresolved questions. "
        "Return JSON only: {\"open_questions\":[\"q1\",\"q2\",\"q3\"]}",
        "COO", fallback='{"open_questions":["Who is the exact customer?","What is the real timeline?","What is the budget?"]}'
    )
    oq_data = safe_json(oq_raw, {"open_questions": ["Who is the primary customer?", "What is the timeline?", "What is the budget?"]})
    context["open_questions"] = oq_data.get("open_questions", [])

    next_raw = call_llm(
        f"Based on this board meeting about: {context['client_idea']}\nAgreements: {agreed}\n"
        "What is the single most important next action the client must take in 24 hours? "
        "Return JSON only: {\"next_step\":\"...\"}",
        "CEO", fallback='{"next_step":"Schedule follow-up meeting and assign all open action items."}'
    )
    next_data = safe_json(next_raw, {"next_step": "Schedule follow-up and assign owners to Week 1 items."})

    doc = {
        "product_name": name_data.get("product_name", "Startup MVP"),
        "one_sentence_description": name_data.get("one_sentence_description", context["client_idea"][:100]),
        "technical_requirements": tech_data.get("technical_requirements", []),
        "go_to_market": gtm_data.get("go_to_market", []),
        "week_one_execution": exec_data.get("week_one_execution", []),
        "resolved_conflicts": context["agreed_on"],
        "open_questions": context["open_questions"],
        "next_step": next_data.get("next_step", ""),
        "client_idea": context["client_idea"],
        "client_clarifications": context.get("client_clarifications", ""),
        "full_conversation": context["conversation"],
    }
    return context, doc


if __name__ == "__main__":
    main()
