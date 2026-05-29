"""Tests for the Strategist brain and Orchestrator."""

import json
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.orchestrator import Orchestrator
from planner_agent.agent.strategist import StrategistBrain
from planner_agent.config import AppConfig
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


SAMPLE_BOOTSTRAP_RESPONSE = json.dumps({
    "goals": [
        {
            "title": "Principal Security Engineer at FAANG",
            "description": "Land a principal-level security role",
            "deadline": "2027-01-31",
            "success_criteria": ["Pass system design interviews"],
            "priority": "critical",
        },
        {
            "title": "UK Global Talent Visa",
            "description": "Portfolio for exceptional talent",
            "deadline": "2026-12-31",
            "success_criteria": ["3+ published papers"],
            "priority": "critical",
        },
    ],
    "milestones": [
        {
            "goal_index": 0,
            "title": "Complete AI Security fundamentals",
            "description": "Finish OWASP Top 10 for LLMs",
            "target_date": "2026-07-15",
            "tracks": ["ai_security"],
            "success_criteria": ["Pass quiz"],
            "depends_on_indices": [],
        },
        {
            "goal_index": 1,
            "title": "First research paper draft",
            "description": "Write first paper on AI security",
            "target_date": "2026-08-31",
            "tracks": ["ai_security", "content_creation"],
            "success_criteria": ["Draft reviewed by 2 peers"],
            "depends_on_indices": [0],
        },
    ],
    "directive": {
        "strategic_focus": "Build AI security foundation",
        "weekly_theme": "LLM Attack Surface Week",
        "targets": [
            {
                "track_id": "ai_security",
                "phase": "learn",
                "hours_allocated": 16.0,
                "priority_rank": 1,
                "objectives": ["Read OWASP Top 10 for LLMs"],
                "task_types_allowed": ["read", "lab"],
                "milestone_ids": [1],
                "phase_transition": None,
            },
            {
                "track_id": "web_appsec",
                "phase": "learn",
                "hours_allocated": 12.0,
                "priority_rank": 2,
                "objectives": ["Review SSRF fundamentals"],
                "task_types_allowed": ["read", "lab"],
                "milestone_ids": [],
                "phase_transition": None,
            },
        ],
        "total_hours_available": 28.0,
        "hours_by_track": {"ai_security": 16.0, "web_appsec": 12.0},
        "phase_transitions": [],
        "milestone_targets": [
            {
                "milestone_id": 1,
                "expected_progress": "20% complete",
                "notes": "",
            },
        ],
        "alerts": [],
        "constraints": ["AI Security gets minimum 14h this week"],
        "opportunity_actions": [],
    },
})

SAMPLE_DIRECTIVE_RESPONSE = json.dumps({
    "strategic_focus": "Deepen prompt injection knowledge",
    "weekly_theme": "Prompt Injection Deep Dive",
    "targets": [
        {
            "track_id": "ai_security",
            "phase": "learn",
            "hours_allocated": 18.0,
            "priority_rank": 1,
            "objectives": ["Complete PI labs"],
            "task_types_allowed": ["lab", "research"],
            "milestone_ids": [1],
            "phase_transition": None,
        },
    ],
    "total_hours_available": 28.0,
    "hours_by_track": {"ai_security": 18.0, "web_appsec": 10.0},
    "phase_transitions": [],
    "milestone_targets": [],
    "alerts": [],
    "constraints": [],
    "opportunity_actions": [],
})


# --- Strategist tests ---


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_strategist_bootstrap_seeds_goals_and_milestones(
    mock_anthropic_cls, tmp_path,
):
    store = _make_store(tmp_path)
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_BOOTSTRAP_RESPONSE)]
    mock_response.usage.input_tokens = 2000
    mock_response.usage.output_tokens = 1500
    mock_client.messages.create.return_value = mock_response

    strategist = StrategistBrain(config, store)
    strategist._client = mock_client

    directive = strategist.run(today="2026-05-28")

    goals = store.get_all_goals()
    assert len(goals) == 2
    assert goals[0]["title"] == "Principal Security Engineer at FAANG"
    assert goals[1]["title"] == "UK Global Talent Visa"

    milestones = store.get_all_milestones()
    assert len(milestones) == 2
    assert milestones[0]["tracks"] == ["ai_security"]
    assert milestones[1]["depends_on"] == [milestones[0]["id"]]

    assert directive.weekly_theme == "LLM Attack Surface Week"
    assert directive.total_hours_available == 28.0
    assert len(directive.targets) == 2

    active = store.get_active_directive()
    assert active is not None


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_strategist_plan_week_when_goals_exist(
    mock_anthropic_cls, tmp_path,
):
    store = _make_store(tmp_path)
    config = _make_config()

    from planner_agent.models import Goal
    store.add_goal(Goal(
        title="Test Goal", deadline="2027-01-31", priority="critical",
    ))

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_DIRECTIVE_RESPONSE)]
    mock_response.usage.input_tokens = 1500
    mock_response.usage.output_tokens = 800
    mock_client.messages.create.return_value = mock_response

    strategist = StrategistBrain(config, store)
    strategist._client = mock_client

    directive = strategist.run(today="2026-05-28")

    assert directive.weekly_theme == "Prompt Injection Deep Dive"
    assert len(directive.targets) == 1
    assert directive.targets[0].track_id == "ai_security"


def test_strategist_needs_directive(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    strategist = StrategistBrain.__new__(StrategistBrain)
    strategist.config = config
    strategist.state = store

    assert strategist.needs_directive("2026-05-28") is True

    store.save_directive(
        "2026-05-25", "2026-05-31",
        json.dumps({"theme": "test"}),
    )
    assert strategist.needs_directive("2026-05-28") is False

    assert strategist.needs_directive("2026-06-04") is True


def test_strategist_week_bounds(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    strategist = StrategistBrain.__new__(StrategistBrain)
    strategist.config = config
    strategist.state = store

    start, end = strategist._week_bounds("2026-05-28")
    assert start == "2026-05-25"
    assert end == "2026-05-31"

    start, end = strategist._week_bounds("2026-05-25")
    assert start == "2026-05-25"
    assert end == "2026-05-31"


# --- Orchestrator tests ---


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_orchestrator_triggers_strategist_on_first_run(
    mock_anthropic_cls, tmp_path,
):
    store = _make_store(tmp_path)
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    strategist_response = MagicMock()
    strategist_response.content = [
        MagicMock(text=SAMPLE_BOOTSTRAP_RESPONSE),
    ]
    strategist_response.usage.input_tokens = 2000
    strategist_response.usage.output_tokens = 1500

    tactician_response = MagicMock()
    tactician_response.stop_reason = "end_turn"
    tactician_response.content = [MagicMock(
        type="text",
        text=json.dumps({
            "focus_track": "ai_security",
            "focus_phase": "learn",
            "focus_rationale": "AI Security is highest priority",
            "tasks": [{
                "title": "Test Task",
                "description": "A test",
                "task_type": "read",
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
        strategist_response,
        tactician_response,
    ]

    orchestrator = Orchestrator(config, store)
    briefing = orchestrator.run_daily(target_date="2026-05-28")

    assert briefing.focus_track == "ai_security"
    assert len(briefing.tasks) == 1

    goals = store.get_all_goals()
    assert len(goals) == 2

    assert mock_client.messages.create.call_count == 2


def test_orchestrator_skips_strategist_when_directive_exists(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    from planner_agent.models import Goal
    store.add_goal(Goal(
        title="Test Goal", deadline="2027-01-31",
    ))
    store.save_directive(
        "2026-05-26", "2026-06-01",
        json.dumps({
            "weekly_theme": "Existing",
            "strategic_focus": "Already planned",
        }),
    )

    orchestrator = Orchestrator(config, store)

    assert store.get_active_directive() is not None

    directive = orchestrator._get_active_directive_for_tactician()
    assert directive is not None
    assert directive["weekly_theme"] == "Existing"


# --- Context builder tests ---


def test_strategist_context_bootstrap_includes_instruction():
    from planner_agent.agent.prompts.strategist import build_strategist_context

    ctx = build_strategist_context(
        about_me="Security Engineer at Meta",
        skills=[{
            "track_id": "ai_security",
            "current_phase": "learn",
            "hours_invested": 14.0,
            "items_completed": 8,
            "competence_level": "novice",
        }],
        goals=[],
        milestones=[],
        cumulative_stats=[],
        active_directive=None,
        critic_review=None,
        intelligence_profile_json=None,
        opportunities=[],
        today="2026-05-28",
        weekday_hours=4.0,
        weekend_hours=6.0,
        is_bootstrap=True,
    )

    assert "FIRST RUN" in ctx
    assert "Security Engineer at Meta" in ctx
    assert "TIME BUDGET" in ctx
    assert "Weekly total: 32.0h" in ctx
    assert "SKILL TRACKS" in ctx


def test_strategist_context_normal_includes_goals():
    from planner_agent.agent.prompts.strategist import build_strategist_context

    ctx = build_strategist_context(
        about_me="Security Engineer",
        skills=[],
        goals=[{
            "title": "Principal at FAANG",
            "priority": "critical",
            "deadline": "2027-01-31",
            "status": "active",
            "success_criteria": ["Pass interviews"],
        }],
        milestones=[{
            "title": "AI Security basics",
            "target_date": "2026-07-15",
            "status": "in_progress",
            "tracks": ["ai_security"],
            "goal_id": 1,
        }],
        cumulative_stats=[],
        active_directive=None,
        critic_review=None,
        intelligence_profile_json=None,
        opportunities=[],
        today="2026-06-04",
        weekday_hours=4.0,
        weekend_hours=6.0,
        is_bootstrap=False,
    )

    assert "GOALS" in ctx
    assert "Principal at FAANG" in ctx
    assert "MILESTONES" in ctx
    assert "AI Security basics" in ctx
    assert "Produce an updated StrategicDirective" in ctx
