"""Tests for the Scout brain and its integration with the Orchestrator."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.prompts.scout import build_scout_context
from planner_agent.agent.scout import ScoutBrain
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


SAMPLE_SCOUT_RESPONSE = json.dumps({
    "opportunities": [
        {
            "title": "DEF CON 34 CTF Qualifiers",
            "description": "Annual CTF — qualifiers are online",
            "opportunity_type": "ctf",
            "url": "https://defcon.org/ctf",
            "deadline": "2026-06-15",
            "event_start": "2026-08-07",
            "event_end": "2026-08-10",
            "tracks": ["ai_security", "web_appsec"],
            "priority": "high",
            "notes": "Great for portfolio",
        },
        {
            "title": "Black Hat USA 2026 CFP",
            "description": "Submit a briefing proposal",
            "opportunity_type": "conference_cfp",
            "url": "https://blackhat.com/cfp",
            "deadline": "2026-07-01",
            "tracks": ["ai_security"],
            "priority": "critical",
            "notes": "Target for GTV portfolio",
        },
        {
            "title": "HackerOne AI Bug Bounty",
            "description": "New AI-specific bounty program",
            "opportunity_type": "bounty_program",
            "url": "https://hackerone.com/ai-bounty",
            "deadline": None,
            "event_start": "2026-06-01",
            "tracks": ["ai_security", "bug_bounty"],
            "priority": "medium",
            "notes": "Ongoing program",
        },
    ],
    "search_terms_used": ["security CTF 2026", "AI security CFP"],
    "coverage_notes": "Focused on Q3 2026 AI security events",
})


# --- ScoutBrain tests ---


def test_scout_needs_run_true_when_never_run(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    scout = ScoutBrain.__new__(ScoutBrain)
    scout.config = config
    scout.state = store

    assert scout.needs_run() is True


def test_scout_needs_run_false_when_recent(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    store.set_meta("scout_last_run", datetime.now(UTC).isoformat())

    scout = ScoutBrain.__new__(ScoutBrain)
    scout.config = config
    scout.state = store

    assert scout.needs_run() is False


def test_scout_needs_run_true_when_stale(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    old = (datetime.now(UTC) - timedelta(days=4)).isoformat()
    store.set_meta("scout_last_run", old)

    scout = ScoutBrain.__new__(ScoutBrain)
    scout.config = config
    scout.state = store

    assert scout.needs_run() is True


def test_scout_needs_run_custom_interval(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    two_days_ago = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    store.set_meta("scout_last_run", two_days_ago)

    scout = ScoutBrain.__new__(ScoutBrain)
    scout.config = config
    scout.state = store

    assert scout.needs_run(interval_days=1) is True
    assert scout.needs_run(interval_days=3) is False


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_scout_run_discovers_opportunities(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = SAMPLE_SCOUT_RESPONSE

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.stop_reason = "end_turn"
    mock_response.usage.input_tokens = 1000
    mock_response.usage.output_tokens = 500
    mock_client.messages.create.return_value = mock_response

    scout = ScoutBrain(config, store)
    scout._client = mock_client

    opportunities = scout.run(today="2026-05-28")

    assert len(opportunities) == 3
    assert opportunities[0].title == "DEF CON 34 CTF Qualifiers"
    assert opportunities[0].opportunity_type == "ctf"
    assert opportunities[1].priority == "critical"
    assert opportunities[2].deadline is None

    all_opps = store.get_all_opportunities()
    assert len(all_opps) == 3

    last_run = store.get_meta("scout_last_run")
    assert last_run is not None


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_scout_handles_invalid_types_gracefully(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()

    response_data = json.dumps({
        "opportunities": [{
            "title": "Unknown Event",
            "description": "Something weird",
            "opportunity_type": "unknown_type",
            "tracks": ["ai_security"],
            "priority": "unknown_priority",
        }],
    })

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = response_data

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.stop_reason = "end_turn"
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 200
    mock_client.messages.create.return_value = mock_response

    scout = ScoutBrain(config, store)
    scout._client = mock_client

    opportunities = scout.run(today="2026-05-28")

    assert len(opportunities) == 1
    assert opportunities[0].opportunity_type == "other"
    assert opportunities[0].priority == "medium"


# --- Context builder tests ---


def test_context_includes_skills():
    ctx = build_scout_context(
        skills=[{
            "track_id": "ai_security",
            "name": "AI Security",
            "current_phase": "learn",
            "hours_invested": 14.0,
        }],
        goals=[],
        existing_opportunities=[],
        achievements=[],
        today="2026-05-28",
    )

    assert "AI Security" in ctx
    assert "ai_security" in ctx
    assert "first scout run" in ctx


def test_context_includes_goals():
    ctx = build_scout_context(
        skills=[],
        goals=[{
            "title": "Principal at FAANG",
            "priority": "critical",
            "deadline": "2027-01-31",
        }],
        existing_opportunities=[],
        achievements=[],
        today="2026-05-28",
    )

    assert "Principal at FAANG" in ctx
    assert "CAREER GOALS" in ctx


def test_context_shows_existing_opportunities():
    ctx = build_scout_context(
        skills=[],
        goals=[],
        existing_opportunities=[{
            "title": "DEF CON CTF",
            "status": "registered",
            "opportunity_type": "ctf",
            "deadline": "2026-06-15",
        }],
        achievements=[],
        today="2026-05-28",
    )

    assert "DEF CON CTF" in ctx
    assert "do not duplicate" in ctx.lower()


def test_context_includes_achievements():
    ctx = build_scout_context(
        skills=[],
        goals=[],
        existing_opportunities=[],
        achievements=[{
            "title": "Atlassian HoF",
            "achievement_type": "hall_of_fame",
        }],
        today="2026-05-28",
    )

    assert "Atlassian HoF" in ctx
    assert "PORTFOLIO" in ctx


# --- Orchestrator integration ---


def test_orchestrator_skips_scout_when_disabled(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    config.brains.scout.enabled = False
    config.brains.scout.auto_trigger = True

    from planner_agent.agent.orchestrator import Orchestrator
    orchestrator = Orchestrator(config, store)
    orchestrator._maybe_run_scout()

    assert store.get_meta("scout_last_run") is None


def test_orchestrator_skips_scout_when_auto_trigger_false(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    config.brains.scout.enabled = True
    config.brains.scout.auto_trigger = False

    from planner_agent.agent.orchestrator import Orchestrator
    orchestrator = Orchestrator(config, store)
    orchestrator._maybe_run_scout()

    assert store.get_meta("scout_last_run") is None


def test_orchestrator_skips_scout_when_recent(tmp_path):
    store = _make_store(tmp_path)
    config = _make_config()
    config.brains.scout.enabled = True
    config.brains.scout.auto_trigger = True

    store.set_meta("scout_last_run", datetime.now(UTC).isoformat())

    from planner_agent.agent.orchestrator import Orchestrator
    orchestrator = Orchestrator(config, store)
    orchestrator._maybe_run_scout()

    opps = store.get_all_opportunities()
    assert len(opps) == 0
