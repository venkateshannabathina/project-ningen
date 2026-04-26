#!/usr/bin/env python3
"""
Flask API server — runs alongside Streamlit.
uidesign.html fetches from http://localhost:5001/api/*
board_meeting.py functions run in background threads.
"""

import sys
import os
import threading
import random
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from flask_cors import CORS

from board_meeting import (
    initialize_context,
    api_run_opening_round,
    api_generate_questions,
    api_apply_clarifications,
    api_run_reaction_round,
    api_detect_conflicts_return,
    api_run_resolution_round,
    api_run_briefings,
    api_generate_requirements,
    save_output,
    save_briefings,
)

try:
    from memory_store import load_memory, save_memory
    MEMORY_ENABLED = True
except ImportError:
    MEMORY_ENABLED = False

flask_app = Flask(__name__)
CORS(flask_app)

# ── Shared API state (protected by lock) ────────────────────────
_lock = threading.Lock()
_BLANK_RESULTS = lambda: {
    "CEO": {"status": "idle", "output": ""},
    "CTO": {"status": "idle", "output": ""},
    "CMO": {"status": "idle", "output": ""},
    "COO": {"status": "idle", "output": ""},
}

_state = {
    "messages": [],
    "phase": "idle",
    "agentStates": {"CEO": "office", "CTO": "office", "CMO": "office", "COO": "office"},
    "statuses": {"CEO": "idle...", "CTO": "idle...", "CMO": "idle...", "COO": "idle..."},
    "scores": {"Requirements": 0, "Product": 0, "Marketing": 0, "Conflicts": 0, "Efficiency": 0},
    "reward": 0.0,
    "episode": {"current": 0, "total": 3, "trend": 0},
    "agent_results": _BLANK_RESULTS(),
    "ctx": None,
    "questions": None,
    "briefing_store": {},
}

def _st(key, value=None):
    with _lock:
        if value is None:
            return _state[key]
        _state[key] = value

def _add_message(agent, round_name, text):
    with _lock:
        _state["messages"].append({
            "agent": agent,
            "round": round_name,
            "text": text[:400],
        })

def _set_agent_active(agent_id):
    with _lock:
        _state["active_agent"] = agent_id
        if agent_id:
            _state["agentStates"][agent_id] = "table"
            _state["statuses"][agent_id] = "talking..."
            for a in ["CEO", "CTO", "CMO", "COO"]:
                if a != agent_id:
                    _state["statuses"][a] = "listening..."

def _update_scores():
    with _lock:
        for k in _state["scores"]:
            _state["scores"][k] = min(1.0, _state["scores"][k] + random.uniform(0.05, 0.15))
        _state["reward"] = round(_state["reward"] + random.uniform(0.01, 0.04), 3)

def _move_all_to_table():
    with _lock:
        for agent in ["CEO", "CTO", "CMO", "COO"]:
            _state["agentStates"][agent] = "table"

# ── Board meeting pipeline (runs in background thread) ──────────
def _run_board_meeting(idea):
    try:
        memory_context = load_memory() if MEMORY_ENABLED else ""
        ctx = initialize_context(idea, memory_context)
        _st("ctx", ctx)
        _st("phase", "opening")
        _st("episode", {"current": 1, "total": 3, "trend": 0})
        _add_message("FOUNDER", "IDEA", idea)

        # Move agents to table
        _move_all_to_table()
        with _lock:
            _state["statuses"] = {"CEO": "thinking...", "CTO": "thinking...", "CMO": "thinking...", "COO": "thinking..."}

        # Opening round
        for md in api_run_opening_round(ctx):
            spk = md.get("speaker", "")
            msg = md.get("message", "")
            _set_agent_active(spk)
            _add_message(spk, "OPENING", msg)
        _update_scores()

        # Questions
        with _lock:
            ctx = _state["ctx"]
        ctx, q_msgs, questions = api_generate_questions(ctx)
        with _lock:
            _state["ctx"] = ctx
            _state["questions"] = questions
        for md in q_msgs:
            spk = md.get("speaker", "")
            msg = md.get("message", "")
            _set_agent_active(spk)
            _add_message(spk, "QUESTION", msg)

        _st("phase", "answering")

    except Exception as e:
        _add_message("SYSTEM", "ERROR", f"Error: {str(e)}")
        _st("phase", "idle")


def _process_answer(answer):
    try:
        _add_message("FOUNDER", "REPLY", answer)
        with _lock:
            ctx = _state["ctx"]
            questions = _state["questions"]

        ctx = api_apply_clarifications(ctx, answer, questions)
        with _lock:
            _state["ctx"] = ctx
        _update_scores()
        _st("phase", "reaction")

        # Reaction round
        for md in api_run_reaction_round(ctx):
            spk = md.get("speaker", "")
            msg = md.get("message", "")
            _set_agent_active(spk)
            _add_message(spk, "REACTION", msg)
        _update_scores()
        _st("phase", "conflicts")

        # Conflicts
        with _lock:
            ctx = _state["ctx"]
        ctx, conflict_msgs = api_detect_conflicts_return(ctx)
        with _lock:
            _state["ctx"] = ctx
        for cm in conflict_msgs:
            spk = cm.get("speaker", "")
            msg = cm.get("message", "")
            if spk:
                _set_agent_active(spk)
                _add_message(spk, "CONFLICT", msg)
            else:
                _add_message("SYSTEM", "CONFLICT", msg)
        _st("phase", "resolution")

        # Resolution
        with _lock:
            ctx = _state["ctx"]
        for md in api_run_resolution_round(ctx):
            spk = md.get("speaker", "")
            msg = md.get("message", "")
            _set_agent_active(spk)
            _add_message(spk, "RESOLUTION", msg)
        _update_scores()
        _st("phase", "briefings")

        # Briefings
        briefing_store = {}
        with _lock:
            ctx = _state["ctx"]
        for md in api_run_briefings(ctx):
            spk = md.get("speaker", "")
            msg = md.get("message", "")
            _set_agent_active(spk)
            _add_message(spk, "BRIEFING", msg)
            briefing_store[spk] = msg
        with _lock:
            _state["briefing_store"] = briefing_store
        save_briefings(briefing_store, ctx)
        _st("phase", "requirements")

        # Requirements
        with _lock:
            ctx = _state["ctx"]
        ctx, doc = api_generate_requirements(ctx)
        with _lock:
            _state["ctx"] = ctx
        save_output(doc)
        if MEMORY_ENABLED:
            try:
                save_memory(doc, ctx, briefing_store)
            except Exception:
                pass
        _update_scores()
        _add_message("SYSTEM", "FINAL", f"✅ Meeting complete: {doc.get('product_name', 'Startup MVP')}")
        with _lock:
            _state["active_agent"] = None
            _state["agentStates"] = {"CEO": "office", "CTO": "office", "CMO": "office", "COO": "office"}
            reward = _state["reward"]
            _state["episode"] = {"current": 1, "total": 3, "trend": round(reward, 3)}
            _state["agent_results"] = _BLANK_RESULTS()
        _st("phase", "done")
        # Auto-trigger all execution agents
        threading.Thread(target=_run_execution_agents, daemon=True).start()

    except Exception as e:
        _add_message("SYSTEM", "ERROR", f"Error: {str(e)}")
        _st("phase", "idle")


# ── Execution agents (run after board meeting ends) ──────────────
def _run_one_agent(agent_id, pipeline_fn, label):
    with _lock:
        _state["agent_results"][agent_id] = {"status": "running", "output": ""}
        _state["statuses"][agent_id] = f"{label}..."
    _add_message("SYSTEM", "EXEC", f"🔧 {agent_id} starting {label}...")
    try:
        result = pipeline_fn()
        output = result.get("file") or result.get("files", [""])[0] if result.get("success") else ""
        if isinstance(output, list):
            output = output[0] if output else ""
        with _lock:
            _state["agent_results"][agent_id] = {
                "status": "done" if result.get("success") else "error",
                "output": str(output),
            }
            _state["statuses"][agent_id] = "done ✓" if result.get("success") else "error ✗"
        msg = f"✅ {agent_id} finished: {output.split('/')[-1] if output else 'complete'}" \
              if result.get("success") else f"❌ {agent_id} failed: {result.get('error','unknown')}"
        _add_message("SYSTEM", "EXEC", msg)
    except Exception as e:
        with _lock:
            _state["agent_results"][agent_id] = {"status": "error", "output": ""}
            _state["statuses"][agent_id] = "error ✗"
        _add_message("SYSTEM", "EXEC", f"❌ {agent_id} error: {str(e)}")


def _run_execution_agents():
    from execute_cto import run_cto_pipeline
    from execute_cmo import run_cmo_pipeline
    from execute_coo import run_coo_pipeline
    from execute_ceo import run_ceo_pipeline

    pipelines = [
        ("CTO", run_cto_pipeline, "building"),
        ("CMO", run_cmo_pipeline, "marketing"),
        ("COO", run_coo_pipeline, "planning"),
        ("CEO", run_ceo_pipeline, "strategizing"),
    ]
    threads = []
    for agent_id, fn, label in pipelines:
        t = threading.Thread(target=_run_one_agent, args=(agent_id, fn, label), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    _add_message("SYSTEM", "EXEC", "🏁 All agents done. Check outputs/ folder.")


# ── Flask endpoints ──────────────────────────────────────────────
@flask_app.route("/api/messages", methods=["GET"])
def get_messages():
    with _lock:
        return jsonify({
            "messages": _state["messages"][-50:],
            "phase": _state["phase"],
            "agentStates": _state["agentStates"],
            "statuses": _state["statuses"],
            "scores": _state["scores"],
            "reward": _state["reward"],
            "episode": _state["episode"],
            "agent_results": _state["agent_results"],
        })


@flask_app.route("/api/output/<agent_id>", methods=["GET"])
def get_output(agent_id):
    agent_id = agent_id.upper()
    outputs = Path(os.path.dirname(__file__)) / "outputs"

    def read(p):
        p = Path(p)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    if agent_id == "CTO":
        # Find most recently modified index.html under outputs/
        files = list(outputs.rglob("index.html"))
        if files:
            latest = max(files, key=lambda f: f.stat().st_mtime)
            return jsonify({"type": "html", "content": read(latest), "path": str(latest)})
        return jsonify({"type": "html", "content": "", "error": "not found"})

    if agent_id == "CMO":
        return jsonify({"type": "cmo", "files": {
            "Discord Post":     read(outputs / "discord_post.md"),
            "Reddit Post":      read(outputs / "reddit_post.md"),
            "Dev.to Article":   read(outputs / "devto_article.md"),
            "Cold Email":       read(outputs / "cold_email.md"),
        }})

    if agent_id == "COO":
        return jsonify({"type": "doc", "files": {
            "Execution Plan":   read(outputs / "execution_plan.md"),
            "Risk Register":    read(outputs / "risk_register.md"),
        }})

    if agent_id == "CEO":
        return jsonify({"type": "doc", "files": {
            "Investor Pitch":   read(outputs / "investor_pitch.md"),
            "Executive Summary": read(outputs / "executive_summary.md"),
        }})

    return jsonify({"error": "unknown agent"}), 404


@flask_app.route("/api/send", methods=["POST"])
def send_message():
    data = request.json or {}
    text = (data.get("text") or "").strip()
    phase = data.get("phase", "idle")

    if not text:
        return jsonify({"ok": False, "error": "empty"})

    if phase == "idle":
        _st("phase", "starting")
        threading.Thread(target=_run_board_meeting, args=(text,), daemon=True).start()
    elif phase == "answering":
        _st("phase", "processing")
        threading.Thread(target=_process_answer, args=(text,), daemon=True).start()

    return jsonify({"ok": True})


@flask_app.route("/api/reset", methods=["POST"])
def reset():
    with _lock:
        _state.update({
            "messages": [],
            "phase": "idle",
            "agentStates": {"CEO": "office", "CTO": "office", "CMO": "office", "COO": "office"},
            "statuses": {"CEO": "idle...", "CTO": "idle...", "CMO": "idle...", "COO": "idle..."},
            "scores": {"Requirements": 0, "Product": 0, "Marketing": 0, "Conflicts": 0, "Efficiency": 0},
            "agent_results": _BLANK_RESULTS(),
            "reward": 0.0,
            "episode": {"current": 0, "total": 3, "trend": 0},
            "ctx": None,
            "questions": None,
            "briefing_store": {},
        })
    return jsonify({"ok": True})


def start_server(port=5001):
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
