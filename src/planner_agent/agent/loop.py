"""Core agent loop — Claude API with structured outputs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import anthropic

from planner_agent.agent.prompts import (
    FEEDBACK_PARSE_PROMPT,
    SYSTEM_PROMPT,
    build_briefing_context,
)
from planner_agent.config import AppConfig, load_about_me
from planner_agent.models import (
    DailyBriefing,
    EmailFeedback,
    NewsletterArticle,
    NewsletterReading,
    Phase,
    Priority,
    Task,
    TaskStatus,
    TaskType,
)
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)


class PlannerAgent:
    def __init__(self, config: AppConfig, state: StateStore):
        self.config = config
        self.state = state
        self.about_me = load_about_me(config.about_me)
        self._client = anthropic.Anthropic(
            api_key=config.llm.api_key,
            base_url="https://api.anthropic.com",
        )

    def generate_briefing(self, target_date: str | None = None) -> DailyBriefing:
        """Generate a daily briefing with hyper-specific tasks."""
        now = datetime.now(UTC)
        today = target_date or now.strftime("%Y-%m-%d")
        day_of_week = datetime.fromisoformat(today).strftime("%A")

        is_weekend = day_of_week in ("Saturday", "Sunday")
        available_hours = (
            self.config.time_budget.weekend_day
            if is_weekend
            else self.config.time_budget.weekday
        )

        skills = self.state.get_all_skills()
        recent_tasks = self.state.get_recent_completed(days=7)
        achievements = self.state.get_all_achievements()
        achievement_counts = self.state.get_achievement_counts()
        completion_stats = self.state.get_completion_stats(days=7)
        skipped_patterns = self.state.get_skipped_patterns(days=14)

        # Newsletter integration (read-only, graceful degradation)
        newsletter_articles = None
        newsletter_meta = None

        if self.config.newsletter.enabled and self.config.newsletter.project_dir:
            try:
                from planner_agent.state.newsletter import NewsletterReader

                reader = NewsletterReader(self.config.newsletter.project_dir)
                if reader.is_available():
                    consumed_urls = self.state.get_consumed_article_urls()
                    db_age = reader.get_db_age_days()
                    total_count = reader.get_article_count()

                    articles_by_priority = reader.get_articles_by_priority(
                        exclude_urls=consumed_urls,
                    )
                    unread_total = sum(len(v) for v in articles_by_priority.values())

                    newsletter_articles = articles_by_priority
                    newsletter_meta = {
                        "db_age_days": db_age,
                        "total_articles": total_count,
                        "unread_shown": unread_total,
                        "consumed_count": len(consumed_urls),
                        "is_stale": (
                            db_age is not None
                            and db_age > self.config.newsletter.stale_threshold_days
                        ),
                    }
                    reader.close()
                    logger.info(
                        "Newsletter: %d total, %d unread shown, DB age: %.1f days",
                        total_count, unread_total, db_age or 0,
                    )
                else:
                    logger.warning(
                        "Newsletter DB not available at %s",
                        self.config.newsletter.project_dir,
                    )
            except Exception:
                logger.exception("Failed to read newsletter DB — continuing without it")

        context = build_briefing_context(
            about_me=self.about_me,
            skills=skills,
            recent_tasks=recent_tasks,
            achievements=achievements,
            achievement_counts=achievement_counts,
            completion_stats=completion_stats,
            skipped_patterns=skipped_patterns,
            available_hours=available_hours,
            day_of_week=day_of_week,
            today=today,
            newsletter_articles=newsletter_articles,
            newsletter_meta=newsletter_meta,
        )

        logger.info("Generating briefing for %s (%s, %.1fh available)", today, day_of_week, available_hours)

        response = self._client.messages.create(
            model=self.config.llm.research_model,
            max_tokens=self.config.llm.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        raw_text = response.content[0].text
        briefing_data = self._parse_json_response(raw_text)

        tasks = []
        for t in briefing_data.get("tasks", []):
            tasks.append(Task(
                title=t.get("title", ""),
                description=t.get("description", ""),
                task_type=TaskType(t.get("task_type", "other")),
                track=t.get("track", ""),
                phase=Phase(t.get("phase", "learn")),
                priority=Priority(t.get("priority", "medium")),
                estimated_hours=t.get("estimated_hours", 1.0),
                resource_url=t.get("resource_url", ""),
                resource_name=t.get("resource_name", ""),
                why=t.get("why", ""),
                status=TaskStatus.PENDING,
                assigned_date=datetime.fromisoformat(today),
            ))

        newsletter_reading = None
        nr_data = briefing_data.get("newsletter_reading")
        if nr_data and isinstance(nr_data, dict) and nr_data.get("articles"):
            newsletter_reading = NewsletterReading(
                title=nr_data.get("title", "Newsletter Reading"),
                description=nr_data.get("description", ""),
                estimated_hours=nr_data.get("estimated_hours", 1.0),
                articles=[
                    NewsletterArticle(
                        title=a.get("title", ""),
                        url=a.get("url", ""),
                        priority=a.get("priority", "INTERESTING"),
                        why=a.get("why", ""),
                    )
                    for a in nr_data["articles"]
                ],
            )

        briefing = DailyBriefing(
            date=today,
            focus_track=briefing_data.get("focus_track", ""),
            focus_phase=Phase(briefing_data.get("focus_phase", "learn")),
            focus_rationale=briefing_data.get("focus_rationale", ""),
            tasks=tasks,
            total_estimated_hours=briefing_data.get("total_estimated_hours", available_hours),
            portfolio_gaps=briefing_data.get("portfolio_gaps", []),
            skill_observations=briefing_data.get("skill_observations", []),
            newsletter_topics=briefing_data.get("newsletter_topics", []),
            newsletter_reading=newsletter_reading,
        )

        self._persist_briefing(briefing)
        logger.info(
            "Generated %d tasks for %s (%.1fh total, focus: %s/%s)",
            len(tasks), today, briefing.total_estimated_hours,
            briefing.focus_track, briefing.focus_phase,
        )

        return briefing

    def parse_feedback(self, email_body: str, briefing_tasks: list[dict]) -> EmailFeedback:
        """Parse a natural-language email reply into structured feedback."""
        task_summary = "\n".join(
            f"Task {i+1}: {t['title']}" for i, t in enumerate(briefing_tasks)
        )

        prompt = (
            f"The daily briefing assigned these tasks:\n{task_summary}\n\n"
            f"The user replied with:\n{email_body}\n\n"
            "Parse this into structured feedback."
        )

        response = self._client.messages.create(
            model=self.config.llm.model,
            max_tokens=1024,
            system=FEEDBACK_PARSE_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text
        feedback_data = self._parse_json_response(raw_text)

        from planner_agent.models import FeedbackEntry

        task_updates = []
        for u in feedback_data.get("task_updates", []):
            raw_status = u.get("status", "done")
            try:
                status = TaskStatus(raw_status)
            except ValueError:
                status_map = {
                    "not_mentioned": TaskStatus.PENDING,
                    "not_started": TaskStatus.PENDING,
                    "partial": TaskStatus.IN_PROGRESS,
                }
                status = status_map.get(raw_status, TaskStatus.PENDING)

            task_updates.append(FeedbackEntry(
                task_id=u.get("task_id", 0),
                status=status,
                actual_hours=u.get("actual_hours"),
                notes=u.get("notes", ""),
                learnings=u.get("learnings", ""),
            ))

        return EmailFeedback(
            task_updates=task_updates,
            general_notes=feedback_data.get("general_notes", ""),
            total_hours_reported=feedback_data.get("total_hours_reported"),
        )

    def apply_feedback(self, feedback: EmailFeedback, briefing_tasks: list[dict]) -> int:
        """Apply parsed feedback to the state store. Returns count of tasks updated."""
        updated = 0
        for entry in feedback.task_updates:
            idx = entry.task_id - 1
            if 0 <= idx < len(briefing_tasks):
                task_row = briefing_tasks[idx]
                db_id = task_row.get("db_id") or task_row.get("id")
                if db_id is None:
                    continue

                self.state.update_task_status(
                    task_id=db_id,
                    status=entry.status,
                    actual_hours=entry.actual_hours,
                    learnings=entry.learnings,
                )
                self.state.log_feedback(
                    task_id=db_id,
                    status=entry.status,
                    actual_hours=entry.actual_hours,
                    notes=entry.notes,
                    learnings=entry.learnings,
                    source="email",
                )

                if entry.status == TaskStatus.DONE:
                    track = task_row.get("track", "")
                    hours = entry.actual_hours or task_row.get("estimated_hours", 0)
                    if track:
                        self.state.update_skill_hours(track, hours)

                updated += 1
                logger.info(
                    "Task %d '%s' → %s",
                    entry.task_id, task_row.get("title", ""), entry.status,
                )

        return updated

    def _persist_briefing(self, briefing: DailyBriefing) -> int:
        all_tasks = list(briefing.tasks)

        if briefing.newsletter_reading and briefing.newsletter_reading.articles:
            nr = briefing.newsletter_reading
            article_lines = []
            for a in nr.articles:
                article_lines.append(f"[{a.priority}] {a.title} — {a.url}")
            full_description = nr.description + "\n\n" + "\n".join(article_lines)

            nr_task = Task(
                title=nr.title,
                description=full_description,
                task_type=TaskType.READ,
                track=briefing.focus_track,
                phase=briefing.focus_phase,
                priority=Priority.MEDIUM,
                estimated_hours=nr.estimated_hours,
                resource_url=nr.articles[0].url if nr.articles else "",
                resource_name=nr.title,
                why="Curated newsletter articles relevant to today's focus.",
                status=TaskStatus.PENDING,
                assigned_date=datetime.fromisoformat(briefing.date),
            )
            all_tasks.append(nr_task)

        task_ids = []
        for task in all_tasks:
            task_id = self.state.add_task(task)
            task_ids.append(task_id)

        tasks_json = json.dumps([
            {"db_id": tid, **t.model_dump(mode="json")}
            for tid, t in zip(task_ids, all_tasks, strict=True)
        ])

        briefing_id = self.state.save_briefing(
            date=briefing.date,
            focus_track=briefing.focus_track,
            focus_phase=briefing.focus_phase,
            focus_rationale=briefing.focus_rationale,
            tasks_json=tasks_json,
            portfolio_gaps=briefing.portfolio_gaps,
            skill_observations=briefing.skill_observations,
            newsletter_topics=briefing.newsletter_topics,
            total_hours=briefing.total_estimated_hours,
        )

        self.state.set_meta("last_briefing_date", briefing.date)
        return briefing_id

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from Claude's response, handling markdown code fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines)
            for i in range(1, len(lines)):
                if lines[i].strip() == "```":
                    end = i
                    break
            text = "\n".join(lines[start:end])

        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end], strict=False)
            logger.error("Failed to parse JSON from response: %s", text[:200])
            raise
