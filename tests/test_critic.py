"""Tests for the Critic brain and its integration with the Orchestrator."""

import json
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.critic import CriticBrain
from planner_agent.agent.prompts.critic import build_critic_context
from planner_agent.config import AppConfig
from planner_agent.models import Phase, Priority, Task, TaskStatus, TaskType
from planner_agent.state.store import StateStore


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")


def _make_store(tmp_path):
    store = StateStore(str(tmp_path / "data"))
    store.upsert_skill("ai_security", "AI Security", "learn", "critical")
    store.upsert_skill("web_appsec", "Web AppSec", "learn", "high")
    return store


def _make_config():
    return AppConfig(
        llm={"model": "claude-sonnet-4-20250514"},
    )


def _seed_last_week_tasks(store):
    """Seed tasks for the previous week (Mon 2026-05-18 to Sun 2026-05-24)."""
    from datetime import datetime
    tasks = [
        Task(
            title="Read OWASP Top 10 for LLMs",
            description="Study LLM risks",
            task_type=TaskType.READ,
            track="ai_security",
            phase=Phase.LEARN,
            priority=Priority.HIGH,
            estimated_hours=2.0,
            actual_hours=2.5,
            status=TaskStatus.DONE,
            assigned_date=datetime.fromisoformat("2026-05-19"),
        ),
        Task(
            title="Prompt Injection Lab 1",
            description="Complete the PortSwigger lab",
            task_type=TaskType.LAB,
            track="ai_security",
            phase=Phase.LEARN,
            priority=Priority.HIGH,
            estimated_hours=1.5,
            status=TaskStatus.SKIPPED,
            assigned_date=datetime.fromisoformat("2026-05-19"),
        ),
        Task(
            title="SSRF Basics Reading",
            description="Read SSRF fundamentals",
            task_type=TaskType.READ,
            track="web_appsec",
            phase=Phase.LEARN,
            priority=Priority.MEDIUM,
            estimated_hours=1.0,
            actual_hours=1.0,
            status=TaskStatus.DONE,
            assigned_date=datetime.fromisoformat("2026-05-20"),
        ),
    ]
    for t in tasks:
        store.add_task(t)


SAMPLE_REVIEW_RESPONSE = json.dumps({
    "overall_grade": "B",
    "overall_narrative": "Solid week on AI security but web appsec fell short.",
    "track_assessments": [
        {
            "track_id": "ai_security",
            "planned_hours": 16.0,
            "actual_hours": 2.5,
            "planned_tasks": 2,
            "completed_tasks": 1,
            "skipped_tasks": 1,
            "quality_assessment": "Good engagement with OWASP material.",
            "trajectory": "on_track",
            "concerns": ["Skipped lab — fatigue?"],
        },
        {
            "track_id": "web_appsec",
            "planned_hours": 12.0,
            "actual_hours": 1.0,
            "planned_tasks": 1,
            "completed_tasks": 1,
            "skipped_tasks": 0,
            "quality_assessment": "Completed reading but minimal depth.",
            "trajectory": "slowing",
            "concerns": ["Only 1h invested vs 12h planned"],
        },
    ],
    "milestone_progress": [],
    "planned_total_hours": 28.0,
    "actual_total_hours": 3.5,
    "adherence_score": 0.125,
    "positive_patterns": ["Completed reading tasks promptly"],
    "negative_patterns": ["Skipping labs", "Web appsec under-invested"],
    "strategic_recommendations": [
        "Reduce web_appsec to 4h — user is not engaging",
        "Add shorter lab exercises to reduce skip rate",
    ],
    "risks": [
        {
            "severity": "warning",
            "description": "No portfolio items in 3 weeks",
            "mitigation": "Force one writeup task this week",
        },
    ],
})


# --- CriticBrain tests ---


def test_critic_week_bounds():
    config = _make_config()
    critic = CriticBrain.__new__(CriticBrain)
    critic.config = config

    start, end = critic._week_bounds("2026-05-28")
    assert start == "2026-05-25"
    assert end == "2026-05-31"


def test_critic_previous_week_bounds():
    config = _make_config()
    critic = CriticBrain.__new__(CriticBrain)
    critic.config = config

    start, end = critic._previous_week_bounds("2026-05-28")
    assert start == "2026-05-18"
    assert end == "2026-05-24"


def test_critic_needs_review_true_when_tasks_exist(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    _seed_last_week_tasks(store)

    critic = CriticBrain.__new__(CriticBrain)
    critic.config = config
    critic.state = store

    assert critic.needs_review("2026-05-28") is True


def test_critic_needs_review_false_when_already_reviewed(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    _seed_last_week_tasks(store)

    store.save_weekly_review(
        "2026-05-18", "2026-05-24",
        json.dumps({"overall_grade": "B"}),
    )

    critic = CriticBrain.__new__(CriticBrain)
    critic.config = config
    critic.state = store

    assert critic.needs_review("2026-05-28") is False


def test_critic_needs_review_false_when_no_tasks(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    critic = CriticBrain.__new__(CriticBrain)
    critic.config = config
    critic.state = store

    assert critic.needs_review("2026-05-28") is False


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_critic_run_produces_review(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    _seed_last_week_tasks(store)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_REVIEW_RESPONSE)]
    mock_response.usage.input_tokens = 2000
    mock_response.usage.output_tokens = 800
    mock_client.messages.create.return_value = mock_response

    critic = CriticBrain(config, store)
    critic._client = mock_client

    review = critic.run(today="2026-05-28")

    assert review.overall_grade == "B"
    assert review.adherence_score == 0.125
    assert len(review.track_assessments) == 2
    assert len(review.strategic_recommendations) == 2
    assert review.week_start == "2026-05-18"
    assert review.week_end == "2026-05-24"

    saved = store.get_review_by_week("2026-05-18")
    assert saved is not None
    assert saved["review"]["overall_grade"] == "B"


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_critic_review_saved_to_db(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    _seed_last_week_tasks(store)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_REVIEW_RESPONSE)]
    mock_response.usage.input_tokens = 2000
    mock_response.usage.output_tokens = 800
    mock_client.messages.create.return_value = mock_response

    critic = CriticBrain(config, store)
    critic._client = mock_client
    critic.run(today="2026-05-28")

    latest = store.get_latest_review()
    assert latest is not None
    assert latest["week_start"] == "2026-05-18"
    assert latest["review"]["overall_narrative"] == (
        "Solid week on AI security but web appsec fell short."
    )


# --- Context builder tests ---


def test_context_includes_directive():
    directive = {
        "directive": {
            "weekly_theme": "Test Theme",
            "strategic_focus": "Focus here",
            "total_hours_available": 28.0,
            "targets": [
                {
                    "track_id": "ai_security",
                    "hours_allocated": 16.0,
                    "phase": "learn",
                    "priority_rank": 1,
                },
            ],
            "constraints": ["Min 14h on AI security"],
        },
    }
    ctx = build_critic_context(
        week_start="2026-05-18",
        week_end="2026-05-24",
        directive=directive,
        tasks=[],
        skills=[],
        goals=[],
        milestones=[],
        cumulative_stats=[],
        feedback_notes=[],
        today="2026-05-28",
    )

    assert "Test Theme" in ctx
    assert "Focus here" in ctx
    assert "ai_security" in ctx
    assert "Min 14h on AI security" in ctx


def test_context_includes_tasks():
    tasks = [
        {
            "title": "Read OWASP",
            "status": "done",
            "track": "ai_security",
            "estimated_hours": 2.0,
            "actual_hours": 2.5,
        },
        {
            "title": "Lab 1",
            "status": "skipped",
            "track": "ai_security",
            "estimated_hours": 1.5,
        },
    ]
    ctx = build_critic_context(
        week_start="2026-05-18",
        week_end="2026-05-24",
        directive=None,
        tasks=tasks,
        skills=[],
        goals=[],
        milestones=[],
        cumulative_stats=[],
        feedback_notes=[],
        today="2026-05-28",
    )

    assert "2 total, 1 done, 1 skipped" in ctx
    assert "Read OWASP" in ctx
    assert "Lab 1" in ctx
    assert "PER-TRACK SUMMARY" in ctx


def test_context_no_directive():
    ctx = build_critic_context(
        week_start="2026-05-18",
        week_end="2026-05-24",
        directive=None,
        tasks=[],
        skills=[],
        goals=[],
        milestones=[],
        cumulative_stats=[],
        feedback_notes=[],
        today="2026-05-28",
    )

    assert "No directive was active" in ctx


def test_context_includes_goals_and_milestones():
    ctx = build_critic_context(
        week_start="2026-05-18",
        week_end="2026-05-24",
        directive=None,
        tasks=[],
        skills=[],
        goals=[{
            "title": "Principal at FAANG",
            "priority": "critical",
            "deadline": "2027-01-31",
        }],
        milestones=[{
            "title": "AI Security basics",
            "target_date": "2026-07-15",
            "status": "in_progress",
            "tracks": ["ai_security"],
        }],
        cumulative_stats=[],
        feedback_notes=[],
        today="2026-05-28",
    )

    assert "Principal at FAANG" in ctx
    assert "AI Security basics" in ctx


# --- Orchestrator integration ---


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_orchestrator_runs_critic_before_strategist(mock_anthropic_cls, tmp_path):
    """When Strategist needs a new directive, Critic should run first."""
    store = _make_store(tmp_path)
    config = _make_config()
    _seed_last_week_tasks(store)

    from planner_agent.models import Goal
    store.add_goal(Goal(
        title="Test Goal", deadline="2027-01-31", priority="critical",
    ))

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    critic_response = MagicMock()
    critic_response.content = [MagicMock(text=SAMPLE_REVIEW_RESPONSE)]
    critic_response.usage.input_tokens = 2000
    critic_response.usage.output_tokens = 800

    strategist_response = MagicMock()
    strategist_response.content = [MagicMock(text=json.dumps({
        "strategic_focus": "Post-review focus",
        "weekly_theme": "Recovery Week",
        "targets": [{
            "track_id": "ai_security",
            "phase": "learn",
            "hours_allocated": 20.0,
            "priority_rank": 1,
            "objectives": ["Catch up on labs"],
            "task_types_allowed": ["lab"],
            "milestone_ids": [],
            "phase_transition": None,
        }],
        "total_hours_available": 28.0,
        "hours_by_track": {"ai_security": 20.0, "web_appsec": 8.0},
        "phase_transitions": [],
        "milestone_targets": [],
        "alerts": [],
        "constraints": [],
        "opportunity_actions": [],
    }))]
    strategist_response.usage.input_tokens = 3000
    strategist_response.usage.output_tokens = 1000

    tactician_response = MagicMock()
    tactician_response.stop_reason = "end_turn"
    tactician_response.content = [MagicMock(
        type="text",
        text=json.dumps({
            "focus_track": "ai_security",
            "focus_phase": "learn",
            "focus_rationale": "Recovering from last week",
            "tasks": [{
                "title": "Lab catch-up",
                "description": "Complete skipped labs",
                "task_type": "lab",
                "track": "ai_security",
                "phase": "learn",
                "priority": "high",
                "estimated_hours": 2.0,
            }],
            "total_estimated_hours": 2.0,
            "portfolio_gaps": [],
            "skill_observations": [],
            "newsletter_topics": [],
        }),
    )]
    tactician_response.usage.input_tokens = 3000
    tactician_response.usage.output_tokens = 500

    mock_client.messages.create.side_effect = [
        critic_response,
        strategist_response,
        tactician_response,
    ]

    from planner_agent.agent.orchestrator import Orchestrator
    orchestrator = Orchestrator(config, store)
    briefing = orchestrator.run_daily(target_date="2026-05-28")

    assert mock_client.messages.create.call_count == 3

    review = store.get_latest_review()
    assert review is not None
    assert review["review"]["overall_grade"] == "B"

    directive = store.get_active_directive()
    assert directive is not None
    assert directive["directive"]["weekly_theme"] == "Recovery Week"

    assert briefing.focus_track == "ai_security"


def test_orchestrator_skips_critic_when_directive_exists(tmp_path):
    """Critic should not run when a directive already exists for this week."""
    store = _make_store(tmp_path)
    config = _make_config()

    from planner_agent.models import Goal
    store.add_goal(Goal(title="Test Goal", deadline="2027-01-31"))
    store.save_directive(
        "2026-05-25", "2026-05-31",
        json.dumps({"weekly_theme": "Existing"}),
    )

    from planner_agent.agent.orchestrator import Orchestrator
    orchestrator = Orchestrator(config, store)

    orchestrator._maybe_run_critic("2026-05-28")

    assert store.get_latest_review() is None


def test_orchestrator_skips_critic_when_disabled(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    config.brains.critic.enabled = False
    _seed_last_week_tasks(store)

    from planner_agent.agent.orchestrator import Orchestrator
    orchestrator = Orchestrator(config, store)

    orchestrator._maybe_run_critic("2026-05-28")

    assert store.get_latest_review() is None
