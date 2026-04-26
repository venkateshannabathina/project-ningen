#!/usr/bin/env python3
"""
CEO Execution Agent — Strategic Vision & Investor Readiness

Reads board meeting requirements and generates:
1. Investor pitch outline with structured sections
2. Executive summary for board/stakeholders
"""

import os
import sys
import json
from pathlib import Path
from typing import Tuple, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ─── ANSI Colors ───────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[1;32m"
AMBER = "\033[33m"
DIM = "\033[2m"


def separator(char="─", width=70):
    print(f"{DIM}{char * width}{RESET}")


def step_header(step_num, title):
    print(f"\n{BOLD}  Step {step_num}: {title}{RESET}")
    separator("─", 70)


# ─── Core Functions ────────────────────────────────────────────────────────────
def find_latest_outputs() -> Tuple[Optional[Path], Optional[Path]]:
    """Find latest requirements and briefings JSON files."""
    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        return None, None

    subdirs = sorted(outputs_dir.glob("*/"), key=lambda p: p.stat().st_mtime, reverse=True)
    for subdir in subdirs:
        req_file = list(subdir.glob("*_requirements.json"))
        brief_file = list(subdir.glob("*_briefings.json"))
        if req_file and brief_file:
            return req_file[0], brief_file[0]

    return None, None


def read_requirements() -> dict:
    """Read requirements and briefings JSON, extract CEO-relevant fields."""
    req_path, brief_path = find_latest_outputs()
    if not req_path or not brief_path:
        raise FileNotFoundError("No requirements or briefings files found in outputs/")

    with open(req_path) as f:
        requirements = json.load(f)
    with open(brief_path) as f:
        briefings = json.load(f)

    return {
        "product_name": requirements.get("product_name", "Startup MVP"),
        "description": requirements.get("one_sentence_description", ""),
        "technical_requirements": requirements.get("technical_requirements", []),
        "go_to_market": requirements.get("go_to_market", []),
        "resolved_conflicts": requirements.get("resolved_conflicts", []),
        "ceo_briefing": briefings.get("ceo_briefing", ""),
    }


def generate_ceo_documents(data: dict) -> dict:
    """Generate investor pitch and executive summary via GPT-4o-mini."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)

    base_context = f"""Product: {data['product_name']}
Description: {data['description']}

Key Technical Approaches:
{chr(10).join('- ' + t for t in data['technical_requirements'][:3])}

Go-To-Market Strategy:
{chr(10).join('- ' + g for g in data['go_to_market'])}

CEO Briefing: {data['ceo_briefing']}

Resolved Conflicts: {chr(10).join('- ' + c for c in data['resolved_conflicts'])}"""

    # Call 1: Investor Pitch
    step_header(1, "Generating Investor Pitch")
    pitch_prompt = f"""You are a CEO preparing a seed-stage investor pitch. You lead with the problem, not the product.
You know that investors fund teams and markets, not features.
{base_context}

Generate a markdown pitch with these exact H2 sections:
## Problem
## Solution
## Market
## Traction
## The Ask

Each section should be 2-3 bullet points. End with a one-line CTA.
Be specific, use numbers where possible, show conviction."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.75,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": "You are a compelling CEO pitching to investors."},
                {"role": "user", "content": pitch_prompt},
            ],
        )
        investor_pitch = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"{AMBER}Warning: investor pitch generation failed: {e}{RESET}")
        investor_pitch = "# Investor Pitch (Generation Failed)\n\nPlease review requirements manually."

    # Call 2: Executive Summary
    step_header(2, "Generating Executive Summary")
    summary_prompt = f"""You are a CEO writing a 1-page strategic briefing for your board of directors.
It is precise, uses specific numbers and dates, and contains no filler words.
{base_context}

Generate a markdown document with these exact H2 sections:
## North Star
## 90-Day Milestones
## Key Risks
## Decision Log

Include:
- North Star: one specific metric (e.g., 10k active users by end of Q2)
- 90-Day Milestones: 3 milestones with target dates
- Key Risks: top 3 risks with owners
- Decision Log: key decisions extracted from resolved conflicts

Be precise. Use dates. Be honest about risks."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=900,
            messages=[
                {"role": "system", "content": "You are a CEO writing a strategic board briefing."},
                {"role": "user", "content": summary_prompt},
            ],
        )
        executive_summary = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"{AMBER}Warning: executive summary generation failed: {e}{RESET}")
        executive_summary = "# Executive Summary (Generation Failed)\n\nPlease review requirements manually."

    return {
        "investor_pitch": investor_pitch,
        "executive_summary": executive_summary,
    }


def save_documents(content: dict) -> None:
    """Save generated documents to outputs/."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    # Investor pitch
    step_header(3, "Saving Investor Pitch")
    pitch_path = outputs_dir / "investor_pitch.md"
    pitch_path.write_text(content["investor_pitch"], encoding="utf-8")
    print(f"{GREEN}✓ Saved to {pitch_path}{RESET}")

    # Executive summary
    step_header(4, "Saving Executive Summary")
    summary_path = outputs_dir / "executive_summary.md"
    summary_path.write_text(content["executive_summary"], encoding="utf-8")
    print(f"{GREEN}✓ Saved to {summary_path}{RESET}")


def run_ceo_pipeline() -> dict:
    """Run full CEO pipeline. Returns success status."""
    try:
        data = read_requirements()
        content = generate_ceo_documents(data)
        save_documents(content)
        return {
            "investor_pitch_saved": (Path("outputs") / "investor_pitch.md").exists(),
            "executive_summary_saved": (Path("outputs") / "executive_summary.md").exists(),
        }
    except Exception as e:
        print(f"{AMBER}CEO pipeline error: {e}{RESET}")
        return {"investor_pitch_saved": False, "executive_summary_saved": False, "error": str(e)}


def main():
    """Standalone entry point."""
    print()
    separator("═", 70)
    print(f"{BOLD}  CEO EXECUTION AGENT — Strategic Vision & Pitch{RESET}")
    separator("═", 70)

    try:
        data = read_requirements()
        print(f"\n{GREEN}✓ Loaded requirements for: {data['product_name']}{RESET}")

        content = generate_ceo_documents(data)
        save_documents(content)

        print(f"\n{BOLD}✓ CEO execution complete{RESET}")
        print(f"  • Investor pitch: outputs/investor_pitch.md")
        print(f"  • Executive summary: outputs/executive_summary.md")

    except Exception as e:
        print(f"\n{BOLD}✗ CEO execution failed: {e}{RESET}")
        sys.exit(1)

    separator("═", 70)


if __name__ == "__main__":
    main()
