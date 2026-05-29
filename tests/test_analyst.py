"""Tests for the Analyst brain — structured competence assessment."""

import json
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.analyst import AnalystBrain
from planner_agent.config import AppConfig
from planner_agent.state.store import StateStore


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")


def _make_store(tmp_path):
    return StateStore(str(tmp_path / "data"))


def _make_config():
    return AppConfig(
        llm={"model": "claude-sonnet-4-20250514"},
    )


SAMPLE_PROFILE_JSON = json.dumps({
    "last_updated": "2026-05-28T00:00:00Z",
    "tracks": [
        {
            "track_id": "ai_security",
            "overall_level": "beginner",
            "sub_skills": [
                {
                    "name": "prompt_injection",
                    "level": "intermediate",
                    "evidence": ["Completed 3 PI labs"],
                    "gaps": ["Indirect PI"],
                    "last_assessed": "2026-05-28",
                },
            ],
            "learning_velocity": 4.0,
            "preferred_resource_types": ["papers", "labs"],
            "difficulty_calibration": "Appropriate",
            "phase_readiness": "Not yet ready for practice",
            "skip_patterns": [],
            "key_learnings": ["Direct vs indirect PI"],
            "resource_quality_notes": [],
        },
    ],
    "general_preferences": {"study_pace": "steady"},
    "engagement_patterns": {"completion_rate": 1.0},
    "confidence_indicators": ["Completed all tasks"],
    "concern_indicators": [],
    "narrative_summary": "User is progressing well in AI security.",
})


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_update_profile_from_scratch(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    store.upsert_skill("ai_security", "AI Security", "learn", "critical")
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_PROFILE_JSON)]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 300
    mock_client.messages.create.return_value = mock_response

    analyst = AnalystBrain(config, store)
    analyst._client = mock_client

    profile = analyst.update_profile()

    assert profile.tracks[0].track_id == "ai_security"
    assert profile.tracks[0].overall_level == "beginner"
    assert len(profile.tracks[0].sub_skills) == 1
    assert profile.narrative_summary == "User is progressing well in AI security."

    stored = store.get_meta("user_intelligence_profile")
    assert stored is not None
    assert "ai_security" in stored

    stored_summary = store.get_meta("learning_summary")
    assert stored_summary == "User is progressing well in AI security."

    history = store.get_competence_history("ai_security")
    assert len(history) == 1
    assert history[0]["competence_level"] == "beginner"
    assert history[0]["learning_velocity"] == 4.0

    skill = store.get_all_skills()[0]
    assert skill["competence_level"] == "beginner"


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_update_from_single_task(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    store.upsert_skill("ai_security", "AI Security", "learn", "critical")
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_PROFILE_JSON)]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 300
    mock_client.messages.create.return_value = mock_response

    analyst = AnalystBrain(config, store)
    analyst._client = mock_client

    task = {
        "track": "ai_security",
        "title": "Read prompt injection paper",
        "estimated_hours": 1.5,
    }
    profile = analyst.update_from_single_task(
        task, status="done", hours=1.0,
        notes="Great paper", learnings="Learned about indirect PI",
    )

    assert profile.tracks[0].track_id == "ai_security"
    mock_client.messages.create.assert_called_once()

    call_kwargs = mock_client.messages.create.call_args[1]
    user_msg = call_kwargs["messages"][0]["content"]
    assert "NEW FEEDBACK" in user_msg
    assert "Read prompt injection paper" in user_msg


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_bootstrap_skips_when_profile_exists(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    store.set_meta("user_intelligence_profile", SAMPLE_PROFILE_JSON)
    store.set_meta("learning_summary", "Old summary")
    config = _make_config()

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    analyst = AnalystBrain(config, store)
    analyst._client = mock_client

    profile = analyst.bootstrap_from_learning_summary()

    mock_client.messages.create.assert_not_called()
    assert profile.tracks[0].track_id == "ai_security"


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_analyst_uses_model_override(mock_anthropic_cls, tmp_path):
    store = _make_store(tmp_path)
    store.upsert_skill("ai_security", "AI Security", "learn", "critical")
    config = _make_config()
    config.brains.analyst.model_override = "claude-haiku-4-5-20251001"

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=SAMPLE_PROFILE_JSON)]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 200
    mock_client.messages.create.return_value = mock_response

    analyst = AnalystBrain(config, store)
    analyst._client = mock_client
    analyst.update_profile()

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


def test_build_analyst_context_includes_sections(tmp_path):
    from planner_agent.agent.prompts.analyst import build_analyst_context

    ctx = build_analyst_context(
        current_profile_json=None,
        new_feedback=[{
            "track": "ai_security",
            "title": "Read paper",
            "status": "done",
            "estimated_hours": 1.0,
            "actual_hours": 1.5,
            "notes": "Good",
            "learnings": "PI basics",
        }],
        cumulative_stats=[{
            "track": "ai_security",
            "done": 5,
            "skipped": 1,
            "hours": 10.0,
        }],
        recent_competence=[],
        all_feedback=[],
        skills=[{
            "track_id": "ai_security",
            "current_phase": "learn",
            "hours_invested": 10.0,
            "items_completed": 5,
        }],
    )

    assert "CURRENT PROFILE" in ctx
    assert "first assessment" in ctx
    assert "NEW FEEDBACK" in ctx
    assert "Read paper" in ctx
    assert "CUMULATIVE TRACK STATS" in ctx
    assert "CURRENT SKILL STATES" in ctx
    assert "INSTRUCTION" in ctx
