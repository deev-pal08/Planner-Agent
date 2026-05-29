"""Prompt modules for each brain.

Backward-compatible: re-exports everything from the original prompts.py
so that ``from planner_agent.agent.prompts import SYSTEM_PROMPT`` still works.
"""

from planner_agent.agent.prompts.feedback import FEEDBACK_PARSE_PROMPT
from planner_agent.agent.prompts.tactician import (
    SUMMARY_UPDATE_PROMPT,
    SYSTEM_PROMPT,
    build_briefing_context,
)

__all__ = [
    "FEEDBACK_PARSE_PROMPT",
    "SUMMARY_UPDATE_PROMPT",
    "SYSTEM_PROMPT",
    "build_briefing_context",
]
