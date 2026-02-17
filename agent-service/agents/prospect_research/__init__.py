"""Prospect Research Goal Bot.

Autonomous goal bot that researches potential business prospects.
Runs on a schedule and persists findings between runs.
"""

from .prospect_research_agent import prospect_research

__all__ = ["prospect_research"]
