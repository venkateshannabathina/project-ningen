#!/usr/bin/env python3
"""
COO Execution Agent — Operational Planning & Risk Management

Reads board meeting requirements and generates:
1. Detailed week-one execution plan with task breakdown
2. Risk register with severity/likelihood assessment
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
    """Read requirements and briefings JSON, extract COO-relevant fields."""
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
        "week_one_execution": requirements.get("week_one_execution", []),
        "resolved_conflicts": requirements.get("resolved_conflicts", []),
        "open_questions": requirements.get("open_questions", []),
        "coo_briefing": briefings.get("coo_briefing", ""),
    }


def generate_coo_documents(data: dict) -> dict:
    """Generate execution plan and risk register via GPT-4o-mini."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)

    base_context = f"""Product: {data['product_name']}
Description: {data['description']}

Week One High-Level Tasks:
{chr(10).join('- ' + t for t in data['week_one_execution'])}

COO Briefing: {data['coo_briefing']}

Resolved Conflicts: {chr(10).join('- ' + c for c in data['resolved_conflicts'])}

Open Questions: {chr(10).join('- ' + q for q in data['open_questions'])}"""

    # Call 1: Execution Plan
    step_header(1, "Generating Week-One Execution Plan")
    plan_prompt = f"""You are a world-class COO turning a vague task list into an airtight execution plan.
{base_context}

Generate a detailed execution plan broken down by day. Format as markdown with H2 headers for each day/segment (Days 1-2, Days 3-4, Days 5-7).
For each task, include:
- Task name
- Owner (CEO/CTO/CMO/COO)
- Dependency (if any)
- Success criterion

Be specific and operational. No vague language."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": "You are a world-class COO."},
                {"role": "user", "content": plan_prompt},
            ],
        )
        execution_plan = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"{AMBER}Warning: execution plan generation failed: {e}{RESET}")
        execution_plan = "# Execution Plan (Generation Failed)\n\nPlease review requirements manually."

    # Call 2: Risk Register
    step_header(2, "Generating Risk Register")
    risk_prompt = f"""You are a COO building a risk register. You think in impact × likelihood. You are brutally honest.
{base_context}

Generate a markdown table of the top 5 risks for this product launch. Table format:
| # | Risk | Severity | Likelihood | Mitigation | Owner |

Severity: HIGH/MEDIUM/LOW
Likelihood: HIGH/MEDIUM/LOW
Mitigation: One concrete action
Owner: CEO/CTO/CMO/COO

Be specific. Name actual failure modes, not generalities."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=800,
            messages=[
                {"role": "system", "content": "You are a COO."},
                {"role": "user", "content": risk_prompt},
            ],
        )
        risk_register = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"{AMBER}Warning: risk register generation failed: {e}{RESET}")
        risk_register = "| # | Risk | Severity | Likelihood | Mitigation | Owner |\n|---|---|---|---|---|---|\n| 1 | (Risk register generation failed) | HIGH | HIGH | Manual review | COO |"

    return {
        "execution_plan": execution_plan,
        "risk_register": risk_register,
    }


def save_documents(content: dict) -> None:
    """Save generated documents to outputs/."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    # Execution plan
    step_header(3, "Saving Execution Plan")
    plan_path = outputs_dir / "execution_plan.md"
    plan_path.write_text(content["execution_plan"], encoding="utf-8")
    print(f"{GREEN}✓ Saved to {plan_path}{RESET}")

    # Risk register
    step_header(4, "Saving Risk Register")
    risk_path = outputs_dir / "risk_register.md"
    risk_path.write_text(content["risk_register"], encoding="utf-8")
    print(f"{GREEN}✓ Saved to {risk_path}{RESET}")


def run_coo_pipeline() -> dict:
    """Run full COO pipeline. Returns success status."""
    try:
        data = read_requirements()
        content = generate_coo_documents(data)
        save_documents(content)
        return {
            "execution_plan_saved": (Path("outputs") / "execution_plan.md").exists(),
            "risk_register_saved": (Path("outputs") / "risk_register.md").exists(),
        }
    except Exception as e:
        print(f"{AMBER}COO pipeline error: {e}{RESET}")
        return {"execution_plan_saved": False, "risk_register_saved": False, "error": str(e)}


def main():
    """Standalone entry point."""
    print()
    separator("═", 70)
    print(f"{BOLD}  COO EXECUTION AGENT — Operational Planning{RESET}")
    separator("═", 70)

    try:
        data = read_requirements()
        print(f"\n{GREEN}✓ Loaded requirements for: {data['product_name']}{RESET}")

        content = generate_coo_documents(data)
        save_documents(content)

        print(f"\n{BOLD}✓ COO execution complete{RESET}")
        print(f"  • Execution plan: outputs/execution_plan.md")
        print(f"  • Risk register: outputs/risk_register.md")

    except Exception as e:
        print(f"\n{BOLD}✗ COO execution failed: {e}{RESET}")
        sys.exit(1)

    separator("═", 70)


if __name__ == "__main__":
    main()
