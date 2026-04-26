#!/usr/bin/env python3
"""
Memory Store — Cross-Episode Learning for Ningen Agents

Stores summaries of completed board meetings so agents can reference past runs
and learn from previous decisions, conflicts, and resolutions.
"""

import json
from pathlib import Path
from datetime import datetime

MEMORY_PATH = Path("outputs") / "memory_store.json"
MAX_ENTRIES = 20
LOAD_LAST_N = 3


def load_memory() -> str:
    """
    Load the last N meeting summaries and format as a prompt section.
    Returns empty string if file doesn't exist or is empty.
    """
    if not MEMORY_PATH.exists():
        return ""

    try:
        with open(MEMORY_PATH, "r") as f:
            entries = json.load(f)
            if not entries:
                return ""

        recent = entries[-LOAD_LAST_N:]
        formatted = "=== PAST MEETING MEMORY (last 3 sessions) ===\n"
        for i, entry in enumerate(recent, 1):
            formatted += f"\n[{i}] Product: {entry.get('product_name', 'Unknown')}\n"
            formatted += f"    Idea: {entry.get('idea', 'N/A')}\n"

            conflicts = entry.get("conflicts", [])
            if conflicts:
                formatted += f"    Conflicts encountered: {', '.join(conflicts)}\n"

            resolutions = entry.get("resolutions", [])
            if resolutions:
                res_text = "; ".join(r[:60] + "..." if len(r) > 60 else r for r in resolutions)
                formatted += f"    Resolutions: {res_text}\n"

            customer = entry.get("target_customer", "")
            if customer:
                formatted += f"    Target customer: {customer}\n"

        formatted += "\n==="
        return formatted

    except (json.JSONDecodeError, Exception):
        return ""


def save_memory(doc: dict, ctx: dict, briefing_store: dict = None) -> None:
    """
    Save a completed meeting's key learnings to the memory store.
    Keeps only the last MAX_ENTRIES.
    """
    briefing_store = briefing_store or {}

    # Extract target customer from CMO briefing
    cmo_briefing = briefing_store.get("CMO", "")
    target_customer = _extract_target_customer(cmo_briefing)

    # Extract conflict topics
    conflicts = [c.get("topic", "Unknown") for c in ctx.get("conflicts", [])]

    # Extract resolutions
    resolutions = _extract_resolutions(ctx.get("agreed_on", []))

    entry = {
        "product_name": doc.get("product_name", "Unknown"),
        "idea": ctx.get("client_idea", ""),
        "conflicts": conflicts,
        "resolutions": resolutions,
        "target_customer": target_customer,
        "timestamp": datetime.now().isoformat(),
    }

    # Load existing or start fresh
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if MEMORY_PATH.exists():
        try:
            with open(MEMORY_PATH, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, Exception):
            existing = []

    # Append and trim
    existing.append(entry)
    existing = existing[-MAX_ENTRIES:]

    # Write back
    with open(MEMORY_PATH, "w") as f:
        json.dump(existing, f, indent=2)


def _extract_target_customer(cmo_briefing: str) -> str:
    """Extract target customer from CMO briefing text."""
    if not cmo_briefing:
        return "professionals seeking productivity solutions"

    lines = cmo_briefing.split("\n")
    for i, line in enumerate(lines):
        if "TARGET CUSTOMER" in line.upper():
            # Get next non-empty, non-header line
            for next_line in lines[i+1:]:
                next_line = next_line.strip()
                if next_line and not next_line.startswith("#"):
                    return next_line
            break

    return "professionals seeking productivity solutions"


def _extract_resolutions(agreed_on: list) -> list:
    """Extract resolution text from agreed_on list."""
    resolutions = []
    for agreement in agreed_on:
        if "AGREED:" in agreement:
            res = agreement.split("AGREED:", 1)[1].strip()
            resolutions.append(res[:120])
        else:
            resolutions.append(agreement[:120])
    return resolutions
