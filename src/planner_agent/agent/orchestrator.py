"""Orchestrator — coordinates all brains automatically.

The orchestrator is the single entry point for `planner daily`.
It decides what needs to run based on the current state:
- Scout runs periodically (every 3+ days) to find opportunities
- No goals? → bootstrap (Strategist seeds goals + milestones)
- No directive for this week? → run Critic (review last week) then Strategist
- No intelligence profile? → bootstrap Analyst
- Then always → run Tactician for daily tasks
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from planner_agent.config import AppConfig
from planner_agent.models import DailyBriefing
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, config: AppConfig, state: StateStore):
        self.config = config
        self.state = state
        self.last_directive: dict | None = None

    _MIN_API_GAP = 20

    def run_daily(
        self,
        target_date: str | None = None,
        force: bool = False,
    ) -> DailyBriefing:
        """Run the full daily cycle, auto-triggering brains as needed.

        This is the ONLY entry point for daily briefing generation.
        It handles:
        1. Analyst bootstrap (first run — convert learning summary)
        2. Scout opportunity discovery (every 3+ days)
        3. Critic weekly review (before Strategist, if last week has tasks)
        4. Strategist bootstrap or weekly planning (if no active directive)
        5. Tactician daily task generation (always)
        """
        now = datetime.now(UTC)
        today = target_date or now.strftime("%Y-%m-%d")
        self._last_api_call = 0.0

        self._maybe_bootstrap_analyst()

        self._pace()
        self._maybe_run_scout()

        self._pace()
        self._maybe_run_critic(today)

        self._pace()
        self._maybe_run_strategist(today)

        directive = self._get_active_directive_for_tactician()
        self.last_directive = directive

        self._pace()
        briefing = self._run_tactician(today, directive)

        return briefing

    def _pace(self) -> None:
        """Enforce minimum gap between consecutive API calls across brains."""
        if not self._last_api_call:
            self._last_api_call = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_api_call
        if elapsed < self._MIN_API_GAP:
            wait = self._MIN_API_GAP - elapsed
            logger.info("Orchestrator pacing: waiting %.0fs", wait)
            time.sleep(wait)
        self._last_api_call = time.monotonic()

    def _maybe_bootstrap_analyst(self) -> None:
        """On first run, convert existing learning summary to profile."""
        if not self.config.brains.analyst.enabled:
            return

        existing_profile = self.state.get_meta("user_intelligence_profile")
        if existing_profile:
            return

        existing_summary = self.state.get_meta("learning_summary")
        if not existing_summary:
            logger.info("Orchestrator: no learning data to bootstrap analyst")
            return

        logger.info("Orchestrator: bootstrapping analyst profile")
        from planner_agent.agent.analyst import AnalystBrain
        analyst = AnalystBrain(self.config, self.state)
        analyst.bootstrap_from_learning_summary()

    def _maybe_run_scout(self) -> None:
        """Run Scout to discover opportunities if last run was 3+ days ago."""
        if not self.config.brains.scout.enabled:
            return
        if not self.config.brains.scout.auto_trigger:
            return

        from planner_agent.agent.scout import ScoutBrain
        scout = ScoutBrain(self.config, self.state)

        if scout.needs_run():
            logger.info("Orchestrator: running Scout for opportunity discovery")
            scout.run()
        else:
            logger.info("Orchestrator: Scout ran recently, skipping")

    def _maybe_run_critic(self, today: str) -> None:
        """Run Critic to review the previous week, if needed.

        The Critic runs when:
        - Critic is enabled
        - The Strategist will need a new directive (i.e., no directive for this week)
        - The previous week has tasks but no review yet
        """
        if not self.config.brains.critic.enabled:
            return

        if not self.config.brains.strategist.enabled:
            return

        from planner_agent.agent.strategist import StrategistBrain
        strategist = StrategistBrain.__new__(StrategistBrain)
        strategist.config = self.config
        strategist.state = self.state

        if not strategist.needs_directive(today):
            logger.info("Orchestrator: directive exists, skipping Critic")
            return

        from planner_agent.agent.critic import CriticBrain
        critic = CriticBrain(self.config, self.state)

        if critic.needs_review(today):
            logger.info("Orchestrator: running Critic for last week's review")
            critic.run(today)
        else:
            logger.info("Orchestrator: no review needed (already done or no tasks)")

    def _maybe_run_strategist(self, today: str) -> None:
        """Run Strategist if no directive exists for the current week."""
        if not self.config.brains.strategist.enabled:
            return

        from planner_agent.agent.strategist import StrategistBrain
        strategist = StrategistBrain(self.config, self.state)

        if strategist.needs_directive(today):
            logger.info("Orchestrator: no directive for this week — "
                         "running Strategist")
            strategist.run(today)
        else:
            logger.info("Orchestrator: directive exists for this week, "
                         "skipping Strategist")

    def _get_active_directive_for_tactician(self) -> dict | None:
        """Get the active directive to pass to the Tactician."""
        active = self.state.get_active_directive()
        if active:
            return active.get("directive")
        return None

    def _run_tactician(
        self, today: str, directive: dict | None,
    ) -> DailyBriefing:
        """Run the Tactician (PlannerAgent) to generate daily tasks."""
        from planner_agent.agent.loop import PlannerAgent
        agent = PlannerAgent(self.config, self.state)
        return agent.generate_briefing(
            target_date=today, directive=directive,
        )
