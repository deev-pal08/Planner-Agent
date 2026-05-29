"""Strategist brain — weekly strategic planning with Opus."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from planner_agent.agent.base import BaseBrain
from planner_agent.agent.prompts.strategist import (
    STRATEGIST_BOOTSTRAP_PROMPT,
    STRATEGIST_SYSTEM_PROMPT,
    build_strategist_context,
)
from planner_agent.config import AppConfig
from planner_agent.models import Goal, Milestone, StrategicDirective
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)


class StrategistBrain(BaseBrain):
    brain_name = "strategist"

    def __init__(self, config: AppConfig, state: StateStore):
        super().__init__(config, state)

    def _get_model(self) -> str:
        override = self.config.brains.strategist.model_override
        return override or self.config.llm.strategic_model

    def _week_bounds(self, today: str) -> tuple[str, str]:
        dt = datetime.fromisoformat(today)
        monday = dt - timedelta(days=dt.weekday())
        sunday = monday + timedelta(days=6)
        return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")

    def needs_directive(self, today: str) -> bool:
        week_start, _ = self._week_bounds(today)
        existing = self.state.get_directive_by_week(week_start)
        return existing is None

    def run(self, today: str | None = None) -> StrategicDirective:
        now = datetime.now(UTC)
        today = today or now.strftime("%Y-%m-%d")
        week_start, week_end = self._week_bounds(today)

        goals = self.state.get_active_goals()
        is_bootstrap = len(goals) == 0

        if is_bootstrap:
            return self._bootstrap(today, week_start, week_end)
        return self._plan_week(today, week_start, week_end)

    def _bootstrap(
        self, today: str, week_start: str, week_end: str,
    ) -> StrategicDirective:
        logger.info("Strategist: bootstrap mode — seeding goals and milestones")

        from planner_agent.config import load_about_me
        about_me = load_about_me(self.config.about_me)

        context = build_strategist_context(
            about_me=about_me,
            skills=self.state.get_all_skills(),
            goals=[],
            milestones=[],
            cumulative_stats=self.state.get_cumulative_track_stats(),
            active_directive=None,
            critic_review=None,
            intelligence_profile_json=self.state.get_meta(
                "user_intelligence_profile",
            ),
            opportunities=[],
            today=today,
            weekday_hours=self.config.time_budget.weekday,
            weekend_hours=self.config.time_budget.weekend_day,
            is_bootstrap=True,
        )

        model = self._get_model()
        raw = self._single_turn(
            model=model,
            system=STRATEGIST_BOOTSTRAP_PROMPT,
            user_message=context,
            max_tokens=self.config.llm.strategic_max_tokens,
        )

        data = self._parse_json_response(raw)

        goal_id_map: dict[int, int] = {}
        for i, g in enumerate(data.get("goals", [])):
            goal = Goal(
                title=g["title"],
                description=g.get("description", ""),
                deadline=g.get("deadline"),
                success_criteria=g.get("success_criteria", []),
                priority=g.get("priority", "high"),
            )
            db_id = self.state.add_goal(goal)
            goal_id_map[i] = db_id
            logger.info("Goal seeded: [%d] %s", db_id, goal.title)

        ms_id_map: dict[int, int] = {}
        for i, m in enumerate(data.get("milestones", [])):
            goal_idx = m.get("goal_index", 0)
            goal_id = goal_id_map.get(goal_idx, 1)

            dep_indices = m.get("depends_on_indices", [])
            depends_on = [
                ms_id_map[di] for di in dep_indices if di in ms_id_map
            ]

            milestone = Milestone(
                goal_id=goal_id,
                title=m["title"],
                description=m.get("description", ""),
                target_date=m["target_date"],
                tracks=m.get("tracks", []),
                success_criteria=m.get("success_criteria", []),
                depends_on=depends_on,
            )
            db_id = self.state.add_milestone(milestone)
            ms_id_map[i] = db_id
            logger.info("Milestone seeded: [%d] %s", db_id, milestone.title)

        directive_data = data.get("directive", {})
        directive_data["week_start"] = week_start
        directive_data["week_end"] = week_end
        directive = StrategicDirective.model_validate(directive_data)

        self.state.save_directive(
            week_start=week_start,
            week_end=week_end,
            directive_json=directive.model_dump_json(),
        )

        logger.info(
            "Strategist bootstrap complete: %d goals, %d milestones, "
            "directive for %s–%s",
            len(goal_id_map), len(ms_id_map), week_start, week_end,
        )
        return directive

    def _plan_week(
        self, today: str, week_start: str, week_end: str,
    ) -> StrategicDirective:
        logger.info("Strategist: planning week %s–%s", week_start, week_end)

        from planner_agent.config import load_about_me
        about_me = load_about_me(self.config.about_me)

        context = build_strategist_context(
            about_me=about_me,
            skills=self.state.get_all_skills(),
            goals=self.state.get_active_goals(),
            milestones=self.state.get_all_milestones(),
            cumulative_stats=self.state.get_cumulative_track_stats(),
            active_directive=self.state.get_active_directive(),
            critic_review=self.state.get_latest_review(),
            intelligence_profile_json=self.state.get_meta(
                "user_intelligence_profile",
            ),
            opportunities=self.state.get_upcoming_opportunities(today),
            today=today,
            weekday_hours=self.config.time_budget.weekday,
            weekend_hours=self.config.time_budget.weekend_day,
            is_bootstrap=False,
        )

        model = self._get_model()
        raw = self._single_turn(
            model=model,
            system=STRATEGIST_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=self.config.llm.strategic_max_tokens,
        )

        directive_data = self._parse_json_response(raw)
        directive_data["week_start"] = week_start
        directive_data["week_end"] = week_end
        directive = StrategicDirective.model_validate(directive_data)

        self.state.save_directive(
            week_start=week_start,
            week_end=week_end,
            directive_json=directive.model_dump_json(),
        )

        logger.info(
            "Strategist produced directive: theme='%s', %d targets, %.0fh",
            directive.weekly_theme,
            len(directive.targets),
            directive.total_hours_available,
        )
        return directive
