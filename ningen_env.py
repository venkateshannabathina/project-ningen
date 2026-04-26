#!/usr/bin/env python3
"""
Ningen RL Environment
Wraps the entire Ningen autonomous startup pipeline as a fully compliant
OpenEnv RL environment with verifiable reward components.

Run with: python3 ningen_env.py
"""

import os
import sys
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

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
CYAN   = "\033[36m"


def separator(char="─", width=70):
    print(f"{DIM}{char * width}{RESET}")


def env_header(title):
    print()
    separator("═", 70)
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    separator("═", 70)
    print()


# ─── Company State ──────────────────────────────────────────────────────────────
@dataclass
class CompanyState:
    idea: str = ""
    requirements_generated: bool = False
    product_built: bool = False
    marketing_published: bool = False
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    llm_calls: int = 0
    episode: int = 0
    reward: float = 0.0
    reward_breakdown: dict = field(default_factory=dict)
    product_name: str = ""
    error_log: list = field(default_factory=list)


# ─── Ningen Environment ────────────────────────────────────────────────────────
class NingenEnv:
    """
    OpenEnv-compatible RL environment wrapping the Ningen startup pipeline.

    Action space: dict with key 'idea' (str) — the startup idea to execute.
    Observation space: dict of CompanyState fields.
    Reward: float between 0.0 and 1.0, computed from 5 verifiable components.
    """

    def __init__(self):
        self.state = CompanyState()
        self._episode_count = 0

    def reset(self):
        """Reset environment to initial state. Returns observation dict."""
        self._episode_count += 1
        self.state = CompanyState(episode=self._episode_count)

        print(f"\n{AMBER}{BOLD}  ENVIRONMENT RESET — Episode {self._episode_count}{RESET}")
        separator("─", 70)

        return self.observe()

    def step(self, action: dict):
        """
        Execute full Ningen pipeline for the given idea.

        Args:
            action: dict with key 'idea' containing the startup idea string.

        Returns:
            (observation, reward, done, info) tuple.
        """
        idea = action.get("idea", "")
        if not idea:
            return self.observe(), 0.0, True, {"error": "No idea provided"}

        self.state.idea = idea

        env_header(f"EPISODE {self.state.episode} — {idea[:50]}...")

        # ── Phase 1: Board Meeting ───────────────────────────────────────────
        self._run_board_meeting(idea)

        # ── Phase 2: CTO Execution ───────────────────────────────────────────
        self._run_cto_execution()

        # ── Phase 3: CMO Execution ───────────────────────────────────────────
        self._run_cmo_execution()

        # ── Compute Reward ───────────────────────────────────────────────────
        reward = self.compute_reward()
        self.state.reward = reward

        # ── Save Episode Record ──────────────────────────────────────────────
        self._save_episode_record()

        # ── Print Reward Breakdown ───────────────────────────────────────────
        self._print_reward_breakdown()

        done = True
        info = {
            "product_name": self.state.product_name,
            "requirements_generated": self.state.requirements_generated,
            "product_built": self.state.product_built,
            "marketing_published": self.state.marketing_published,
            "conflicts_detected": self.state.conflicts_detected,
            "conflicts_resolved": self.state.conflicts_resolved,
            "llm_calls": self.state.llm_calls,
            "errors": self.state.error_log,
        }

        return self.observe(), reward, done, info

    def observe(self):
        """Returns current state as observation dict."""
        return {
            "idea": self.state.idea,
            "requirements_generated": self.state.requirements_generated,
            "product_built": self.state.product_built,
            "marketing_published": self.state.marketing_published,
            "conflicts_detected": self.state.conflicts_detected,
            "conflicts_resolved": self.state.conflicts_resolved,
            "llm_calls": self.state.llm_calls,
            "episode": self.state.episode,
            "reward": self.state.reward,
            "product_name": self.state.product_name,
        }

    # ── Phase 1: Board Meeting ───────────────────────────────────────────────
    def _run_board_meeting(self, idea: str):
        env_header("PHASE 1 — BOARD MEETING")

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

            # Initialize context
            ctx = initialize_context(idea)
            llm_count = 0

            # Round 1: Opening positions (4 LLM calls)
            print(f"{AMBER}Running Round 1 — Opening Positions...{RESET}")
            for msg in api_run_opening_round(ctx):
                llm_count += 1
                print(f"{DIM}  [{msg['speaker']}] {msg['message'][:80]}...{RESET}")

            # Client Q&A: Generate questions (4 LLM calls)
            print(f"{AMBER}Running Client Q&A...{RESET}")
            ctx, q_msgs, questions = api_generate_questions(ctx)
            llm_count += 4

            # Auto-answer client questions (autonomous mode)
            auto_answer = (
                f"The product is {idea}. Target audience is professionals and consumers "
                f"who need this solution. Budget is flexible, timeline is 90 days for MVP. "
                f"No existing infrastructure — building from scratch. Success means active "
                f"engaged users and positive feedback within the first month."
            )
            ctx = api_apply_clarifications(ctx, auto_answer, questions)
            print(f"{GREEN}✓ Client questions auto-answered{RESET}")

            # Round 2: Reactions (4 LLM calls)
            print(f"{AMBER}Running Round 2 — Reactions...{RESET}")
            for msg in api_run_reaction_round(ctx):
                llm_count += 1
                print(f"{DIM}  [{msg['speaker']}] {msg['message'][:80]}...{RESET}")

            # Conflict detection
            print(f"{AMBER}Running Conflict Detection...{RESET}")
            ctx, conflict_msgs = api_detect_conflicts_return(ctx)
            self.state.conflicts_detected = len(ctx.get("conflicts", []))
            for cm in conflict_msgs:
                print(f"{RED}  ⚠ {cm['message'][:100]}{RESET}")

            # Round 3: Resolution (2 LLM calls per conflict)
            print(f"{AMBER}Running Round 3 — Resolution...{RESET}")
            resolution_count = 0
            for msg in api_run_resolution_round(ctx):
                if msg["type"] == "resolution":
                    llm_count += 1
                    resolution_count += 1
                elif msg["type"] == "agreement":
                    print(f"{GREEN}  ✓ {msg['message'][:100]}{RESET}")

            self.state.conflicts_resolved = len(ctx.get("agreed_on", []))

            # Briefings (4 LLM calls)
            print(f"{AMBER}Running Final Briefings...{RESET}")
            briefing_store = {}
            for msg in api_run_briefings(ctx):
                llm_count += 1
                briefing_store[msg["speaker"]] = msg["message"]
                print(f"{DIM}  [{msg['speaker']}] briefing ready{RESET}")

            # Generate requirements document (5-6 LLM calls)
            print(f"{AMBER}Generating Requirements Document...{RESET}")
            ctx, doc = api_generate_requirements(ctx)
            llm_count += 6  # product name, tech req, GTM, execution, open Q, next step

            self.state.product_name = doc.get("product_name", "Startup MVP")

            # Save outputs
            project_name = doc.get("product_name", "project")
            save_briefings(briefing_store, ctx, project_name)
            save_output(doc)

            self.state.requirements_generated = True
            self.state.llm_calls += llm_count

            print(f"\n{GREEN}{BOLD}✓ Board meeting complete — {self.state.product_name}{RESET}")
            print(f"{GREEN}  LLM calls: {llm_count} | Conflicts: {self.state.conflicts_detected} detected, {self.state.conflicts_resolved} resolved{RESET}")

        except Exception as e:
            self.state.requirements_generated = False
            self.state.error_log.append(f"Board meeting failed: {str(e)}")
            print(f"{RED}✗ Board meeting failed: {e}{RESET}")

    # ── Phase 2: CTO Execution ───────────────────────────────────────────────
    def _run_cto_execution(self):
        env_header("PHASE 2 — CTO EXECUTION")

        if not self.state.requirements_generated:
            print(f"{RED}✗ Skipping CTO — no requirements generated{RESET}")
            self.state.error_log.append("CTO skipped: no requirements")
            return

        try:
            from execute_cto import (
                find_latest_outputs as cto_find_outputs,
                read_requirements as cto_read_req,
                generate_claude_prompt,
                run_claude_code,
            )

            # Read requirements
            print(f"{AMBER}CTO reading requirements...{RESET}")
            data = cto_read_req()
            self.state.llm_calls += 1  # GPT-4o-mini prompt generation

            # Generate Claude Code prompt
            print(f"{AMBER}CTO generating build prompt...{RESET}")
            prompt_text, prompt_path = generate_claude_prompt(data)
            self.state.llm_calls += 1

            # Run Claude Code
            print(f"{AMBER}CTO running Claude Code...{RESET}")
            success = run_claude_code(prompt_path)

            # Check if index.html exists
            index_path = Path("outputs") / "index.html"
            if success and index_path.exists():
                self.state.product_built = True
                size = index_path.stat().st_size
                print(f"{GREEN}{BOLD}✓ Product built — index.html ({size:,} bytes){RESET}")
            else:
                self.state.product_built = False
                self.state.error_log.append("CTO: index.html not created")
                print(f"{RED}✗ Product not built — index.html missing{RESET}")

        except Exception as e:
            self.state.product_built = False
            self.state.error_log.append(f"CTO execution failed: {str(e)}")
            print(f"{RED}✗ CTO execution failed: {e}{RESET}")

    # ── Phase 3: CMO Execution ───────────────────────────────────────────────
    def _run_cmo_execution(self):
        env_header("PHASE 3 — CMO EXECUTION")

        if not self.state.requirements_generated:
            print(f"{RED}✗ Skipping CMO — no requirements generated{RESET}")
            self.state.error_log.append("CMO skipped: no requirements")
            return

        try:
            from execute_cmo import (
                read_requirements as cmo_read_req,
                generate_content,
                save_content,
                publish_content,
            )

            # Read requirements
            print(f"{AMBER}CMO reading requirements...{RESET}")
            data = cmo_read_req()

            # Generate marketing content (4 LLM calls)
            print(f"{AMBER}CMO generating marketing content...{RESET}")
            content = generate_content(data)
            self.state.llm_calls += 4

            # Save content to files
            print(f"{AMBER}CMO saving content...{RESET}")
            save_content(content)

            # Publish content
            print(f"{AMBER}CMO publishing content...{RESET}")
            results = publish_content(content, data)

            # Check if marketing files were created
            marketing_files = [
                Path("outputs") / "devto_article.md",
                Path("outputs") / "discord_post.md",
                Path("outputs") / "cold_email.md",
            ]
            if any(f.exists() for f in marketing_files):
                self.state.marketing_published = True
                created = sum(1 for f in marketing_files if f.exists())
                print(f"{GREEN}{BOLD}✓ Marketing published — {created}/3 channels{RESET}")
            else:
                self.state.marketing_published = False
                self.state.error_log.append("CMO: no marketing files created")
                print(f"{RED}✗ Marketing not published{RESET}")

        except Exception as e:
            self.state.marketing_published = False
            self.state.error_log.append(f"CMO execution failed: {str(e)}")
            print(f"{RED}✗ CMO execution failed: {e}{RESET}")

    # ── Reward Computation ───────────────────────────────────────────────────
    def compute_reward(self):
        """
        Compute reward from 5 independent verifiable components. No LLM judge.
        Returns float between 0.0 and 1.0.
        """
        # Component 1: Requirements generated
        requirements_score = 1.0 if self.state.requirements_generated else 0.0

        # Component 2: Product built (index.html exists and > 1000 bytes)
        product_score = 0.0
        index_path = Path("outputs") / "index.html"
        if self.state.product_built and index_path.exists() and index_path.stat().st_size > 1000:
            product_score = 1.0

        # Component 3: Marketing files created (count of 4 possible files)
        marketing_files = [
            Path("outputs") / "cold_email.md",
            Path("outputs") / "devto_article.md",
            Path("outputs") / "discord_post.md",
            Path("outputs") / "reddit_post.md",
        ]
        existing_count = sum(1 for f in marketing_files if f.exists())
        marketing_score = existing_count / 4.0

        # Component 4: Conflict resolution ratio
        if self.state.conflicts_detected == 0:
            conflict_resolution_score = 1.0
        else:
            conflict_resolution_score = self.state.conflicts_resolved / self.state.conflicts_detected

        # Component 5: Efficiency (fewer LLM calls = better)
        if self.state.llm_calls <= 20:
            efficiency_score = 1.0
        elif self.state.llm_calls <= 30:
            efficiency_score = 0.5
        else:
            efficiency_score = 0.0

        # Weighted sum
        weights = {
            "requirements_score": 0.25,
            "product_score": 0.25,
            "marketing_score": 0.20,
            "conflict_resolution": 0.15,
            "efficiency_score": 0.15,
        }

        breakdown = {
            "requirements_score": requirements_score,
            "product_score": product_score,
            "marketing_score": marketing_score,
            "conflict_resolution": conflict_resolution_score,
            "efficiency_score": efficiency_score,
        }

        total = sum(breakdown[k] * weights[k] for k in weights)

        self.state.reward_breakdown = breakdown
        return round(total, 4)

    # ── Print Reward Breakdown ───────────────────────────────────────────────
    def _print_reward_breakdown(self):
        env_header(f"EPISODE {self.state.episode} REWARD: {self.state.reward:.4f}")

        weights = {
            "requirements_score": 0.25,
            "product_score": 0.25,
            "marketing_score": 0.20,
            "conflict_resolution": 0.15,
            "efficiency_score": 0.15,
        }

        for key, score in self.state.reward_breakdown.items():
            weight_pct = int(weights[key] * 100)
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            print(f"  {key:<24} {score:.3f}  {bar}  {weight_pct}%")

        print()
        weighted = self.state.reward * 100
        print(f"  {BOLD}{'TOTAL':<24} {self.state.reward:.4f}  {'█' * int(weighted / 10)}{'░' * (10 - int(weighted / 10))}  100%{RESET}")
        separator("─", 70)

    # ── Save Episode Record ──────────────────────────────────────────────────
    def _save_episode_record(self):
        """Append episode record to outputs/episode_log.json."""
        log_path = Path("outputs") / "episode_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "episode": self.state.episode,
            "idea": self.state.idea,
            "product_name": self.state.product_name,
            "reward": self.state.reward,
            "reward_breakdown": self.state.reward_breakdown,
            "requirements_generated": self.state.requirements_generated,
            "product_built": self.state.product_built,
            "marketing_published": self.state.marketing_published,
            "conflicts_detected": self.state.conflicts_detected,
            "conflicts_resolved": self.state.conflicts_resolved,
            "llm_calls": self.state.llm_calls,
            "errors": self.state.error_log,
            "timestamp": datetime.now().isoformat(),
        }

        # Load existing records or start fresh
        existing = []
        if log_path.exists():
            try:
                with open(log_path, "r") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, Exception):
                existing = []

        existing.append(record)

        with open(log_path, "w") as f:
            json.dump(existing, f, indent=2)

        print(f"{GREEN}✓ Episode record saved to: {log_path}{RESET}")


# ─── Experiment Runner ──────────────────────────────────────────────────────────
def run_experiment():
    """Run a baseline experiment with 3 episodes using different startup ideas."""

    separator("═", 70)
    print(f"{WHITE}{BOLD}")
    print("  ██████╗ ██╗          ███████╗██╗  ██╗██████╗ ")
    print("  ██╔══██╗██║          ██╔════╝╚██╗██╔╝██╔══██╗")
    print("  ██████╔╝██║          █████╗   ╚███╔╝ ██████╔╝")
    print("  ██╔══██╗██║          ██╔══╝   ██╔██╗ ██╔═══╝ ")
    print("  ██║  ██║███████╗     ███████╗██╔╝ ██╗██║     ")
    print("  ╚═╝  ╚═╝╚══════╝     ╚══════╝╚═╝  ╚═╝╚═╝     ")
    print(f"{RESET}")
    print(f"{WHITE}       NINGEN RL EXPERIMENT — Baseline Run{RESET}")
    separator("═", 70)

    ideas = [
        "AI powered recipe generator",
        "personal finance tracker for students",
        "remote team collaboration tool",
    ]

    env = NingenEnv()
    results = []

    for i, idea in enumerate(ideas):
        print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
        print(f"{CYAN}{BOLD}  EXPERIMENT EPISODE {i + 1}/3 — {idea}{RESET}")
        print(f"{CYAN}{BOLD}{'='*70}{RESET}")

        obs = env.reset()

        try:
            obs, reward, done, info = env.step({"idea": idea})
            results.append({
                "episode": i + 1,
                "idea": idea,
                "product_name": info.get("product_name", "N/A"),
                "reward": reward,
                "requirements": info.get("requirements_generated", False),
                "product_built": info.get("product_built", False),
                "marketing": info.get("marketing_published", False),
                "errors": info.get("errors", []),
            })
        except Exception as e:
            print(f"{RED}✗ Episode {i + 1} crashed: {e}{RESET}")
            results.append({
                "episode": i + 1,
                "idea": idea,
                "product_name": "FAILED",
                "reward": 0.0,
                "requirements": False,
                "product_built": False,
                "marketing": False,
                "errors": [str(e)],
            })

        # Sleep between episodes to avoid rate limits
        if i < len(ideas) - 1:
            print(f"\n{DIM}Sleeping 5 seconds before next episode...{RESET}")
            time.sleep(5)

    # ── Summary Table ────────────────────────────────────────────────────────
    print()
    separator("═", 70)
    print(f"{WHITE}{BOLD}  EXPERIMENT SUMMARY{RESET}")
    separator("═", 70)
    print()

    print(f"  {'EP':<4} {'IDEA':<40} {'REWARD':<10}")
    print(f"  {'──':<4} {'──────────────────────────────────────':<40} {'──────':<10}")
    for r in results:
        reward_color = GREEN if r["reward"] >= 0.5 else AMBER if r["reward"] > 0 else RED
        print(f"  {r['episode']:<4} {r['idea'][:38]:<40} {reward_color}{r['reward']:.4f}{RESET}")

    print()

    # ── Compute Aggregates ───────────────────────────────────────────────────
    rewards = [r["reward"] for r in results]
    avg_reward = sum(rewards) / len(rewards) if rewards else 0.0
    best = max(results, key=lambda x: x["reward"]) if results else {}
    worst = min(results, key=lambda x: x["reward"]) if results else {}

    # ── Save Experiment Results ──────────────────────────────────────────────
    experiment_data = {
        "baseline_rewards": rewards,
        "average_reward": round(avg_reward, 4),
        "best_episode": best,
        "worst_episode": worst,
        "all_episodes": results,
        "timestamp": datetime.now().isoformat(),
    }

    experiment_path = Path("outputs") / "rl_experiment.json"
    experiment_path.parent.mkdir(parents=True, exist_ok=True)
    with open(experiment_path, "w") as f:
        json.dump(experiment_data, f, indent=2)

    # ── Final Output ─────────────────────────────────────────────────────────
    print()
    separator("═", 70)
    print(f"{GREEN}{BOLD}  RL EXPERIMENT COMPLETE{RESET}")
    print(f"{GREEN}  Average reward: {avg_reward:.4f}{RESET}")
    print(f"{GREEN}  Best episode: {best.get('episode', '?')} (reward: {best.get('reward', 0):.4f}){RESET}")
    print(f"{GREEN}  Results saved to outputs/rl_experiment.json{RESET}")
    print(f"{CYAN}  This environment is OpenEnv compatible.{RESET}")
    separator("═", 70)


# ─── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_experiment()
