"""Analyst brain — structured competence assessment and user intelligence."""

from __future__ import annotations

import json
import logging

from planner_agent.agent.base import BaseBrain
from planner_agent.agent.prompts.analyst import ANALYST_SYSTEM_PROMPT, build_analyst_context
from planner_agent.config import AppConfig
from planner_agent.models import EmailFeedback, UserIntelligenceProfile
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)


class AnalystBrain(BaseBrain):
    brain_name = "analyst"

    def __init__(self, config: AppConfig, state: StateStore):
        super().__init__(config, state)

    def _get_model(self) -> str:
        override = self.config.brains.analyst.model_override
        return override or self.config.llm.model

    def update_profile(
        self,
        feedback: EmailFeedback | None = None,
        briefing_tasks: list[dict] | None = None,
    ) -> UserIntelligenceProfile:
        """Run the Analyst to produce/update the UserIntelligenceProfile."""
        current_profile_json = self.state.get_meta("user_intelligence_profile")

        # Build new feedback context from just-received feedback
        new_feedback = []
        if feedback and briefing_tasks:
            for entry in feedback.task_updates:
                idx = entry.task_id - 1
                if 0 <= idx < len(briefing_tasks):
                    task = briefing_tasks[idx]
                    new_feedback.append({
                        "track": task.get("track", ""),
                        "title": task.get("title", ""),
                        "status": str(entry.status),
                        "estimated_hours": task.get("estimated_hours"),
                        "actual_hours": entry.actual_hours,
                        "notes": entry.notes,
                        "learnings": entry.learnings,
                    })
            if feedback.general_notes:
                new_feedback.append({
                    "track": "general",
                    "title": "(general notes)",
                    "status": "n/a",
                    "notes": feedback.general_notes,
                    "learnings": "",
                })

        cumulative_stats = self.state.get_cumulative_track_stats()
        skills = self.state.get_all_skills()
        all_feedback = self.state.get_all_feedback_with_content()

        # Get recent competence entries for context
        recent_competence = []
        for s in skills:
            entry = self.state.get_latest_competence(s["track_id"])
            if entry:
                recent_competence.append(entry)

        context = build_analyst_context(
            current_profile_json=current_profile_json,
            new_feedback=new_feedback,
            cumulative_stats=cumulative_stats,
            recent_competence=recent_competence,
            all_feedback=all_feedback,
            skills=skills,
        )

        model = self._get_model()
        raw_text = self._single_turn(
            model=model,
            system=ANALYST_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=3072,
        )

        profile_data = self._parse_json_response(raw_text)
        profile = UserIntelligenceProfile.model_validate(profile_data)

        # Persist the full profile
        self.state.set_meta(
            "user_intelligence_profile",
            profile.model_dump_json(),
        )

        # Also update the narrative summary in the old key for backward compat
        if profile.narrative_summary:
            self.state.set_meta("learning_summary", profile.narrative_summary)

        # Log competence entries for tracks that were assessed
        for track_intel in profile.tracks:
            self.state.add_competence_entry(
                track_id=track_intel.track_id,
                phase=next(
                    (s["current_phase"] for s in skills
                     if s["track_id"] == track_intel.track_id),
                    "learn",
                ),
                competence_level=track_intel.overall_level,
                sub_skills_json=json.dumps(
                    [s.model_dump() for s in track_intel.sub_skills],
                ),
                evidence="; ".join(track_intel.key_learnings[:3]),
                learning_velocity=track_intel.learning_velocity,
                engagement_score=None,
                notes=track_intel.difficulty_calibration,
                assessor="analyst",
            )

            # Update skill competence_level in skills table
            self.state._conn.execute(
                "UPDATE skills SET competence_level = ? WHERE track_id = ?",
                (track_intel.overall_level, track_intel.track_id),
            )
        self.state._conn.commit()

        logger.info(
            "Analyst updated profile: %d tracks assessed, narrative=%d chars",
            len(profile.tracks),
            len(profile.narrative_summary),
        )

        return profile

    def update_from_single_task(
        self,
        task: dict,
        status: str,
        hours: float | None = None,
        notes: str = "",
        learnings: str = "",
    ) -> UserIntelligenceProfile:
        """Convenience: update profile from a single CLI complete/skip."""
        feedback = EmailFeedback(
            task_updates=[{
                "task_id": 1,
                "status": status,
                "actual_hours": hours,
                "notes": notes,
                "learnings": learnings,
            }],
            general_notes="",
        )
        return self.update_profile(feedback, [task])

    def bootstrap_from_learning_summary(self) -> UserIntelligenceProfile:
        """Convert existing learning summary into a UserIntelligenceProfile on first run."""
        existing_summary = self.state.get_meta("learning_summary")
        if not existing_summary:
            logger.info("No existing learning summary to bootstrap from")
            return self.update_profile()

        # If profile already exists, skip bootstrap
        existing_profile = self.state.get_meta("user_intelligence_profile")
        if existing_profile:
            logger.info("Profile already exists, skipping bootstrap")
            return UserIntelligenceProfile.model_validate_json(existing_profile)

        logger.info("Bootstrapping profile from existing learning summary")
        return self.update_profile()
