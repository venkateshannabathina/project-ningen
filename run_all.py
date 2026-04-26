#!/usr/bin/env python3
"""
Ningen Master Script — Run All Execution Phases

Orchestrates the complete startup pipeline in one command:
  python3 run_all.py "your startup idea"
  python3 run_all.py                      # prompts for idea

Runs: Board Meeting → CTO Build → CMO Marketing → COO Ops Plan → CEO Strategy
"""

import sys
import time
from pathlib import Path
from typing import Tuple, Optional, Dict

# ─── ANSI Colors ───────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[1;32m"
RED = "\033[1;31m"
AMBER = "\033[33m"
CYAN = "\033[36m"
WHITE = "\033[1;37m"
DIM = "\033[2m"


def separator(char="─", width=70):
    print(f"{DIM}{char * width}{RESET}")


def phase_header(phase_name):
    print()
    separator("═", 70)
    print(f"{CYAN}{BOLD}  {phase_name}{RESET}")
    separator("═", 70)


# ─── Phase Orchestration ───────────────────────────────────────────────────────
def parse_idea() -> str:
    """Get startup idea from command line or prompt."""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    else:
        idea = input(f"\n{BOLD}Describe your startup idea:{RESET} ").strip()
        if not idea:
            print(f"{RED}✗ No idea provided. Exiting.{RESET}")
            sys.exit(1)
        return idea


def phase_board_meeting(idea: str, memory_context: str = "") -> Optional[Tuple[Dict, Dict, Dict]]:
    """Run board meeting and return (ctx, doc) or None on failure."""
    phase_header("PHASE 1 — BOARD MEETING")

    try:
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

        ctx = initialize_context(idea, memory_context)
        print(f"{AMBER}Round 1 — Opening Positions...{RESET}")
        for msg in api_run_opening_round(ctx):
            pass

        print(f"{AMBER}Client Q&A — Question Generation...{RESET}")
        ctx, q_msgs, questions = api_generate_questions(ctx)

        # Auto-answer for headless mode
        auto_answer = (
            f"The product is {idea}. Target audience is professionals and consumers "
            f"who need this solution. Budget is flexible, timeline is 90 days for MVP. "
            f"No existing infrastructure — building from scratch. Success means active "
            f"engaged users and positive feedback within the first month."
        )
        ctx = api_apply_clarifications(ctx, auto_answer, questions)

        print(f"{AMBER}Round 2 — Reactions...{RESET}")
        for msg in api_run_reaction_round(ctx):
            pass

        print(f"{AMBER}Conflict Detection...{RESET}")
        ctx, conflict_msgs = api_detect_conflicts_return(ctx)

        print(f"{AMBER}Round 3 — Resolution...{RESET}")
        for msg in api_run_resolution_round(ctx):
            pass

        print(f"{AMBER}Final Briefings...{RESET}")
        briefing_store = {}
        for msg in api_run_briefings(ctx):
            briefing_store[msg.get("speaker")] = msg.get("message")

        print(f"{AMBER}Generating Requirements...{RESET}")
        ctx, doc = api_generate_requirements(ctx)

        # Save outputs
        save_briefings(briefing_store, ctx)
        save_output(doc)

        product_name = doc.get("product_name", "Startup MVP")
        print(f"\n{GREEN}✓ Board meeting complete{RESET}")
        print(f"{GREEN}  Product: {product_name}{RESET}")
        print(f"{GREEN}  Conflicts: {len(ctx.get('conflicts', []))} detected, {len(ctx.get('agreed_on', []))} resolved{RESET}")

        return (ctx, doc, briefing_store)

    except Exception as e:
        print(f"{RED}✗ Board meeting failed: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return None


def phase_cto() -> Dict:
    """Run CTO execution."""
    phase_header("PHASE 2 — CTO BUILD")

    try:
        from execute_cto import run_cto_pipeline
        result = run_cto_pipeline()
        if result.get("success"):
            print(f"\n{GREEN}✓ CTO build successful{RESET}")
            print(f"{GREEN}  File: {result.get('file', 'index.html')}{RESET}")
        else:
            print(f"{RED}✗ CTO build failed{RESET}")
        return result
    except Exception as e:
        print(f"{RED}✗ CTO execution error: {e}{RESET}")
        return {"success": False, "error": str(e)}


def phase_cmo() -> dict:
    """Run CMO execution."""
    phase_header("PHASE 3 — CMO MARKETING")

    try:
        from execute_cmo import run_cmo_pipeline
        result = run_cmo_pipeline()
        if result.get("success"):
            print(f"\n{GREEN}✓ CMO marketing complete{RESET}")
            print(f"{GREEN}  Files: {len(result.get('files', []))} marketing pieces{RESET}")
        else:
            print(f"{RED}✗ CMO marketing failed{RESET}")
        return result
    except Exception as e:
        print(f"{RED}✗ CMO execution error: {e}{RESET}")
        return {"success": False, "error": str(e)}


def phase_coo() -> dict:
    """Run COO execution."""
    phase_header("PHASE 4 — COO OPERATIONS")

    try:
        from execute_coo import run_coo_pipeline
        result = run_coo_pipeline()
        if result.get("execution_plan_saved") and result.get("risk_register_saved"):
            print(f"\n{GREEN}✓ COO operations plan complete{RESET}")
            print(f"{GREEN}  Files: execution_plan.md, risk_register.md{RESET}")
        else:
            print(f"{RED}✗ COO operations failed{RESET}")
        return result
    except Exception as e:
        print(f"{RED}✗ COO execution error: {e}{RESET}")
        return {"success": False, "error": str(e)}


def phase_ceo() -> dict:
    """Run CEO execution."""
    phase_header("PHASE 5 — CEO STRATEGY")

    try:
        from execute_ceo import run_ceo_pipeline
        result = run_ceo_pipeline()
        if result.get("investor_pitch_saved") and result.get("executive_summary_saved"):
            print(f"\n{GREEN}✓ CEO strategy documents complete{RESET}")
            print(f"{GREEN}  Files: investor_pitch.md, executive_summary.md{RESET}")
        else:
            print(f"{RED}✗ CEO strategy failed{RESET}")
        return result
    except Exception as e:
        print(f"{RED}✗ CEO execution error: {e}{RESET}")
        return {"success": False, "error": str(e)}


def print_summary_table(results: dict, product_name: str = "Unknown"):
    """Print execution summary table."""
    print()
    separator("═", 70)
    print(f"{WHITE}{BOLD}  RUN ALL COMPLETE — {product_name}{RESET}")
    separator("═", 70)
    print()
    print(f"  {'Phase':<20} {'Status':<12} {'Output':<40}")
    separator("─", 70)

    phases_info = [
        ("Board Meeting", results.get("board_meeting", {}), "requirements.json"),
        ("CTO Build", results.get("cto", {}), "index.html"),
        ("CMO Campaign", results.get("cmo", {}), "4 marketing files"),
        ("COO Operations", results.get("coo", {}), "execution_plan.md"),
        ("CEO Strategy", results.get("ceo", {}), "investor_pitch.md"),
    ]

    for phase_name, result, output_desc in phases_info:
        success = result.get("success", False)
        status = f"{GREEN}✓ Done{RESET}" if success else f"{RED}✗ Failed{RESET}"
        print(f"  {phase_name:<20} {status:<12} {output_desc:<40}")

    print()
    separator("═", 70)


def main():
    """Main orchestration."""
    print()
    separator("═", 70)
    print(f"{WHITE}{BOLD}")
    print("  ██████╗ ██╗          ███████╗██╗  ██╗██████╗")
    print("  ██╔══██╗██║          ██╔════╝╚██╗██╔╝██╔══██╗")
    print("  ██████╔╝██║          █████╗   ╚███╔╝ ██████╔╝")
    print("  ██╔══██╗██║          ██╔══╝   ██╔██╗ ██╔═══╝")
    print("  ██║  ██║███████╗     ███████╗██╔╝ ██╗██║")
    print("  ╚═╝  ╚═╝╚══════╝     ╚══════╝╚═╝  ╚═╝╚═╝")
    print(f"{RESET}")
    print(f"{WHITE}       NINGEN — Full Startup Execution Pipeline{RESET}")
    separator("═", 70)

    # Parse idea
    idea = parse_idea()
    print(f"\n{GREEN}✓ Idea: {idea}{RESET}")

    # Load memory if available
    try:
        from memory_store import load_memory, save_memory
        memory_context = load_memory()
        MEMORY_ENABLED = True
    except ImportError:
        memory_context = ""
        MEMORY_ENABLED = False

    results = {}
    product_name = "Unknown"

    # Phase 1: Board Meeting
    board_result = phase_board_meeting(idea, memory_context)
    if board_result:
        ctx, doc, briefing_store = board_result
        results["board_meeting"] = {"success": True}
        product_name = doc.get("product_name", "Unknown")

        # Save memory if enabled
        if MEMORY_ENABLED:
            try:
                save_memory(doc, ctx, briefing_store)
            except Exception:
                pass

        # Sleep between phases to avoid rate limits
        time.sleep(2)

        # Phases 2-5: All execution agents (continue even if one fails)
        results["cto"] = phase_cto()
        time.sleep(2)

        results["cmo"] = phase_cmo()
        time.sleep(2)

        results["coo"] = phase_coo()
        time.sleep(2)

        results["ceo"] = phase_ceo()
    else:
        results["board_meeting"] = {"success": False}
        print(f"\n{RED}Skipping execution phases due to board meeting failure.{RESET}")

    # Summary
    print_summary_table(results, product_name)


if __name__ == "__main__":
    main()
