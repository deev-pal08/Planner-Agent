"""Critic brain — honest weekly review of planned vs actual."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from planner_agent.agent.base import BaseBrain
from planner_agent.agent.prompts.critic import (
    CRITIC_SYSTEM_PROMPT,
    build_critic_context,
)
from planner_agent.config import AppConfig
from planner_agent.models import WeeklyReview
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)


class CriticBrain(BaseBrain):
    brain_name = "critic"

    def __init__(self, config: AppConfig, state: StateStore):
        super().__init__(config, state)

    def _get_model(self) -> str:
        override = self.config.brains.critic.model_override
        return override or self.config.llm.research_model

    def _week_bounds(self, today: str) -> tuple[str, str]:
        dt = datetime.fromisoformat(today)
        monday = dt - timedelta(days=dt.weekday())
        sunday = monday + timedelta(days=6)
        return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")

    def _previous_week_bounds(self, today: str) -> tuple[str, str]:
        dt = datetime.fromisoformat(today)
        this_monday = dt - timedelta(days=dt.weekday())
        prev_monday = this_monday - timedelta(days=7)
        prev_sunday = prev_monday + timedelta(days=6)
        return prev_monday.strftime("%Y-%m-%d"), prev_sunday.strftime("%Y-%m-%d")

    def needs_review(self, today: str) -> bool:
        prev_start, _ = self._previous_week_bounds(today)
        existing = self.state.get_review_by_week(prev_start)
        if existing:
            return False

        prev_start, prev_end = self._previous_week_bounds(today)
        tasks = self.state.get_tasks_for_week(prev_start, prev_end)
        return len(tasks) > 0

    def run(self, today: str | None = None) -> WeeklyReview:
        now = datetime.now(UTC)
        today = today or now.strftime("%Y-%m-%d")
        prev_start, prev_end = self._previous_week_bounds(today)

        directive_row = self.state.get_directive_by_week(prev_start)
        tasks = self.state.get_tasks_for_week(prev_start, prev_end)

        context = build_critic_context(
            week_start=prev_start,
            week_end=prev_end,
            directive=directive_row,
            tasks=tasks,
            skills=self.state.get_all_skills(),
            goals=self.state.get_active_goals(),
            milestones=self.state.get_all_milestones(),
            cumulative_stats=self.state.get_cumulative_track_stats(),
            feedback_notes=self.state.get_recent_feedback_notes(),
            today=today,
        )

        model = self._get_model()
        raw = self._single_turn(
            model=model,
            system=CRITIC_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=4096,
        )

        review_data = self._parse_json_response(raw)
        review_data["week_start"] = prev_start
        review_data["week_end"] = prev_end
        review = WeeklyReview.model_validate(review_data)

        self.state.save_weekly_review(
            week_start=prev_start,
            week_end=prev_end,
            review_json=json.dumps(review_data),
        )

        logger.info(
            "Critic review complete: grade=%s, adherence=%.0f%%, "
            "%d recommendations (%s–%s)",
            review.overall_grade,
            review.adherence_score * 100,
            len(review.strategic_recommendations),
            prev_start, prev_end,
        )
        return review
