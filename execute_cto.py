#!/usr/bin/env python3
"""
CTO Execution Agent
Reads board meeting requirements, calls GPT-4o directly to build a
complete HTML product file. No Claude Code CLI required.

Run with: python3 execute_cto.py
"""

import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

RESET = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"
GREEN = "\033[1;32m"
RED   = "\033[1;31m"
AMBER = "\033[33m"
BLUE  = "\033[34m"
WHITE = "\033[1;37m"

def separator(char="─", width=70):
    print(f"{DIM}{char * width}{RESET}")

def step_header(n, title):
    print()
    separator("═", 70)
    print(f"{WHITE}  STEP {n} — {title}{RESET}")
    separator("═", 70)
    print()


# ── Step 1: Read requirements ────────────────────────────────────
def find_latest_outputs():
    outputs_dir = Path("outputs")
    subdirs = [d for d in outputs_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    if subdirs:
        latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        req_files   = list(latest_dir.glob("*_requirements.json"))
        brief_files = list(latest_dir.glob("*_briefings.json"))
        if req_files and brief_files:
            return req_files[0], brief_files[0], latest_dir
    req_path   = outputs_dir / "board_meeting_result.json"
    brief_path = outputs_dir / "agent_briefings.json"
    if req_path.exists() and brief_path.exists():
        return req_path, brief_path, outputs_dir
    return None, None, None


def read_requirements():
    step_header(1, "READ REQUIREMENTS")
    req_path, brief_path, project_dir = find_latest_outputs()
    if not req_path:
        print(f"{RED}✗ No board meeting output found. Run board_meeting.py first.{RESET}")
        sys.exit(1)

    with open(req_path) as f:
        req = json.load(f)
    with open(brief_path) as f:
        brief = json.load(f)

    data = {
        "product_name":          req.get("product_name", "MVP"),
        "description":           req.get("one_sentence_description", ""),
        "technical_requirements": req.get("technical_requirements", []),
        "core_features":         req.get("core_features", []),
        "target_customer":       req.get("target_customer", ""),
        "week_one_execution":    req.get("week_one_execution", ""),
        "cto_briefing":          brief.get("cto_briefing") or brief.get("CTO", ""),
        "project_dir":           project_dir,
    }

    print(f"{GREEN}✓ Product:  {BOLD}{data['product_name']}{RESET}")
    print(f"{GREEN}✓ Features: {len(data['technical_requirements'])} tech requirements{RESET}")
    return data


# ── Step 2: GPT-4o builds the HTML file ─────────────────────────
def build_product_html(data):
    step_header(2, "GPT-4o BUILDS PRODUCT HTML")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"{RED}✗ OPENAI_API_KEY not set in .env{RESET}")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    tech_req_text  = "\n".join(f"  - {r}" for r in data["technical_requirements"])
    feat_text      = "\n".join(f"  - {f}" for f in data["core_features"]) if data["core_features"] else tech_req_text

    system = (
        "You are a world-class senior frontend engineer. "
        "You produce complete, fully working single-file web applications in one HTML file. "
        "The HTML must be self-contained (no external CDN dependencies except Google Fonts if needed), "
        "pixel-perfect, production-quality, and include real interactive functionality — not placeholder text. "
        "Output ONLY the raw HTML. No markdown, no code fences, no explanation."
    )

    user = f"""Build a complete, production-ready single-file web application for:

Product: {data['product_name']}
Description: {data['description']}
Target customer: {data['target_customer']}

Minimum requirements to implement (all must work):
{feat_text}

CTO technical notes:
{data['cto_briefing']}

Design rules:
- Primary color: #0A0A1A (deep navy)
- Accent color:  #F5A04A (amber)
- Clean modern sans-serif typography
- Fully responsive (mobile + desktop)
- Smooth CSS transitions and hover effects

Sections to include:
1. Sticky navbar with product name and nav links
2. Hero section — product name, one-line tagline, CTA button
3. Features section — top 3 features with icons (use unicode/emoji), short descriptions
4. Interactive demo or working core feature (if the product is a tool, make it actually work)
5. Footer with product name and copyright

Output the complete HTML file now. Start with <!DOCTYPE html>."""

    print(f"{AMBER}Calling gpt-4o to build {data['product_name']}...{RESET}")
    print(f"{DIM}This may take 20–60 seconds...{RESET}\n")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.3,
            max_tokens=8000,
        )
        html_content = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"{RED}✗ OpenAI API call failed: {e}{RESET}")
        sys.exit(1)

    # Strip accidental markdown fences if model adds them
    html_content = re.sub(r"^```[a-zA-Z]*\n?", "", html_content)
    html_content = re.sub(r"\n?```$",          "", html_content).strip()

    if not html_content.startswith("<!"):
        print(f"{RED}✗ Model did not return valid HTML. Response preview:{RESET}")
        print(html_content[:300])
        sys.exit(1)

    print(f"{GREEN}✓ HTML generated — {len(html_content):,} characters{RESET}")
    return html_content


# ── Step 3: Save HTML file ───────────────────────────────────────
def save_html(html_content, data):
    step_header(3, "SAVE PRODUCT HTML")

    product_dir = Path("outputs") / data["product_name"].replace(" ", "_")
    product_dir.mkdir(parents=True, exist_ok=True)

    out_path = product_dir / "index.html"
    out_path.write_text(html_content, encoding="utf-8")

    size_kb = len(html_content) / 1024
    print(f"{GREEN}✓ Saved: {out_path}  ({size_kb:.1f} KB){RESET}")
    return out_path


# ── Main ─────────────────────────────────────────────────────────
def main():
    separator("═", 70)
    print(f"{WHITE}{BOLD}   NINGEN CTO — GPT-4o PRODUCT BUILDER{RESET}")
    separator("═", 70)

    data        = read_requirements()
    html        = build_product_html(data)
    out_path    = save_html(html, data)

    print()
    separator("═", 70)
    print(f"{GREEN}{BOLD}  BUILD COMPLETE{RESET}")
    print(f"{GREEN}  Product: {data['product_name']}{RESET}")
    print(f"{GREEN}  File:    {out_path}{RESET}")
    separator("═", 70)


# ── Pipeline wrapper (called by run_all.py / api_server.py) ─────
def run_cto_pipeline() -> dict:
    try:
        data     = read_requirements()
        html     = build_product_html(data)
        out_path = save_html(html, data)
        return {"success": True, "file": str(out_path), "product_name": data["product_name"]}
    except SystemExit:
        return {"success": False, "error": "requirements not found or API error"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    main()
