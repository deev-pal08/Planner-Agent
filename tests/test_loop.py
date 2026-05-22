"""Tests for _parse_json_response and BriefingParseError."""

import pytest

from planner_agent.agent.loop import BriefingParseError, PlannerAgent


class FakeConfig:
    class LLM:
        api_key = "fake"
        model = "fake"
        research_model = "fake"
        max_tokens = 8192
        api_key_env = "ANTHROPIC_API_KEY"

    llm = LLM()
    about_me = ""

    class TimeBudget:
        weekday = 4.0
        weekend_day = 6.0

    time_budget = TimeBudget()

    class Newsletter:
        enabled = False
        project_dir = ""

    newsletter = Newsletter()

    class Email:
        enabled = False

    email = Email()

    state_dir = "/tmp/fake"
    tracks = {}


def _make_agent():
    agent = object.__new__(PlannerAgent)
    agent.config = FakeConfig()
    return agent


def test_parse_clean_json():
    agent = _make_agent()
    result = agent._parse_json_response('{"tasks": [], "focus_track": "ai_security"}')
    assert result["focus_track"] == "ai_security"
    assert result["tasks"] == []


def test_parse_markdown_fenced_json():
    agent = _make_agent()
    text = '```json\n{"tasks": [{"title": "test"}], "date": "2026-05-22"}\n```'
    result = agent._parse_json_response(text)
    assert result["date"] == "2026-05-22"
    assert len(result["tasks"]) == 1


def test_parse_raises_on_invalid():
    agent = _make_agent()
    with pytest.raises(BriefingParseError):
        agent._parse_json_response("this is not json at all")


def test_parse_raises_on_empty_string():
    agent = _make_agent()
    with pytest.raises(BriefingParseError):
        agent._parse_json_response("")
