"""Optional LLM narrative layer.

The deterministic engine in ``insights.py`` produces structured findings
with evidence. This module can upgrade those findings to free-form
consultant narrative when an Anthropic API key is available. Without a
key the app silently falls back to the deterministic text.

Usage:
    export ANTHROPIC_API_KEY=...   # optional
"""
from __future__ import annotations

import os

from foodcost.ai_engine.insights import Insight

SYSTEM_PROMPT = (
    "You are a veteran multi-unit restaurant operations consultant. "
    "You are given structured findings from a food-cost analytics engine. "
    "Rewrite each finding as 2-3 crisp sentences an owner would act on. "
    "Keep every number exactly as given. No fluff."
)


def is_available() -> bool:
    """True when an LLM can be called."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def enhance_insights(insights: list[Insight]) -> list[Insight]:
    """Rewrite insight bodies with an LLM when configured; no-op otherwise."""
    if not is_available():
        return insights
    try:
        import anthropic  # optional dependency

        client = anthropic.Anthropic()
        for ins in insights[:10]:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (f"Finding: {ins.title}\n"
                                f"Details: {ins.body}\n"
                                f"Suggested action: {ins.action}\n"
                                f"Evidence: {ins.evidence}"),
                }],
            )
            ins.body = msg.content[0].text.strip()
    except Exception:
        # Any failure -> deterministic text stands.
        pass
    return insights
