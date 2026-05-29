"""Phase 3 tests — directive-aware Tactician, phase transitions, email templates."""

import json
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.loop import PlannerAgent
from planner_agent.config import AppConfig
from planner_agent.email.templates import (
    _render_directive_banner,
    render_briefing_html,
)
from planner_agent.models import DailyBriefing, Phase, Task, TaskStatus, TaskType
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


def _sample_directive():
    return {
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
        "milestone_targets": [],
        "alerts": [
            {"severity": "high", "message": "CTF deadline in 5 days"},
        ],
        "constraints": ["AI Security gets minimum 14h this week"],
        "opportunity_actions": [],
    }


SAMPLE_TACTICIAN_RESPONSE = json.dumps({
    "focus_track": "ai_security",
    "focus_phase": "learn",
    "focus_rationale": "AI Security is highest priority per directive",
    "tasks": [
        {
            "title": "Read OWASP Top 10 for LLMs",
            "description": "Study the OWASP Top 10 risks for LLM applications",
            "task_type": "read",
            "track": "ai_security",
            "phase": "learn",
            "priority": "high",
            "estimated_hours": 2.0,
            "milestone_id": 1,
        },
        {
            "title": "SSRF Lab: Basic exploitation",
            "description": "Complete the PortSwigger SSRF basics lab",
            "task_type": "lab",
            "track": "web_appsec",
            "phase": "learn",
            "priority": "medium",
            "estimated_hours": 1.5,
        },
    ],
    "total_estimated_hours": 3.5,
    "portfolio_gaps": [],
    "skill_observations": [],
    "newsletter_topics": [],
})


# --- Directive-aware briefing generation ---


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_tactician_generates_briefing_with_directive(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    directive = _sample_directive()

    store.save_directive(
        "2026-05-25", "2026-05-31",
        json.dumps(directive),
    )

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(type="text", text=SAMPLE_TACTICIAN_RESPONSE)]
    mock_response.usage.input_tokens = 3000
    mock_response.usage.output_tokens = 500
    mock_client.messages.create.return_value = mock_response

    agent = PlannerAgent(config, store)
    agent._client = mock_client

    briefing = agent.generate_briefing(
        target_date="2026-05-28", directive=directive,
    )

    assert briefing.focus_track == "ai_security"
    assert len(briefing.tasks) == 2
    assert briefing.tasks[0].milestone_id == 1
    assert briefing.tasks[0].directive_id is not None


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_tactician_links_directive_id_to_tasks(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    directive = _sample_directive()

    dir_id = store.save_directive(
        "2026-05-25", "2026-05-31",
        json.dumps(directive),
    )

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(type="text", text=SAMPLE_TACTICIAN_RESPONSE)]
    mock_response.usage.input_tokens = 3000
    mock_response.usage.output_tokens = 500
    mock_client.messages.create.return_value = mock_response

    agent = PlannerAgent(config, store)
    agent._client = mock_client

    briefing = agent.generate_briefing(
        target_date="2026-05-28", directive=directive,
    )

    for task in briefing.tasks:
        assert task.directive_id == dir_id

    last_briefing = store.get_last_briefing()
    assert last_briefing is not None
    assert last_briefing.get("directive_id") == dir_id


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_tactician_works_without_directive(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(type="text", text=SAMPLE_TACTICIAN_RESPONSE)]
    mock_response.usage.input_tokens = 3000
    mock_response.usage.output_tokens = 500
    mock_client.messages.create.return_value = mock_response

    agent = PlannerAgent(config, store)
    agent._client = mock_client

    briefing = agent.generate_briefing(target_date="2026-05-28")

    assert briefing.focus_track == "ai_security"
    assert len(briefing.tasks) == 2
    for task in briefing.tasks:
        assert task.directive_id is None


# --- Phase transitions ---


def _get_skill(store, track_id):
    return next(s for s in store.get_all_skills() if s["track_id"] == track_id)


def test_execute_phase_transitions(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    agent = object.__new__(PlannerAgent)
    agent.config = config
    agent.state = store

    skill_before = _get_skill(store, "ai_security")
    assert skill_before["current_phase"] == "learn"

    directive = {
        "phase_transitions": [
            {
                "track_id": "ai_security",
                "from_phase": "learn",
                "to_phase": "practice",
                "rationale": "Completed all learning materials",
            },
        ],
    }

    agent._execute_phase_transitions(directive)

    skill_after = _get_skill(store, "ai_security")
    assert skill_after["current_phase"] == "practice"


def test_execute_phase_transitions_empty_list(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    agent = object.__new__(PlannerAgent)
    agent.config = config
    agent.state = store

    directive = {"phase_transitions": []}
    agent._execute_phase_transitions(directive)

    skill = _get_skill(store, "ai_security")
    assert skill["current_phase"] == "learn"


def test_execute_phase_transitions_no_key(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    agent = object.__new__(PlannerAgent)
    agent.config = config
    agent.state = store

    agent._execute_phase_transitions({})

    skill = _get_skill(store, "ai_security")
    assert skill["current_phase"] == "learn"


def test_execute_multiple_phase_transitions(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    agent = object.__new__(PlannerAgent)
    agent.config = config
    agent.state = store

    directive = {
        "phase_transitions": [
            {"track_id": "ai_security", "to_phase": "practice"},
            {"track_id": "web_appsec", "to_phase": "produce"},
        ],
    }

    agent._execute_phase_transitions(directive)

    assert _get_skill(store, "ai_security")["current_phase"] == "practice"
    assert _get_skill(store, "web_appsec")["current_phase"] == "produce"


# --- Email template rendering ---


def _sample_briefing():
    return DailyBriefing(
        date="2026-05-28",
        focus_track="ai_security",
        focus_phase=Phase.LEARN,
        focus_rationale="AI Security is the top priority this week",
        tasks=[
            Task(
                title="Read OWASP Top 10 for LLMs",
                description="Study the risks",
                task_type=TaskType.READ,
                track="ai_security",
                phase=Phase.LEARN,
                priority="high",
                estimated_hours=2.0,
                status=TaskStatus.PENDING,
            ),
        ],
        total_estimated_hours=2.0,
        portfolio_gaps=[],
        skill_observations=[],
        newsletter_topics=[],
    )


def test_render_directive_banner_with_directive():
    directive = _sample_directive()
    html = _render_directive_banner(directive)

    assert "Weekly Directive" in html
    assert "LLM Attack Surface Week" in html
    assert "Build AI security foundation" in html
    assert "Ai Security" in html
    assert "Web Appsec" in html
    assert "16.0h" in html
    assert "12.0h" in html
    assert "CTF deadline in 5 days" in html
    assert "AI Security gets minimum 14h this week" in html


def test_render_directive_banner_none():
    html = _render_directive_banner(None)
    assert html == ""


def test_render_directive_banner_empty_dict():
    html = _render_directive_banner({})
    assert html == ""


def test_render_briefing_html_with_directive():
    briefing = _sample_briefing()
    directive = _sample_directive()

    html = render_briefing_html(briefing, directive=directive)

    assert "DAILY BRIEFING" in html
    assert "2026-05-28" in html
    assert "Weekly Directive" in html
    assert "LLM Attack Surface Week" in html
    assert "Read OWASP Top 10 for LLMs" in html


def test_render_briefing_html_without_directive():
    briefing = _sample_briefing()
    html = render_briefing_html(briefing)

    assert "DAILY BRIEFING" in html
    assert "2026-05-28" in html
    assert "Weekly Directive" not in html
    assert "Read OWASP Top 10 for LLMs" in html


def test_render_directive_banner_no_alerts_no_constraints():
    directive = {
        "weekly_theme": "Focus Week",
        "strategic_focus": "Deep dive",
        "targets": [
            {
                "track_id": "ai_security",
                "phase": "learn",
                "hours_allocated": 10.0,
                "priority_rank": 1,
                "objectives": ["Study basics"],
                "task_types_allowed": ["read"],
            },
        ],
        "alerts": [],
        "constraints": [],
    }
    html = _render_directive_banner(directive)

    assert "Focus Week" in html
    assert "Alerts" not in html
    assert "Constraints" not in html


# --- Orchestrator last_directive ---


def test_orchestrator_exposes_last_directive(tmp_path):
    from planner_agent.agent.orchestrator import Orchestrator

    store = _make_store(tmp_path)
    config = _make_config()

    orchestrator = Orchestrator(config, store)
    assert orchestrator.last_directive is None
