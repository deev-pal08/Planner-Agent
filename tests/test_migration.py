"""Tests for v3 schema migration and new table CRUD."""

import json
from datetime import UTC, datetime

from planner_agent.models import (
    Goal,
    Milestone,
    Opportunity,
    Phase,
    Priority,
    Task,
    TaskStatus,
    TaskType,
)
from planner_agent.state.store import StateStore


def _make_store(tmp_path):
    return StateStore(str(tmp_path / "data"))


# --- Migration idempotency ---


def test_migration_runs_on_fresh_db(tmp_path):
    store = _make_store(tmp_path)
    assert store.get_meta("schema_version") == "v3"

    tables = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    ).fetchall()
    table_names = {r["name"] for r in tables}
    for expected in (
        "goals", "milestones", "strategic_directives",
        "weekly_reviews", "competence_log", "opportunities",
    ):
        assert expected in table_names, f"Missing table: {expected}"


def test_migration_idempotent(tmp_path):
    store1 = _make_store(tmp_path)
    store1.upsert_skill("ai_security", "AI Security", "learn", "critical")
    task = Task(
        title="Test", description="Test task", task_type=TaskType.READ,
        track="ai_security", phase=Phase.LEARN, priority=Priority.MEDIUM,
        estimated_hours=1.0, status=TaskStatus.PENDING,
        assigned_date=datetime.now(UTC),
    )
    store1.add_task(task)
    store1.close()

    store2 = StateStore(str(tmp_path / "data"))
    assert store2.get_meta("schema_version") == "v3"
    skills = store2.get_all_skills()
    assert len(skills) == 1
    assert skills[0]["track_id"] == "ai_security"
    store2.close()


def test_existing_data_preserved_after_migration(tmp_path):
    store = _make_store(tmp_path)
    task = Task(
        title="Existing Task", description="Should survive migration",
        task_type=TaskType.LAB, track="web_appsec",
        phase=Phase.PRACTICE, priority=Priority.HIGH,
        estimated_hours=2.0, status=TaskStatus.DONE,
        assigned_date=datetime.now(UTC),
    )
    task_id = store.add_task(task)
    result = store.get_task_by_id(task_id)
    assert result["title"] == "Existing Task"
    assert result["milestone_id"] is None
    assert result["directive_id"] is None


def test_new_task_columns_work(tmp_path):
    store = _make_store(tmp_path)
    task = Task(
        title="Linked Task", description="Has milestone",
        task_type=TaskType.READ, track="ai_security",
        phase=Phase.LEARN, priority=Priority.MEDIUM,
        estimated_hours=1.0, assigned_date=datetime.now(UTC),
        milestone_id=42, directive_id=7,
    )
    task_id = store.add_task(task)
    result = store.get_task_by_id(task_id)
    assert result["milestone_id"] == 42
    assert result["directive_id"] == 7


def test_skills_new_columns(tmp_path):
    store = _make_store(tmp_path)
    store.upsert_skill("ai_security", "AI Security", "learn", "critical")
    skill = store.get_all_skills()[0]
    assert skill["competence_level"] == "novice"
    assert skill["sub_skills_json"] == "{}"


# --- Goals CRUD ---


def test_goal_crud(tmp_path):
    store = _make_store(tmp_path)
    goal = Goal(
        title="Principal Security Engineer",
        description="Land a principal role at FAANG",
        deadline="2026-12-31",
        success_criteria=["Pass system design interviews"],
        priority=Priority.CRITICAL,
    )
    goal_id = store.add_goal(goal)
    assert goal_id > 0

    retrieved = store.get_goal_by_id(goal_id)
    assert retrieved["title"] == "Principal Security Engineer"
    assert retrieved["success_criteria"] == ["Pass system design interviews"]
    assert retrieved["status"] == "active"

    store.update_goal_status(goal_id, "achieved")
    updated = store.get_goal_by_id(goal_id)
    assert updated["status"] == "achieved"

    active = store.get_active_goals()
    assert all(g["id"] != goal_id for g in active)


# --- Milestones CRUD ---


def test_milestone_crud(tmp_path):
    store = _make_store(tmp_path)
    goal_id = store.add_goal(Goal(
        title="Test Goal", deadline="2026-12-31",
    ))
    ms = Milestone(
        goal_id=goal_id,
        title="Complete AI Security fundamentals",
        target_date="2026-07-15",
        tracks=["ai_security"],
        success_criteria=["Pass quiz"],
        depends_on=[],
    )
    ms_id = store.add_milestone(ms)
    assert ms_id > 0

    retrieved = store.get_milestone_by_id(ms_id)
    assert retrieved["title"] == "Complete AI Security fundamentals"
    assert retrieved["tracks"] == ["ai_security"]

    by_goal = store.get_milestones_by_goal(goal_id)
    assert len(by_goal) == 1

    store.update_milestone_status(ms_id, "completed")
    updated = store.get_milestone_by_id(ms_id)
    assert updated["status"] == "completed"
    assert updated["completion_date"] is not None


# --- Strategic Directives CRUD ---


def test_directive_crud(tmp_path):
    store = _make_store(tmp_path)
    directive = {
        "week_start": "2026-05-26",
        "week_end": "2026-06-01",
        "strategic_focus": "AI Security deep dive",
        "weekly_theme": "Prompt Injection Week",
    }
    d_id = store.save_directive(
        "2026-05-26", "2026-06-01", json.dumps(directive),
    )
    assert d_id > 0

    active = store.get_active_directive()
    assert active is not None
    assert active["directive"]["strategic_focus"] == "AI Security deep dive"

    by_week = store.get_directive_by_week("2026-05-26")
    assert by_week is not None


def test_directive_supersedes_previous(tmp_path):
    store = _make_store(tmp_path)
    d1 = json.dumps({"focus": "week1"})
    d2 = json.dumps({"focus": "week2"})

    id1 = store.save_directive("2026-05-26", "2026-06-01", d1)
    id2 = store.save_directive("2026-06-02", "2026-06-08", d2)

    row1 = store._conn.execute(
        "SELECT status FROM strategic_directives WHERE id = ?", (id1,),
    ).fetchone()
    assert row1["status"] == "superseded"

    active = store.get_active_directive()
    assert active["id"] == id2


# --- Weekly Reviews CRUD ---


def test_weekly_review_crud(tmp_path):
    store = _make_store(tmp_path)
    review = {"overall_grade": "B", "narrative": "Good week"}
    r_id = store.save_weekly_review(
        "2026-05-19", "2026-05-25", json.dumps(review),
    )
    assert r_id > 0

    latest = store.get_latest_review()
    assert latest["review"]["overall_grade"] == "B"

    by_week = store.get_review_by_week("2026-05-19")
    assert by_week is not None


# --- Competence Log CRUD ---


def test_competence_log_crud(tmp_path):
    store = _make_store(tmp_path)
    store.upsert_skill("ai_security", "AI Security", "learn", "critical")

    entry_id = store.add_competence_entry(
        track_id="ai_security",
        phase="learn",
        competence_level="beginner",
        sub_skills_json=json.dumps([
            {"name": "prompt_injection", "level": "intermediate"},
        ]),
        evidence="Completed 3 labs on PI",
        learning_velocity=4.0,
        assessor="analyst",
    )
    assert entry_id > 0

    history = store.get_competence_history("ai_security")
    assert len(history) == 1
    assert history[0]["competence_level"] == "beginner"
    assert history[0]["learning_velocity"] == 4.0

    latest = store.get_latest_competence("ai_security")
    assert latest is not None
    assert latest["evidence"] == "Completed 3 labs on PI"


# --- Opportunities CRUD ---


def test_opportunity_crud(tmp_path):
    store = _make_store(tmp_path)
    opp = Opportunity(
        title="DEF CON AI CTF",
        description="Annual AI security CTF",
        opportunity_type="ctf",
        url="https://defcon.org/ctf",
        deadline="2026-08-01",
        tracks=["ai_security"],
    )
    opp_id = store.add_opportunity(opp)
    assert opp_id > 0

    all_opps = store.get_all_opportunities()
    assert len(all_opps) == 1
    assert all_opps[0]["tracks"] == ["ai_security"]

    upcoming = store.get_upcoming_opportunities(today="2026-06-01")
    assert len(upcoming) == 1

    store.update_opportunity_status(opp_id, "expired")
    upcoming_after = store.get_upcoming_opportunities(today="2026-06-01")
    assert len(upcoming_after) == 0


# --- Tasks for week ---


def test_tasks_for_week(tmp_path):
    store = _make_store(tmp_path)
    for day in ("2026-05-26", "2026-05-28", "2026-06-02"):
        task = Task(
            title=f"Task on {day}", description="test",
            task_type=TaskType.READ, track="ai_security",
            phase=Phase.LEARN, priority=Priority.MEDIUM,
            estimated_hours=1.0, assigned_date=datetime.fromisoformat(day),
        )
        store.add_task(task)

    week_tasks = store.get_tasks_for_week("2026-05-26", "2026-06-01")
    assert len(week_tasks) == 2
    titles = [t["title"] for t in week_tasks]
    assert "Task on 2026-05-26" in titles
    assert "Task on 2026-05-28" in titles
