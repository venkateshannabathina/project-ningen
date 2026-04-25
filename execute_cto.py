#!/usr/bin/env python3
"""
CTO Execution Agent
Reads board meeting outputs, generates a Claude Code prompt via GPT-4o-mini,
runs Claude Code CLI to build the product, and pushes to GitHub.

Run with: python3 execute_cto.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ─── ANSI Colors ───────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[1;32m"
RED    = "\033[1;31m"
AMBER  = "\033[33m"
BLUE   = "\033[34m"
WHITE  = "\033[1;37m"


def separator(char="─", width=70):
    print(f"{DIM}{char * width}{RESET}")


def step_header(step_num, title):
    print()
    separator("═", 70)
    print(f"{WHITE}  STEP {step_num} — {title}{RESET}")
    separator("═", 70)
    print()


# ─── Step 1: Read Requirements ─────────────────────────────────────────────────
def find_latest_outputs():
    """Find the most recent board meeting output files.
    Checks project subdirectories first (new format), falls back to root outputs/.
    """
    outputs_dir = Path("outputs")

    # Check for project subdirectories (new format: outputs/<ProjectName>/)
    subdirs = [d for d in outputs_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    if subdirs:
        # Use the most recently modified subdirectory
        latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        # Find requirements and briefings files in that directory
        req_files = list(latest_dir.glob("*_requirements.json"))
        brief_files = list(latest_dir.glob("*_briefings.json"))
        if req_files and brief_files:
            return req_files[0], brief_files[0], latest_dir
        
    # Fallback to old format at outputs/ root
    req_path = outputs_dir / "board_meeting_result.json"
    brief_path = outputs_dir / "agent_briefings.json"
    if req_path.exists() and brief_path.exists():
        return req_path, brief_path, outputs_dir

    return None, None, None


def read_requirements():
    step_header(1, "READ REQUIREMENTS")

    req_path, brief_path, project_dir = find_latest_outputs()

    if not req_path or not brief_path:
        print(f"{RED}✗ Could not find board meeting output files in outputs/{RESET}")
        print(f"{RED}  Run board_meeting.py first to generate outputs.{RESET}")
        sys.exit(1)

    print(f"{AMBER}Reading: {req_path}{RESET}")
    with open(req_path, "r") as f:
        requirements = json.load(f)

    print(f"{AMBER}Reading: {brief_path}{RESET}")
    with open(brief_path, "r") as f:
        briefings = json.load(f)

    product_name = requirements.get("product_name", "Startup MVP")
    description = requirements.get("one_sentence_description", "")
    tech_requirements = requirements.get("technical_requirements", [])
    cto_briefing = briefings.get("cto_briefing", "")

    print(f"\n{GREEN}✓ Product Name: {BOLD}{product_name}{RESET}")
    print(f"{GREEN}✓ Description: {description[:100]}...{RESET}")
    print(f"{GREEN}✓ Tech Requirements: {len(tech_requirements)} items{RESET}")
    print(f"{GREEN}✓ CTO Briefing: {len(cto_briefing)} characters{RESET}")

    return {
        "product_name": product_name,
        "description": description,
        "technical_requirements": tech_requirements,
        "cto_briefing": cto_briefing,
        "project_dir": project_dir,
    }


# ─── Step 2: Generate Claude Code Prompt ────────────────────────────────────────
def generate_claude_prompt(data):
    step_header(2, "CTO GENERATES CLAUDE CODE PROMPT")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"{RED}✗ OPENAI_API_KEY not set in .env{RESET}")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    tech_req_text = "\n".join(f"  - {r}" for r in data["technical_requirements"])

    system_prompt = (
        "You are a world class CTO. Your job is to write the perfect prompt for Claude Code "
        "to build a complete working web application. You write prompts that are so detailed "
        "and structured that Claude Code can build the entire product without asking a single "
        "question. You always specify exact colors, exact file structure, exact features, exact "
        "interactions. You never leave anything ambiguous."
    )

    user_prompt = f"""Based on these requirements build a complete Claude Code prompt.

Product name: {data['product_name']}
Description: {data['description']}
Technical requirements:
{tech_req_text}
CTO briefing:
{data['cto_briefing']}

Write a Claude Code prompt that instructs it to build a complete single page web application for this product. The prompt must include: exact file structure, exact color scheme using navy #0A0A1A and amber #F5A04A as primary colors, hero section with product name and tagline, features section showing the top three features from the requirements, call to action section, footer with product name, fully responsive design, clean modern CSS, no external dependencies, everything in one HTML file. End the prompt with: save everything to a single file called index.html."""

    print(f"{AMBER}Calling GPT-4o-mini to generate Claude Code prompt...{RESET}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        prompt_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"{RED}✗ OpenAI API call failed: {e}{RESET}")
        sys.exit(1)

    # Save prompt to outputs/
    prompt_path = Path("outputs") / "cto_claude_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(prompt_path, "w") as f:
        f.write(prompt_text)

    print(f"\n{GREEN}✓ Prompt saved to: {prompt_path}{RESET}")
    separator("─", 70)
    print(f"\n{BLUE}{prompt_text}{RESET}\n")
    separator("─", 70)

    return prompt_text, prompt_path


# ─── Step 3: Run Claude Code CLI ────────────────────────────────────────────────
def run_claude_code(prompt_path):
    step_header(3, "RUN CLAUDE CODE CLI")

    with open(prompt_path, "r") as f:
        prompt = f.read()

    print(f"{AMBER}Running: claude -p <prompt> (in ./outputs){RESET}")
    print(f"{DIM}This may take a minute...{RESET}\n")

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            cwd="./outputs",
        )

        if result.stdout:
            print(f"{GREEN}--- Claude Code stdout ---{RESET}")
            print(result.stdout)

        if result.stderr:
            print(f"{AMBER}--- Claude Code stderr ---{RESET}")
            print(result.stderr)

        if result.returncode != 0:
            print(f"\n{RED}✗ Claude Code exited with code {result.returncode}{RESET}")
            print(f"{RED}  The prompt has been saved to {prompt_path}{RESET}")
            print(f"{RED}  You can run it manually with:{RESET}")
            print(f"{RED}    cd outputs && claude -p \"$(cat ../outputs/cto_claude_prompt.txt)\"{RESET}")
            return False

        # Verify index.html was created
        index_path = Path("outputs") / "index.html"
        if index_path.exists():
            size = index_path.stat().st_size
            print(f"\n{GREEN}✓ index.html created ({size:,} bytes){RESET}")
            return True
        else:
            print(f"\n{RED}✗ index.html was not created by Claude Code{RESET}")
            print(f"{RED}  The prompt has been saved to {prompt_path}{RESET}")
            print(f"{RED}  You can run it manually with:{RESET}")
            print(f"{RED}    cd outputs && claude -p \"$(cat ../outputs/cto_claude_prompt.txt)\"{RESET}")
            return False

    except FileNotFoundError:
        print(f"{RED}✗ 'claude' CLI not found. Install Claude Code first:{RESET}")
        print(f"{RED}    npm install -g @anthropic-ai/claude-code{RESET}")
        print(f"\n{AMBER}The prompt has been saved to {prompt_path}{RESET}")
        print(f"{AMBER}You can run it manually once Claude Code is installed.{RESET}")
        return False
    except Exception as e:
        print(f"{RED}✗ Error running Claude Code: {e}{RESET}")
        print(f"\n{AMBER}The prompt has been saved to {prompt_path}{RESET}")
        return False


# ─── Step 4: Push to GitHub ──────────────────────────────────────────────────────
def push_to_github(product_name):
    step_header(4, "PUSH TO GITHUB")

    commands = [
        ["git", "add", "outputs/index.html"],
        ["git", "commit", "-m", f"CTO agent built product: {product_name}"],
        ["git", "push", "origin", "main"],
    ]

    for cmd in commands:
        cmd_str = " ".join(cmd)
        print(f"{AMBER}Running: {cmd_str}{RESET}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=".",
            )

            if result.stdout:
                print(f"{DIM}{result.stdout.strip()}{RESET}")
            if result.stderr:
                print(f"{DIM}{result.stderr.strip()}{RESET}")

            if result.returncode != 0:
                print(f"{RED}✗ Command failed: {cmd_str}{RESET}")
                return False

            print(f"{GREEN}✓ Done{RESET}\n")

        except Exception as e:
            print(f"{RED}✗ Error running '{cmd_str}': {e}{RESET}")
            return False

    # Get the remote URL for display
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        remote_url = result.stdout.strip()
        print(f"{GREEN}✓ GitHub URL: {remote_url}{RESET}")
    except Exception:
        print(f"{GREEN}✓ Pushed to origin/main{RESET}")

    return True


# ─── Main ───────────────────────────────────────────────────────────────────────
def main():
    separator("═", 70)
    print(f"{WHITE}{BOLD}")
    print("   ██████╗████████╗ ██████╗     ███████╗██╗  ██╗███████╗ ██████╗")
    print("  ██╔════╝╚══██╔══╝██╔═══██╗    ██╔════╝╚██╗██╔╝██╔════╝██╔════╝")
    print("  ██║        ██║   ██║   ██║    █████╗   ╚███╔╝ █████╗  ██║     ")
    print("  ██║        ██║   ██║   ██║    ██╔══╝   ██╔██╗ ██╔══╝  ██║     ")
    print("  ╚██████╗   ██║   ╚██████╔╝    ███████╗██╔╝ ██╗███████╗╚██████╗")
    print("   ╚═════╝   ╚═╝    ╚═════╝     ╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝")
    print(f"{RESET}")
    print(f"{WHITE}              CTO EXECUTION AGENT — project ningen{RESET}")
    separator("═", 70)

    # Step 1: Read requirements
    data = read_requirements()
    product_name = data["product_name"]

    # Step 2: Generate Claude Code prompt
    prompt_text, prompt_path = generate_claude_prompt(data)

    # Step 3: Run Claude Code CLI
    claude_success = run_claude_code(prompt_path)

    # Step 4: Push to GitHub (only if Claude Code succeeded)
    if claude_success:
        push_to_github(product_name)
    else:
        print(f"\n{AMBER}⚠ Skipping GitHub push — Claude Code did not produce index.html{RESET}")
        print(f"{AMBER}  Run the prompt manually, then push with:{RESET}")
        print(f"{AMBER}    git add outputs/index.html && git commit -m 'CTO built {product_name}' && git push origin main{RESET}")

    # Final summary
    print()
    separator("═", 70)
    print(f"{GREEN}{BOLD}  CTO EXECUTION COMPLETE{RESET}")
    print(f"{GREEN}  Product built: {product_name}{RESET}")
    print(f"{GREEN}  File saved: outputs/index.html{RESET}")
    if claude_success:
        print(f"{GREEN}  GitHub: pushed to origin main{RESET}")
    else:
        print(f"{AMBER}  GitHub: pending (run Claude Code manually first){RESET}")
    separator("═", 70)


if __name__ == "__main__":
    main()
