#!/usr/bin/env python3
"""
Ningen — AI Board Meeting System
Terminal-only CLI interface
Run: venv/bin/python dashboard/app.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
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

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_speaker(speaker, role):
    print(f"\n[{speaker} — {role}]")

def main():
    print("\n" + "="*80)
    print("  NINGEN — AI Board Meeting System")
    print("="*80 + "\n")

    # Phase 1: Get idea from user
    print("Describe your startup idea:")
    print("(What problem does it solve? Who are your users?)\n")
    idea = input("> ").strip()

    if not idea:
        print("No idea provided. Exiting.")
        return

    print_section("INITIALIZING BOARD MEETING")

    # Initialize context
    ctx = initialize_context(idea)
    print(f"✓ Idea registered: {idea}\n")

    # Phase 1: Opening Round
    print_section("ROUND 1 — OPENING POSITIONS")

    for md in api_run_opening_round(ctx):
        spk = md.get("speaker", "")
        role = md.get("role", "")
        msg = md.get("message", "")
        print_speaker(spk, role)
        print(msg)

    # Phase 1: Questions
    print_section("CLIENT QUESTIONS ROUND")

    ctx, q_msgs, questions = api_generate_questions(ctx)

    for md in q_msgs:
        spk = md.get("speaker", "")
        role = md.get("role", "")
        msg = md.get("message", "")
        print_speaker(spk, role)
        print(msg)

    # Phase 1: Get client answers
    print_section("YOUR TURN")
    print("Answer all four questions above in a single response:\n")
    answer = input("> ").strip()

    if not answer:
        print("No answer provided. Exiting.")
        return

    ctx = api_apply_clarifications(ctx, answer, questions)
    print("\n✓ Answers recorded.\n")

    # Phase 2: Reaction Round
    print_section("ROUND 2 — REACTIONS")

    for md in api_run_reaction_round(ctx):
        spk = md.get("speaker", "")
        role = md.get("role", "")
        msg = md.get("message", "")
        print_speaker(spk, role)
        print(msg)

    # Phase 2: Conflict Detection
    print_section("CONFLICT DETECTION")

    ctx, conflict_msgs = api_detect_conflicts_return(ctx)

    for cm in conflict_msgs:
        spk = cm.get("speaker", "")
        msg = cm.get("message", "")
        if spk:
            print_speaker(spk, "")
            print(msg)
        else:
            print(msg)

    # Phase 2: Resolution Round
    print_section("ROUND 3 — CONFLICT RESOLUTION")

    for md in api_run_resolution_round(ctx):
        spk = md.get("speaker", "")
        role = md.get("role", "")
        msg = md.get("message", "")
        print_speaker(spk, role)
        print(msg)

    # Phase 2: Briefings
    print_section("FINAL AGENT BRIEFINGS")

    briefing_store = {}
    for md in api_run_briefings(ctx):
        spk = md.get("speaker", "")
        role = md.get("role", "")
        msg = md.get("message", "")
        print_speaker(spk, role)
        print(msg)
        briefing_store[spk] = msg

    save_briefings(briefing_store, ctx)

    # Phase 2: Requirements Document
    print_section("REQUIREMENTS DOCUMENT")

    ctx, doc = api_generate_requirements(ctx)
    save_output(doc)

    # Print final document
    print(f"Product Name: {doc.get('product_name', 'N/A')}")
    print(f"Description: {doc.get('one_sentence_description', 'N/A')}\n")

    print("Technical Requirements:")
    for req in doc.get("technical_requirements", []):
        print(f"  • {req}")

    print("\nGo-To-Market:")
    for gtm in doc.get("go_to_market", []):
        print(f"  • {gtm}")

    print("\nWeek One Execution:")
    for task in doc.get("week_one_execution", []):
        print(f"  • {task}")

    if doc.get("resolved_conflicts"):
        print("\nResolved Conflicts:")
        for conf in doc.get("resolved_conflicts", []):
            print(f"  ✓ {conf}")

    if doc.get("open_questions"):
        print("\nOpen Questions:")
        for q in doc.get("open_questions", []):
            print(f"  ? {q}")

    print(f"\nNext Step: {doc.get('next_step', 'N/A')}")

    out_path = str(Path("outputs/board_meeting_result.json").resolve())
    print(f"\n✓ Full results saved to: {out_path}")

    print_section("BOARD MEETING COMPLETE")
    print("All agents briefed and ready to execute.\n")

if __name__ == "__main__":
    main()
