"""SQLite-backed state manager for the Planner Agent."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from planner_agent.models import (
    Achievement,
    AchievementType,
    Phase,
    Priority,
    Task,
    TaskStatus,
    TaskType,
)

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
                why, assigned_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.title, task.description, task.task_type, task.track,
                task.phase, task.priority, task.estimated_hours, task.status,
                task.resource_url, task.resource_name, task.why,
                (task.assigned_date or datetime.now(UTC)).isoformat(),
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

    def get_recent_completed(self, days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM tasks
               WHERE status = 'done'
               AND completed_date >= datetime('now', ?)
               ORDER BY completed_date DESC LIMIT ?""",
            (f"-{days} days", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_completion_stats(self, days: int = 7) -> dict[str, Any]:
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'done' THEN COALESCE(actual_hours, estimated_hours) ELSE 0 END) as hours_done
               FROM tasks
               WHERE assigned_date >= datetime('now', ?)""",
            (f"-{days} days",),
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
                SUM(CASE WHEN status = 'done' THEN COALESCE(actual_hours, estimated_hours) ELSE 0 END) as hours
               FROM tasks
               GROUP BY track
               ORDER BY hours DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_skipped_patterns(self, days: int = 14) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT track, task_type, COUNT(*) as skip_count
               FROM tasks
               WHERE status = 'skipped'
               AND assigned_date >= datetime('now', ?)
               GROUP BY track, task_type
               HAVING skip_count >= 2
               ORDER BY skip_count DESC""",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_consumed_article_urls(self) -> set[str]:
        """Return all resource_urls from completed tasks — these are 'already read'."""
        rows = self._conn.execute(
            """SELECT DISTINCT resource_url FROM tasks
               WHERE status = 'done'
               AND resource_url != ''
               AND resource_url IS NOT NULL""",
        ).fetchall()
        return {r["resource_url"] for r in rows}

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
            "SELECT achievement_type, COUNT(*) as count FROM achievements GROUP BY achievement_type",
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
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO daily_briefings
               (date, focus_track, focus_phase, focus_rationale, tasks_json,
                portfolio_gaps_json, skill_observations_json,
                newsletter_topics_json, total_estimated_hours)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                date, focus_track, focus_phase, focus_rationale, tasks_json,
                json.dumps(portfolio_gaps), json.dumps(skill_observations),
                json.dumps(newsletter_topics), total_hours,
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

    def close(self) -> None:
        self._conn.close()
