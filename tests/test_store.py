"""Tests for StateStore database operations."""

from datetime import UTC, datetime

from planner_agent.models import Phase, Priority, Task, TaskStatus, TaskType
from planner_agent.state.store import StateStore


def _make_store(tmp_path):
    return StateStore(str(tmp_path / "data"))


def _make_task(**overrides):
    defaults = {
        "title": "Test Task",
        "description": "A test task",
        "task_type": TaskType.READ,
        "track": "web_appsec",
        "phase": Phase.LEARN,
        "priority": Priority.MEDIUM,
        "estimated_hours": 1.5,
        "status": TaskStatus.PENDING,
        "assigned_date": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Task(**defaults)


def test_task_add_and_retrieve(tmp_path):
    store = _make_store(tmp_path)
    task = _make_task(title="Read SSRF paper", estimated_hours=2.0)
    task_id = store.add_task(task)

    result = store.get_task_by_id(task_id)
    assert result is not None
    assert result["title"] == "Read SSRF paper"
    assert result["estimated_hours"] == 2.0
    assert result["status"] == "pending"
    assert result["track"] == "web_appsec"


def test_task_status_update(tmp_path):
    store = _make_store(tmp_path)
    task = _make_task(title="Complete lab")
    task_id = store.add_task(task)

    store.update_task_status(task_id, status="done", actual_hours=1.0, learnings="Learned SSRF")

    completed = store.get_recent_completed(days=1)
    assert len(completed) >= 1
    found = next(t for t in completed if t["id"] == task_id)
    assert found["status"] == "done"
    assert found["actual_hours"] == 1.0
    assert found["learnings"] == "Learned SSRF"


def test_skill_hours_accumulate(tmp_path):
    store = _make_store(tmp_path)
    store.upsert_skill("ai_security", "AI/ML Security", "learn", "critical")

    store.update_skill_hours("ai_security", 2.5)
    store.update_skill_hours("ai_security", 1.5)

    skills = store.get_all_skills()
    ai = next(s for s in skills if s["track_id"] == "ai_security")
    assert ai["hours_invested"] == 4.0
    assert ai["items_completed"] == 2


def test_feedback_notes_retrieved(tmp_path):
    store = _make_store(tmp_path)
    task = _make_task(title="SSRF Lab")
    task_id = store.add_task(task)

    store.log_feedback(
        task_id=task_id,
        status="skipped",
        notes="Too basic, already know cloud metadata",
        source="email",
    )

    notes = store.get_recent_feedback_notes(days=7)
    assert len(notes) >= 1
    assert "Too basic" in notes[0]["notes"]
    assert notes[0]["title"] == "SSRF Lab"


def test_briefing_exists_for_date(tmp_path):
    store = _make_store(tmp_path)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    assert store.briefing_exists_for_date(today) is False

    store.save_briefing(
        date=today,
        focus_track="web_appsec",
        focus_phase="learn",
        focus_rationale="Testing",
        tasks_json="[]",
        portfolio_gaps=[],
        skill_observations=[],
        newsletter_topics=[],
        total_hours=4.0,
    )

    assert store.briefing_exists_for_date(today) is True
    assert store.briefing_exists_for_date("2020-01-01") is False
