#!/usr/bin/env python3
"""
CMO Execution Agent
Reads board meeting outputs, generates four pieces of marketing content via GPT-4o-mini,
and publishes them to Resend (email), Dev.to, Discord, and saves locally.

Run with: python3 execute_cmo.py
"""

import os
import sys
import json
import requests
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
CORAL  = "\033[31m"
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
    """Find the most recent board meeting output files."""
    outputs_dir = Path("outputs")

    # Check for project subdirectories (new format)
    subdirs = [d for d in outputs_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    if subdirs:
        latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        req_files = list(latest_dir.glob("*_requirements.json"))
        brief_files = list(latest_dir.glob("*_briefings.json"))
        if req_files and brief_files:
            return req_files[0], brief_files[0]

    # Fallback to old format
    req_path = outputs_dir / "board_meeting_result.json"
    brief_path = outputs_dir / "agent_briefings.json"
    if req_path.exists() and brief_path.exists():
        return req_path, brief_path

    return None, None


def read_requirements():
    step_header(1, "READ REQUIREMENTS")

    req_path, brief_path = find_latest_outputs()

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
    go_to_market = requirements.get("go_to_market", [])
    tech_requirements = requirements.get("technical_requirements", [])
    cmo_briefing = briefings.get("cmo_briefing", "")

    # Extract target customer from CMO briefing
    target_customer = ""
    for line in cmo_briefing.split("\n"):
        if "TARGET CUSTOMER" in line.upper():
            # Grab the next non-empty line as the customer description
            idx = cmo_briefing.find(line)
            remaining = cmo_briefing[idx + len(line):].strip()
            for next_line in remaining.split("\n"):
                next_line = next_line.strip()
                if next_line and not next_line.startswith("#"):
                    target_customer = next_line
                    break
            break

    if not target_customer:
        target_customer = "busy professionals seeking productivity solutions"

    print(f"\n{GREEN}✓ Product Name: {BOLD}{product_name}{RESET}")
    print(f"{GREEN}✓ Description: {description[:100]}...{RESET}")
    print(f"{GREEN}✓ Target Customer: {target_customer[:100]}...{RESET}")
    print(f"{GREEN}✓ Go-To-Market: {len(go_to_market)} items{RESET}")
    print(f"{GREEN}✓ CMO Briefing: {len(cmo_briefing)} characters{RESET}")

    return {
        "product_name": product_name,
        "description": description,
        "go_to_market": go_to_market,
        "tech_requirements": tech_requirements,
        "target_customer": target_customer,
        "cmo_briefing": cmo_briefing,
    }


# ─── Step 2: Generate Marketing Content ─────────────────────────────────────────
def generate_content(data):
    step_header(2, "CMO GENERATES MARKETING CONTENT")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"{RED}✗ OPENAI_API_KEY not set in .env{RESET}")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    gtm_text = "\n".join(f"  - {g}" for g in data["go_to_market"])
    tech_text = "\n".join(f"  - {r}" for r in data["tech_requirements"])

    base_context = f"""Product: {data['product_name']}
Description: {data['description']}
Target Customer: {data['target_customer']}
Go-To-Market Plan:
{gtm_text}
Key Features:
{tech_text}
CMO Briefing:
{data['cmo_briefing']}"""

    content = {}

    # ── Content 1: Cold Email ────────────────────────────────────────────────
    print(f"{AMBER}Generating cold email...{RESET}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are an expert B2B cold email copywriter. You write short, personal, "
                    "specific emails that get replies. No fluff. No corporate speak. You sound "
                    "like a real person who genuinely wants to help."
                )},
                {"role": "user", "content": f"""Write a cold email for this product.

{base_context}

Write the email with:
- A compelling subject line
- A personal, specific body that speaks directly to the target customer's pain point
- A clear call to action
- Keep it under 200 words

Format as:
Subject: [subject line]

[body]"""}
            ],
            temperature=0.8,
            max_tokens=500,
        )
        content["cold_email"] = response.choices[0].message.content.strip()
        print(f"{GREEN}✓ Cold email generated{RESET}")
    except Exception as e:
        print(f"{RED}✗ Failed to generate cold email: {e}{RESET}")
        content["cold_email"] = None

    # ── Content 2: Dev.to Article ────────────────────────────────────────────
    print(f"{AMBER}Generating Dev.to article...{RESET}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a technical writer who creates engaging, professional articles "
                    "for Dev.to. You write clear, helpful content that developers and tech "
                    "professionals actually want to read. You use markdown formatting."
                )},
                {"role": "user", "content": f"""Write a full Dev.to article about this product.

{base_context}

The article must include:
- A catchy tagline at the top
- An introduction explaining the problem
- Three detailed sections covering the solution, key features, and technical approach
- A conclusion with a call to action
- Minimum 500 words
- Professional but approachable tone
- Use markdown formatting (headers, bold, bullet points)
- Do NOT include a title line — just start with the tagline and content"""}
            ],
            temperature=0.7,
            max_tokens=1500,
        )
        content["devto_article"] = response.choices[0].message.content.strip()
        print(f"{GREEN}✓ Dev.to article generated{RESET}")
    except Exception as e:
        print(f"{RED}✗ Failed to generate Dev.to article: {e}{RESET}")
        content["devto_article"] = None

    # ── Content 3: Discord Announcement ──────────────────────────────────────
    print(f"{AMBER}Generating Discord announcement...{RESET}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a community manager writing exciting product launch announcements "
                    "for Discord. You're energetic, use emoji, and keep things punchy and fun."
                )},
                {"role": "user", "content": f"""Write a Discord announcement for this product launch.

{base_context}

Include:
- Product name in bold
- One line description
- Top three features as bullet points with emoji
- A call to action
- Keep it under 300 words
- Use Discord markdown formatting"""}
            ],
            temperature=0.85,
            max_tokens=500,
        )
        content["discord_post"] = response.choices[0].message.content.strip()
        print(f"{GREEN}✓ Discord announcement generated{RESET}")
    except Exception as e:
        print(f"{RED}✗ Failed to generate Discord announcement: {e}{RESET}")
        content["discord_post"] = None

    # ── Content 4: Reddit Post ───────────────────────────────────────────────
    print(f"{AMBER}Generating Reddit-style post...{RESET}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a regular Reddit user sharing something genuinely helpful. "
                    "You're not selling anything. You're sharing your experience with a "
                    "problem and what you found that helped. Natural, conversational, honest."
                )},
                {"role": "user", "content": f"""Write a Reddit-style post about the problem this product solves.

{base_context}

Rules:
- Write like a real person sharing something useful
- Start by describing the problem from personal experience
- Share what you tried before
- Mention the product naturally near the end as something you found
- NOT salesy at all — reads like genuine advice
- Include a post title
- Keep it authentic and helpful

Format as:
Title: [title]

[body]"""}
            ],
            temperature=0.9,
            max_tokens=600,
        )
        content["reddit_post"] = response.choices[0].message.content.strip()
        print(f"{GREEN}✓ Reddit post generated{RESET}")
    except Exception as e:
        print(f"{RED}✗ Failed to generate Reddit post: {e}{RESET}")
        content["reddit_post"] = None

    return content


# ─── Step 3: Save Content to Files ──────────────────────────────────────────────
def save_content(content):
    step_header(3, "SAVE CONTENT TO FILES")

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    file_map = {
        "cold_email": "cold_email.md",
        "devto_article": "devto_article.md",
        "discord_post": "discord_post.md",
        "reddit_post": "reddit_post.md",
    }

    for key, filename in file_map.items():
        if content.get(key):
            path = outputs_dir / filename
            with open(path, "w") as f:
                f.write(content[key])
            print(f"{GREEN}✓ Saved: {path}{RESET}")
        else:
            print(f"{RED}✗ Skipped {filename} (content generation failed){RESET}")


# ─── Step 4: Publish Content ────────────────────────────────────────────────────
def publish_content(content, data):
    step_header(4, "PUBLISH CONTENT")

    results = {
        "email_sent": False,
        "devto_url": None,
        "discord_sent": False,
    }

    # ── Resend Email ─────────────────────────────────────────────────────────
    print(f"{CORAL}{BOLD}▌ RESEND — Cold Email{RESET}")
    separator("─", 60)

    resend_api_key = os.getenv("RESEND_API_KEY")
    resend_from = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    resend_to = os.getenv("RESEND_SUBSCRIBER_EMAILS", "")

    if not resend_api_key:
        print(f"{RED}✗ RESEND_API_KEY not set in .env — skipping email{RESET}")
    elif not resend_to:
        print(f"{RED}✗ RESEND_SUBSCRIBER_EMAILS not set in .env — skipping email{RESET}")
    elif not content.get("cold_email"):
        print(f"{RED}✗ Cold email content not available — skipping{RESET}")
    else:
        # Parse subject and body from the generated email
        email_text = content["cold_email"]
        subject = data["product_name"] + " — Launch Announcement"
        body = email_text

        if email_text.startswith("Subject:"):
            lines = email_text.split("\n", 1)
            subject = lines[0].replace("Subject:", "").strip()
            body = lines[1].strip() if len(lines) > 1 else email_text

        # Split subscriber emails
        to_emails = [e.strip() for e in resend_to.split(",") if e.strip()]

        print(f"{AMBER}Sending to: {', '.join(to_emails)}{RESET}")

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": resend_from,
                    "to": to_emails,
                    "subject": subject,
                    "text": body,
                },
                timeout=15,
            )

            if response.status_code in (200, 201):
                resp_data = response.json()
                print(f"{GREEN}✓ Email sent! ID: {resp_data.get('id', 'unknown')}{RESET}")
                results["email_sent"] = True
                results["email_to"] = ", ".join(to_emails)
            else:
                print(f"{RED}✗ Resend API error ({response.status_code}): {response.text}{RESET}")
        except Exception as e:
            print(f"{RED}✗ Resend request failed: {e}{RESET}")

    print()

    # ── Dev.to Article ───────────────────────────────────────────────────────
    print(f"{BLUE}{BOLD}▌ DEV.TO — Technical Article{RESET}")
    separator("─", 60)

    devto_api_key = os.getenv("DEVTO_API_KEY")

    if not devto_api_key:
        print(f"{RED}✗ DEVTO_API_KEY not set in .env — skipping Dev.to{RESET}")
    elif not content.get("devto_article"):
        print(f"{RED}✗ Dev.to article content not available — skipping{RESET}")
    else:
        title = f"{data['product_name']} — Launch"
        print(f"{AMBER}Publishing: {title}{RESET}")

        try:
            response = requests.post(
                "https://dev.to/api/articles",
                headers={
                    "api-key": devto_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "article": {
                        "title": title,
                        "body_markdown": content["devto_article"],
                        "published": True,
                        "tags": ["ai", "startup", "technology"],
                    }
                },
                timeout=15,
            )

            if response.status_code in (200, 201):
                resp_data = response.json()
                article_url = resp_data.get("url", "")
                print(f"{GREEN}✓ Article published! URL: {article_url}{RESET}")
                results["devto_url"] = article_url
            else:
                print(f"{RED}✗ Dev.to API error ({response.status_code}): {response.text}{RESET}")
        except Exception as e:
            print(f"{RED}✗ Dev.to request failed: {e}{RESET}")

    print()

    # ── Discord Webhook ──────────────────────────────────────────────────────
    print(f"{AMBER}{BOLD}▌ DISCORD — Announcement{RESET}")
    separator("─", 60)

    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")

    if not discord_webhook:
        print(f"{RED}✗ DISCORD_WEBHOOK_URL not set in .env — skipping Discord{RESET}")
    elif not content.get("discord_post"):
        print(f"{RED}✗ Discord content not available — skipping{RESET}")
    else:
        print(f"{AMBER}Sending to Discord webhook...{RESET}")

        try:
            response = requests.post(
                discord_webhook,
                json={"content": content["discord_post"]},
                timeout=15,
            )

            if response.status_code in (200, 204):
                print(f"{GREEN}✓ Discord message sent!{RESET}")
                results["discord_sent"] = True
            else:
                print(f"{RED}✗ Discord webhook error ({response.status_code}): {response.text}{RESET}")
        except Exception as e:
            print(f"{RED}✗ Discord request failed: {e}{RESET}")

    print()

    return results


# ─── Main ───────────────────────────────────────────────────────────────────────
def main():
    separator("═", 70)
    print(f"{WHITE}{BOLD}")
    print("   ██████╗███╗   ███╗ ██████╗     ███████╗██╗  ██╗███████╗ ██████╗")
    print("  ██╔════╝████╗ ████║██╔═══██╗    ██╔════╝╚██╗██╔╝██╔════╝██╔════╝")
    print("  ██║     ██╔████╔██║██║   ██║    █████╗   ╚███╔╝ █████╗  ██║     ")
    print("  ██║     ██║╚██╔╝██║██║   ██║    ██╔══╝   ██╔██╗ ██╔══╝  ██║     ")
    print("  ╚██████╗██║ ╚═╝ ██║╚██████╔╝    ███████╗██╔╝ ██╗███████╗╚██████╗")
    print("   ╚═════╝╚═╝     ╚═╝ ╚═════╝     ╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝")
    print(f"{RESET}")
    print(f"{WHITE}              CMO EXECUTION AGENT — project ningen{RESET}")
    separator("═", 70)

    # Step 1: Read requirements
    data = read_requirements()

    # Step 2: Generate all marketing content
    content = generate_content(data)

    # Step 3: Save content to files
    save_content(content)

    # Step 4: Publish everywhere
    results = publish_content(content, data)

    # Final summary
    print()
    separator("═", 70)
    print(f"{GREEN}{BOLD}  CMO EXECUTION COMPLETE{RESET}")

    if results["email_sent"]:
        print(f"{GREEN}  Email sent via Resend to: {results.get('email_to', 'subscribers')}{RESET}")
    else:
        print(f"{RED}  Email: not sent{RESET}")

    if results["devto_url"]:
        print(f"{GREEN}  Article published on Dev.to: {results['devto_url']}{RESET}")
    else:
        print(f"{RED}  Dev.to: not published{RESET}")

    if results["discord_sent"]:
        print(f"{GREEN}  Discord message sent to channel{RESET}")
    else:
        print(f"{RED}  Discord: not sent{RESET}")

    print(f"{GREEN}  All content saved to outputs/ folder{RESET}")
    separator("═", 70)


if __name__ == "__main__":
    main()
