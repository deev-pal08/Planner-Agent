"""Integration test — full daily cycle through all brains."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.orchestrator import Orchestrator
from planner_agent.config import AppConfig
from planner_agent.models import Goal, Phase, Priority, Task, TaskStatus, TaskType
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
        brains={
            "scout": {"enabled": True, "auto_trigger": True},
            "critic": {"enabled": True},
            "strategist": {"enabled": True},
            "analyst": {"enabled": True},
        },
    )


def _seed_previous_week(store):
    """Seed goals, directive, and tasks for the previous week."""
    store.add_goal(Goal(
        title="Principal Security Engineer at FAANG",
        deadline="2027-01-31",
        priority="critical",
    ))

    store.save_directive(
        "2026-05-18", "2026-05-24",
        json.dumps({
            "weekly_theme": "AI Security Foundations",
            "strategic_focus": "Build foundational knowledge",
            "targets": [{
                "track_id": "ai_security",
                "phase": "learn",
                "hours_allocated": 16.0,
                "priority_rank": 1,
                "objectives": ["OWASP Top 10 for LLMs"],
            }],
            "total_hours_available": 28.0,
        }),
    )

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
            title="Prompt Injection Lab",
            description="Complete the lab",
            task_type=TaskType.LAB,
            track="ai_security",
            phase=Phase.LEARN,
            priority=Priority.HIGH,
            estimated_hours=1.5,
            actual_hours=1.0,
            status=TaskStatus.DONE,
            assigned_date=datetime.fromisoformat("2026-05-20"),
        ),
    ]
    for t in tasks:
        store.add_task(t)

    store.set_meta("learning_summary", "User is making good progress on AI security.")


SCOUT_RESPONSE = json.dumps({
    "opportunities": [{
        "title": "AI Village CTF at DEF CON",
        "description": "AI-focused CTF",
        "opportunity_type": "ctf",
        "deadline": "2026-07-01",
        "tracks": ["ai_security"],
        "priority": "high",
    }],
})

ANALYST_BOOTSTRAP_RESPONSE = json.dumps({
    "last_updated": "2026-05-28",
    "tracks": [{
        "track_id": "ai_security",
        "overall_level": "beginner",
        "learning_velocity": 0.7,
        "phase_readiness": "Not ready for practice yet",
    }],
    "confidence_indicators": ["Good reading discipline"],
    "concern_indicators": [],
    "narrative_summary": "Early stage learner with good habits.",
})

CRITIC_RESPONSE = json.dumps({
    "overall_grade": "B",
    "overall_narrative": "Good week on AI security.",
    "track_assessments": [{
        "track_id": "ai_security",
        "planned_hours": 16.0,
        "actual_hours": 3.5,
        "planned_tasks": 2,
        "completed_tasks": 2,
        "skipped_tasks": 0,
        "quality_assessment": "Solid engagement.",
        "trajectory": "on_track",
        "concerns": [],
    }],
    "milestone_progress": [],
    "planned_total_hours": 28.0,
    "actual_total_hours": 3.5,
    "adherence_score": 0.125,
    "positive_patterns": ["Completed all assigned tasks"],
    "negative_patterns": [],
    "strategic_recommendations": ["Increase hours slightly"],
    "risks": [],
})

STRATEGIST_RESPONSE = json.dumps({
    "strategic_focus": "Deepen prompt injection knowledge",
    "weekly_theme": "Prompt Injection Deep Dive",
    "targets": [{
        "track_id": "ai_security",
        "phase": "learn",
        "hours_allocated": 20.0,
        "priority_rank": 1,
        "objectives": ["Advanced PI techniques"],
        "task_types_allowed": ["lab", "research"],
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
})

TACTICIAN_RESPONSE = json.dumps({
    "focus_track": "ai_security",
    "focus_phase": "learn",
    "focus_rationale": "Directive orders deep dive into prompt injection",
    "tasks": [{
        "title": "Advanced Prompt Injection Lab",
        "description": "Complete advanced PI exercises",
        "task_type": "lab",
        "track": "ai_security",
        "phase": "learn",
        "priority": "high",
        "estimated_hours": 2.5,
    }],
    "total_estimated_hours": 2.5,
    "portfolio_gaps": [],
    "skill_observations": [],
    "newsletter_topics": [],
})


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_full_daily_cycle_all_brains(mock_anthropic_cls, tmp_path):
    """End-to-end: Scout → Analyst bootstrap → Critic → Strategist → Tactician."""
    store = _make_store(tmp_path)
    config = _make_config()
    _seed_previous_week(store)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    def make_response(text):
        resp = MagicMock()
        resp.content = [MagicMock(text=text)]
        resp.usage.input_tokens = 1000
        resp.usage.output_tokens = 500
        resp.stop_reason = "end_turn"
        for block in resp.content:
            block.type = "text"
        return resp

    mock_client.messages.create.side_effect = [
        make_response(ANALYST_BOOTSTRAP_RESPONSE),  # 1. Analyst bootstrap
        make_response(SCOUT_RESPONSE),              # 2. Scout
        make_response(CRITIC_RESPONSE),             # 3. Critic
        make_response(STRATEGIST_RESPONSE),         # 4. Strategist
        make_response(TACTICIAN_RESPONSE),          # 5. Tactician
    ]

    orchestrator = Orchestrator(config, store)
    briefing = orchestrator.run_daily(target_date="2026-05-28")

    assert mock_client.messages.create.call_count == 5

    assert briefing.focus_track == "ai_security"
    assert briefing.tasks[0].title == "Advanced Prompt Injection Lab"

    opps = store.get_all_opportunities()
    assert len(opps) == 1
    assert opps[0]["title"] == "AI Village CTF at DEF CON"

    profile = store.get_meta("user_intelligence_profile")
    assert profile is not None
    assert "beginner" in profile

    review = store.get_latest_review()
    assert review is not None
    assert review["review"]["overall_grade"] == "B"

    directive = store.get_active_directive()
    assert directive is not None
    assert directive["directive"]["weekly_theme"] == "Prompt Injection Deep Dive"

    last_briefing = store.get_last_briefing()
    assert last_briefing is not None
    assert last_briefing["directive_id"] == directive["id"]

    assert orchestrator.last_directive is not None
    assert orchestrator.last_directive["weekly_theme"] == "Prompt Injection Deep Dive"

    scout_tokens = store.get_meta("tokens_scout")
    assert scout_tokens is not None
    data = json.loads(scout_tokens)
    assert data["calls"] == 1

    analyst_tokens = store.get_meta("tokens_analyst")
    assert analyst_tokens is not None

    strategist_tokens = store.get_meta("tokens_strategist")
    assert strategist_tokens is not None

    tactician_tokens = store.get_meta("tokens_tactician")
    assert tactician_tokens is not None

    critic_tokens = store.get_meta("tokens_critic")
    assert critic_tokens is not None


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_daily_cycle_minimal_no_prior_data(mock_anthropic_cls, tmp_path):
    """First ever run: no tasks, no goals — triggers Strategist bootstrap only."""
    store = _make_store(tmp_path)
    config = _make_config()
    config.brains.scout.auto_trigger = False

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    bootstrap_response = MagicMock()
    bootstrap_response.content = [MagicMock(text=json.dumps({
        "goals": [{
            "title": "Test Goal",
            "description": "A goal",
            "deadline": "2027-01-31",
            "success_criteria": ["Pass"],
            "priority": "critical",
        }],
        "milestones": [{
            "goal_index": 0,
            "title": "First milestone",
            "description": "Do the thing",
            "target_date": "2026-07-15",
            "tracks": ["ai_security"],
            "success_criteria": ["Done"],
            "depends_on_indices": [],
        }],
        "directive": {
            "strategic_focus": "Get started",
            "weekly_theme": "Kickoff Week",
            "targets": [{
                "track_id": "ai_security",
                "phase": "learn",
                "hours_allocated": 20.0,
                "priority_rank": 1,
                "objectives": ["Start learning"],
                "task_types_allowed": ["read"],
                "milestone_ids": [1],
                "phase_transition": None,
            }],
            "total_hours_available": 28.0,
            "hours_by_track": {"ai_security": 20.0},
            "phase_transitions": [],
            "milestone_targets": [],
            "alerts": [],
            "constraints": [],
            "opportunity_actions": [],
        },
    }))]
    bootstrap_response.usage.input_tokens = 2000
    bootstrap_response.usage.output_tokens = 1500

    tactician_response = MagicMock()
    tactician_response.stop_reason = "end_turn"
    tactician_response.content = [MagicMock(
        type="text",
        text=TACTICIAN_RESPONSE,
    )]
    tactician_response.usage.input_tokens = 3000
    tactician_response.usage.output_tokens = 500

    mock_client.messages.create.side_effect = [
        bootstrap_response,
        tactician_response,
    ]

    orchestrator = Orchestrator(config, store)
    briefing = orchestrator.run_daily(target_date="2026-05-28")

    assert mock_client.messages.create.call_count == 2

    goals = store.get_all_goals()
    assert len(goals) == 1
    assert goals[0]["title"] == "Test Goal"

    milestones = store.get_all_milestones()
    assert len(milestones) == 1

    assert briefing.focus_track == "ai_security"


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_cost_tracking_accumulates(mock_anthropic_cls, tmp_path):
    """Verify token counts accumulate across multiple API calls."""
    store = _make_store(tmp_path)
    config = _make_config()
    config.brains.scout.auto_trigger = False

    store.add_goal(Goal(
        title="Test Goal", deadline="2027-01-31", priority="critical",
    ))
    store.save_directive(
        "2026-05-25", "2026-05-31",
        json.dumps({"weekly_theme": "Existing"}),
    )

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    resp1 = MagicMock()
    resp1.stop_reason = "end_turn"
    resp1.content = [MagicMock(type="text", text=TACTICIAN_RESPONSE)]
    resp1.usage.input_tokens = 1000
    resp1.usage.output_tokens = 400

    resp2 = MagicMock()
    resp2.stop_reason = "end_turn"
    resp2.content = [MagicMock(type="text", text=TACTICIAN_RESPONSE)]
    resp2.usage.input_tokens = 1200
    resp2.usage.output_tokens = 500

    mock_client.messages.create.side_effect = [resp1, resp2]

    orchestrator = Orchestrator(config, store)
    orchestrator.run_daily(target_date="2026-05-28")

    store.delete_pending_tasks_for_date("2026-05-28")
    store._conn.execute(
        "DELETE FROM daily_briefings WHERE date LIKE '2026-05-28%'"
    )
    store._conn.commit()

    orchestrator.run_daily(target_date="2026-05-28", force=True)

    raw = store.get_meta("tokens_tactician")
    assert raw is not None
    data = json.loads(raw)
    assert data["calls"] == 2
    assert data["input"] == 2200
    assert data["output"] == 900
