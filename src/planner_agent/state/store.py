"""SQLite-backed state manager for the Planner Agent."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from planner_agent.models import (
    Achievement,
    Goal,
    Milestone,
    Opportunity,
    Task,
)

log = logging.getLogger(__name__)

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS skills (
    track_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    current_phase TEXT NOT NULL DEFAULT 'learn',
    priority TEXT NOT NULL DEFAULT 'medium',
    hours_invested REAL DEFAULT 0.0,
    items_completed INTEGER DEFAULT 0,
    confidence_note TEXT DEFAULT '',
    last_assessed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'other',
    track TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'learn',
    priority TEXT NOT NULL DEFAULT 'medium',
    estimated_hours REAL NOT NULL,
    actual_hours REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    resource_url TEXT DEFAULT '',
    resource_name TEXT DEFAULT '',
    why TEXT DEFAULT '',
    learnings TEXT DEFAULT '',
    assigned_date TIMESTAMP NOT NULL,
    completed_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    track TEXT DEFAULT '',
    date_achieved TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TIMESTAMP NOT NULL,
    focus_track TEXT NOT NULL,
    focus_phase TEXT NOT NULL,
    focus_rationale TEXT DEFAULT '',
    tasks_json TEXT NOT NULL,
    portfolio_gaps_json TEXT DEFAULT '[]',
    skill_observations_json TEXT DEFAULT '[]',
    newsletter_topics_json TEXT DEFAULT '[]',
    total_estimated_hours REAL,
    email_sent INTEGER DEFAULT 0,
    email_message_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    actual_hours REAL,
    notes TEXT DEFAULT '',
    learnings TEXT DEFAULT '',
    received_at TIMESTAMP NOT NULL,
    source TEXT DEFAULT 'email',
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_date);
CREATE INDEX IF NOT EXISTS idx_tasks_track ON tasks(track);
CREATE INDEX IF NOT EXISTS idx_briefings_date ON daily_briefings(date);
CREATE INDEX IF NOT EXISTS idx_achievements_type ON achievements(achievement_type);
"""

# ---------------------------------------------------------------------------
# v3 Migration: Multi-Brain tables + column additions
# ---------------------------------------------------------------------------
MIGRATION_V3 = """
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    deadline TEXT,
    success_criteria TEXT DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'high',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    target_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    completion_date TEXT,
    depends_on TEXT DEFAULT '[]',
    tracks TEXT DEFAULT '[]',
    success_criteria TEXT DEFAULT '[]',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS strategic_directives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    directive_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL,
    critic_review_id INTEGER,
    FOREIGN KEY (critic_review_id) REFERENCES weekly_reviews(id)
);

CREATE TABLE IF NOT EXISTS weekly_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    review_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS competence_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id TEXT NOT NULL,
    assessed_at TIMESTAMP NOT NULL,
    assessor TEXT NOT NULL DEFAULT 'analyst',
    phase TEXT NOT NULL,
    competence_level TEXT NOT NULL DEFAULT 'novice',
    sub_skills_json TEXT DEFAULT '{}',
    evidence TEXT DEFAULT '',
    learning_velocity REAL,
    engagement_score REAL,
    notes TEXT DEFAULT '',
    FOREIGN KEY (track_id) REFERENCES skills(track_id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    opportunity_type TEXT NOT NULL,
    url TEXT DEFAULT '',
    deadline TEXT,
    event_start TEXT,
    event_end TEXT,
    tracks TEXT DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'discovered',
    priority TEXT NOT NULL DEFAULT 'medium',
    notes TEXT DEFAULT '',
    location TEXT DEFAULT '',
    source TEXT DEFAULT '',
    discovered_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_milestones_goal ON milestones(goal_id);
CREATE INDEX IF NOT EXISTS idx_milestones_target ON milestones(target_date);
CREATE INDEX IF NOT EXISTS idx_milestones_status ON milestones(status);
CREATE INDEX IF NOT EXISTS idx_directives_week ON strategic_directives(week_start);
CREATE INDEX IF NOT EXISTS idx_directives_status ON strategic_directives(status);
CREATE INDEX IF NOT EXISTS idx_competence_track ON competence_log(track_id);
CREATE INDEX IF NOT EXISTS idx_competence_date ON competence_log(assessed_at);
CREATE INDEX IF NOT EXISTS idx_opportunities_deadline ON opportunities(deadline);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_reviews_week ON weekly_reviews(week_start);
"""

# Columns added to existing tables in v3 (each wrapped individually for idempotency)
_V3_ALTER_COLUMNS = [
    "ALTER TABLE tasks ADD COLUMN milestone_id INTEGER",
    "ALTER TABLE tasks ADD COLUMN directive_id INTEGER",
    "ALTER TABLE tasks ADD COLUMN quality_score REAL",
    "ALTER TABLE tasks ADD COLUMN quality_notes TEXT DEFAULT ''",
    "ALTER TABLE skills ADD COLUMN competence_level TEXT DEFAULT 'novice'",
    "ALTER TABLE skills ADD COLUMN sub_skills_json TEXT DEFAULT '{}'",
    "ALTER TABLE daily_briefings ADD COLUMN directive_id INTEGER",
    "ALTER TABLE opportunities ADD COLUMN location TEXT DEFAULT ''",
]

_V3_ALTER_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tasks_milestone ON tasks(milestone_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_directive ON tasks(directive_id)",
]


class StateStore:
    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.db_path = self.state_dir / "planner.db"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(CREATE_TABLES)
        self._conn.commit()
        self._run_migrations()

    # --- Skills ---

    def upsert_skill(
        self,
        track_id: str,
        name: str,
        current_phase: str = "learn",
        priority: str = "medium",
    ) -> None:
        self._conn.execute(
            """INSERT INTO skills (track_id, name, current_phase, priority, last_assessed)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(track_id) DO UPDATE SET
                   name = excluded.name,
                   current_phase = excluded.current_phase,
                   priority = excluded.priority,
                   last_assessed = excluded.last_assessed""",
            (track_id, name, current_phase, priority, datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

    def get_all_skills(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM skills ORDER BY priority, track_id",
        ).fetchall()
        return [dict(r) for r in rows]

    def update_skill_hours(self, track_id: str, hours: float) -> None:
        self._conn.execute(
            """UPDATE skills SET hours_invested = hours_invested + ?,
               items_completed = items_completed + 1,
               last_assessed = ?
               WHERE track_id = ?""",
            (hours, datetime.now(UTC).isoformat(), track_id),
        )
        self._conn.commit()

    def update_skill_phase(self, track_id: str, phase: str) -> None:
        self._conn.execute(
            "UPDATE skills SET current_phase = ?, last_assessed = ? WHERE track_id = ?",
            (phase, datetime.now(UTC).isoformat(), track_id),
        )
        self._conn.commit()

    # --- Tasks ---

    def add_task(self, task: Task) -> int:
        cursor = self._conn.execute(
            """INSERT INTO tasks
               (title, description, task_type, track, phase, priority,
                estimated_hours, status, resource_url, resource_name,
                why, assigned_date, milestone_id, directive_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.title, task.description, task.task_type, task.track,
                task.phase, task.priority, task.estimated_hours, task.status,
                task.resource_url, task.resource_name, task.why,
                (task.assigned_date or datetime.now(UTC)).isoformat(),
                task.milestone_id, task.directive_id,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_pending_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM tasks WHERE status IN ('pending', 'in_progress')
               ORDER BY assigned_date DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tasks_for_date(self, date: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE DATE(assigned_date) = DATE(?) ORDER BY id",
            (date,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_task_by_id(self, task_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_task_status(
        self,
        task_id: int,
        status: str,
        actual_hours: float | None = None,
        learnings: str = "",
    ) -> None:
        updates = ["status = ?"]
        params: list[Any] = [status]

        if status in ("done", "skipped"):
            updates.append("completed_date = ?")
            params.append(datetime.now(UTC).isoformat())

        if actual_hours is not None:
            updates.append("actual_hours = ?")
            params.append(actual_hours)

        if learnings:
            updates.append("learnings = ?")
            params.append(learnings)

        params.append(task_id)
        self._conn.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        self._conn.commit()

    def get_recent_completed(self, limit: int = 15) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM tasks
               WHERE status = 'done'
               ORDER BY completed_date DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_completion_stats(self, limit: int = 20) -> dict[str, Any]:
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'done'
                    THEN COALESCE(actual_hours, estimated_hours)
                    ELSE 0 END) as hours_done
               FROM (SELECT * FROM tasks ORDER BY assigned_date DESC LIMIT ?)""",
            (limit,),
        ).fetchone()
        if row is None:
            return {"total": 0, "done": 0, "skipped": 0, "pending": 0, "hours_done": 0}
        return dict(row)

    def get_track_stats(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT
                track,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'done'
                    THEN COALESCE(actual_hours, estimated_hours)
                    ELSE 0 END) as hours
               FROM tasks
               GROUP BY track
               ORDER BY hours DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_skipped_patterns(self, limit: int = 40) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT track, task_type, COUNT(*) as skip_count
               FROM (SELECT * FROM tasks ORDER BY assigned_date DESC LIMIT ?)
               WHERE status = 'skipped'
               GROUP BY track, task_type
               HAVING skip_count >= 2
               ORDER BY skip_count DESC""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_consumed_article_urls(self) -> set[str]:
        """Return all URLs from completed tasks — resource_url plus any URLs in description."""
        import re

        urls: set[str] = set()
        rows = self._conn.execute(
            """SELECT resource_url, description FROM tasks
               WHERE status = 'done'""",
        ).fetchall()
        for r in rows:
            if r["resource_url"]:
                urls.add(r["resource_url"])
            if r["description"]:
                urls.update(re.findall(r"https?://\S+", r["description"]))
        return urls

    # --- Achievements ---

    def add_achievement(self, achievement: Achievement) -> int:
        cursor = self._conn.execute(
            """INSERT INTO achievements
               (achievement_type, title, url, description, track, date_achieved)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                achievement.achievement_type, achievement.title,
                achievement.url, achievement.description,
                achievement.track,
                (achievement.date_achieved or datetime.now(UTC)).isoformat(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_all_achievements(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM achievements ORDER BY date_achieved DESC",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_achievement_counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT achievement_type, COUNT(*) as count "
            "FROM achievements GROUP BY achievement_type",
        ).fetchall()
        return {r["achievement_type"]: r["count"] for r in rows}

    # --- Daily Briefings ---

    def save_briefing(
        self,
        date: str,
        focus_track: str,
        focus_phase: str,
        focus_rationale: str,
        tasks_json: str,
        portfolio_gaps: list[str],
        skill_observations: list[str],
        newsletter_topics: list[str],
        total_hours: float,
        directive_id: int | None = None,
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO daily_briefings
               (date, focus_track, focus_phase, focus_rationale, tasks_json,
                portfolio_gaps_json, skill_observations_json,
                newsletter_topics_json, total_estimated_hours, directive_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                date, focus_track, focus_phase, focus_rationale, tasks_json,
                json.dumps(portfolio_gaps), json.dumps(skill_observations),
                json.dumps(newsletter_topics), total_hours, directive_id,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def update_briefing_email(self, briefing_id: int, message_id: str) -> None:
        self._conn.execute(
            "UPDATE daily_briefings SET email_sent = 1, email_message_id = ? WHERE id = ?",
            (message_id, briefing_id),
        )
        self._conn.commit()

    def get_last_briefing(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM daily_briefings ORDER BY date DESC LIMIT 1",
        ).fetchone()
        return dict(row) if row else None

    def briefing_exists_for_date(self, date: str) -> bool:
        row = self._conn.execute(
            "SELECT id FROM daily_briefings WHERE DATE(date) = DATE(?)", (date,),
        ).fetchone()
        return row is not None

    def delete_pending_tasks_for_date(self, date: str) -> int:
        cursor = self._conn.execute(
            "DELETE FROM tasks WHERE DATE(assigned_date) = DATE(?) AND status = 'pending'",
            (date,),
        )
        self._conn.commit()
        return cursor.rowcount

    def get_last_email_message_id(self) -> str | None:
        row = self._conn.execute(
            """SELECT email_message_id FROM daily_briefings
               WHERE email_sent = 1 AND email_message_id != ''
               ORDER BY date DESC LIMIT 1""",
        ).fetchone()
        return row["email_message_id"] if row else None

    # --- Feedback Log ---

    def log_feedback(
        self,
        task_id: int,
        status: str,
        actual_hours: float | None = None,
        notes: str = "",
        learnings: str = "",
        source: str = "email",
    ) -> None:
        self._conn.execute(
            """INSERT INTO feedback_log
               (task_id, status, actual_hours, notes, learnings, received_at, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, status, actual_hours, notes, learnings,
             datetime.now(UTC).isoformat(), source),
        )
        self._conn.commit()

    def get_recent_feedback_notes(self, limit: int = 15) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT f.notes, f.learnings, f.received_at, t.title, t.track
               FROM feedback_log f
               JOIN tasks t ON f.task_id = t.id
               WHERE (
                   (f.notes IS NOT NULL AND f.notes != '')
                   OR (f.learnings IS NOT NULL AND f.learnings != '')
               )
               ORDER BY f.received_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_cumulative_track_stats(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT
                t.track,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN t.status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                SUM(CASE WHEN t.status = 'done'
                    THEN COALESCE(t.actual_hours, t.estimated_hours) ELSE 0 END) as hours,
                MAX(CASE WHEN t.status = 'done' THEN t.completed_date END) as last_completed,
                MIN(t.assigned_date) as first_assigned
               FROM tasks t
               GROUP BY t.track
               ORDER BY hours DESC""",
        ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            type_rows = self._conn.execute(
                """SELECT task_type, COUNT(*) as cnt
                   FROM tasks WHERE track = ? AND status = 'done'
                   GROUP BY task_type ORDER BY cnt DESC LIMIT 3""",
                (row["track"],),
            ).fetchall()
            row["top_task_types"] = [(tr["task_type"], tr["cnt"]) for tr in type_rows]
            result.append(row)
        return result

    def get_all_feedback_with_content(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT f.notes, f.learnings, f.status, f.actual_hours,
                      f.received_at, t.title, t.track, t.task_type
               FROM feedback_log f
               JOIN tasks t ON f.task_id = t.id
               WHERE (f.notes IS NOT NULL AND f.notes != '')
                  OR (f.learnings IS NOT NULL AND f.learnings != '')
               ORDER BY f.received_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Meta ---

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,),
        ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    @property
    def last_briefing_date(self) -> str | None:
        return self.get_meta("last_briefing_date")

    # --- Migration ---

    def _run_migrations(self) -> None:
        """Apply schema migrations idempotently."""
        version = self.get_meta("schema_version") or "v1"
        if version >= "v3":
            return
        log.info("Running v3 migration: multi-brain tables")
        self._conn.executescript(MIGRATION_V3)
        for stmt in _V3_ALTER_COLUMNS:
            try:
                self._conn.execute(stmt)
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
        for stmt in _V3_ALTER_INDEXES:
            self._conn.execute(stmt)
        self._conn.commit()
        self.set_meta("schema_version", "v3")
        log.info("v3 migration complete")

    # --- Goals ---

    def add_goal(self, goal: Goal) -> int:
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO goals
               (title, description, deadline, success_criteria, status, priority,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                goal.title, goal.description, goal.deadline,
                json.dumps(goal.success_criteria), goal.status, goal.priority,
                now, now,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_all_goals(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM goals ORDER BY priority, id",
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["success_criteria"] = json.loads(d.get("success_criteria") or "[]")
            result.append(d)
        return result

    def get_active_goals(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM goals WHERE status = 'active' ORDER BY priority, id",
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["success_criteria"] = json.loads(d.get("success_criteria") or "[]")
            result.append(d)
        return result

    def get_goal_by_id(self, goal_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM goals WHERE id = ?", (goal_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["success_criteria"] = json.loads(d.get("success_criteria") or "[]")
        return d

    def update_goal_status(self, goal_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE goals SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(UTC).isoformat(), goal_id),
        )
        self._conn.commit()

    # --- Milestones ---

    def add_milestone(self, milestone: Milestone) -> int:
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO milestones
               (goal_id, title, description, target_date, status,
                depends_on, tracks, success_criteria, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                milestone.goal_id, milestone.title, milestone.description,
                milestone.target_date, milestone.status,
                json.dumps(milestone.depends_on), json.dumps(milestone.tracks),
                json.dumps(milestone.success_criteria), now, now,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_all_milestones(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM milestones ORDER BY target_date",
        ).fetchall()
        return [self._parse_milestone_row(r) for r in rows]

    def get_milestones_by_goal(self, goal_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM milestones WHERE goal_id = ? ORDER BY target_date",
            (goal_id,),
        ).fetchall()
        return [self._parse_milestone_row(r) for r in rows]

    def get_milestone_by_id(self, milestone_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM milestones WHERE id = ?", (milestone_id,),
        ).fetchone()
        return self._parse_milestone_row(row) if row else None

    def update_milestone_status(self, milestone_id: int, status: str) -> None:
        updates = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, datetime.now(UTC).isoformat()]
        if status == "completed":
            updates.append("completion_date = ?")
            params.append(datetime.now(UTC).strftime("%Y-%m-%d"))
        params.append(milestone_id)
        self._conn.execute(
            f"UPDATE milestones SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        self._conn.commit()

    def _parse_milestone_row(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["depends_on"] = json.loads(d.get("depends_on") or "[]")
        d["tracks"] = json.loads(d.get("tracks") or "[]")
        d["success_criteria"] = json.loads(d.get("success_criteria") or "[]")
        return d

    # --- Strategic Directives ---

    def save_directive(
        self,
        week_start: str,
        week_end: str,
        directive_json: str,
        critic_review_id: int | None = None,
    ) -> int:
        # Supersede any active directive for overlapping weeks
        self._conn.execute(
            "UPDATE strategic_directives SET status = 'superseded' WHERE status = 'active'",
        )
        cursor = self._conn.execute(
            """INSERT INTO strategic_directives
               (week_start, week_end, directive_json, status, created_at, critic_review_id)
               VALUES (?, ?, ?, 'active', ?, ?)""",
            (week_start, week_end, directive_json,
             datetime.now(UTC).isoformat(), critic_review_id),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_active_directive(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM strategic_directives "
            "WHERE status = 'active' ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["directive"] = json.loads(d["directive_json"])
        return d

    def get_directive_by_week(self, week_start: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM strategic_directives "
            "WHERE week_start = ? ORDER BY created_at DESC LIMIT 1",
            (week_start,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["directive"] = json.loads(d["directive_json"])
        return d

    # --- Weekly Reviews ---

    def save_weekly_review(
        self, week_start: str, week_end: str, review_json: str,
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO weekly_reviews (week_start, week_end, review_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (week_start, week_end, review_json, datetime.now(UTC).isoformat()),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_latest_review(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM weekly_reviews ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["review"] = json.loads(d["review_json"])
        return d

    def get_review_by_week(self, week_start: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM weekly_reviews WHERE week_start = ? ORDER BY created_at DESC LIMIT 1",
            (week_start,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["review"] = json.loads(d["review_json"])
        return d

    # --- Competence Log ---

    def add_competence_entry(
        self,
        track_id: str,
        phase: str,
        competence_level: str,
        sub_skills_json: str = "{}",
        evidence: str = "",
        learning_velocity: float | None = None,
        engagement_score: float | None = None,
        notes: str = "",
        assessor: str = "analyst",
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO competence_log
               (track_id, assessed_at, assessor, phase, competence_level,
                sub_skills_json, evidence, learning_velocity, engagement_score, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                track_id, datetime.now(UTC).isoformat(), assessor, phase,
                competence_level, sub_skills_json, evidence,
                learning_velocity, engagement_score, notes,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_competence_history(
        self, track_id: str, limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM competence_log
               WHERE track_id = ? ORDER BY assessed_at DESC LIMIT ?""",
            (track_id, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["sub_skills"] = json.loads(d.get("sub_skills_json") or "{}")
            result.append(d)
        return result

    def get_latest_competence(self, track_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """SELECT * FROM competence_log
               WHERE track_id = ? ORDER BY assessed_at DESC LIMIT 1""",
            (track_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["sub_skills"] = json.loads(d.get("sub_skills_json") or "{}")
        return d

    # --- Opportunities ---

    def add_opportunity(self, opp: Opportunity) -> int:
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO opportunities
               (title, description, opportunity_type, url, deadline,
                event_start, event_end, tracks, status, priority,
                notes, location, source, discovered_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opp.title, opp.description, opp.opportunity_type, opp.url,
                opp.deadline, opp.event_start, opp.event_end,
                json.dumps(opp.tracks), opp.status, opp.priority,
                opp.notes, opp.location, opp.source, now, now,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_all_opportunities(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM opportunities ORDER BY deadline ASC NULLS LAST, priority",
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tracks"] = json.loads(d.get("tracks") or "[]")
            result.append(d)
        return result

    def get_upcoming_opportunities(self, today: str | None = None) -> list[dict[str, Any]]:
        today = today or datetime.now(UTC).strftime("%Y-%m-%d")
        rows = self._conn.execute(
            """SELECT * FROM opportunities
               WHERE status IN ('discovered', 'registered', 'in_progress')
               AND (deadline IS NULL OR deadline >= ?)
               ORDER BY deadline ASC NULLS LAST""",
            (today,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tracks"] = json.loads(d.get("tracks") or "[]")
            result.append(d)
        return result

    def update_opportunity_status(self, opp_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE opportunities SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(UTC).isoformat(), opp_id),
        )
        self._conn.commit()

    # --- Tasks (v3 extensions) ---

    def get_tasks_for_week(
        self, week_start: str, week_end: str,
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM tasks
               WHERE DATE(assigned_date) >= DATE(?)
               AND DATE(assigned_date) <= DATE(?)
               ORDER BY assigned_date, id""",
            (week_start, week_end),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
