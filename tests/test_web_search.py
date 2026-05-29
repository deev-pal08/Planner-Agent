"""Tests for multi-source web_search tool integration."""

import json
from unittest.mock import MagicMock, patch

import pytest

from planner_agent.agent.loop import PlannerAgent
from planner_agent.config import AppConfig


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")


def _make_agent(tmp_path, monkeypatch, *, search_enabled=True, search_overrides=None):
    from planner_agent.state.store import StateStore

    search_cfg = {"enabled": search_enabled}
    if search_overrides:
        search_cfg.update(search_overrides)
    config = AppConfig(
        llm={"model": "claude-sonnet-4-20250514"},
        search=search_cfg,
    )
    store = StateStore(str(tmp_path / "data"))
    return PlannerAgent(config, store)


def test_web_search_disabled(tmp_path, monkeypatch):
    agent = _make_agent(tmp_path, monkeypatch, search_enabled=False)
    result = agent._web_search("test query")
    assert "error" in result
    assert "disabled" in result["error"]


def test_web_search_no_api_keys(tmp_path, monkeypatch):
    for key in ("BRAVE_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    agent = _make_agent(tmp_path, monkeypatch)
    result = agent._web_search("test query")
    assert "error" in result
    assert "No search providers" in result["error"]


def test_brave_only(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    agent = _make_agent(tmp_path, monkeypatch)

    with patch.object(agent, "_search_brave", return_value=[
        {"title": "Brave Result", "url": "https://brave.example.com", "source": "brave"},
    ]) as mock_brave:
        result = agent._web_search("test")
        mock_brave.assert_called_once()

    assert result["result_count"] == 1
    assert result["sources"] == ["brave"]
    assert result["results"][0]["source"] == "brave"


def test_tavily_only(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    agent = _make_agent(tmp_path, monkeypatch)

    with patch.object(agent, "_search_tavily", return_value=[
        {"title": "Tavily Result", "url": "https://tavily.example.com", "source": "tavily"},
    ]):
        result = agent._web_search("test")

    assert result["sources"] == ["tavily"]
    assert result["results"][0]["source"] == "tavily"


def test_exa_only(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("EXA_API_KEY", "test-exa")
    agent = _make_agent(tmp_path, monkeypatch)

    with patch.object(agent, "_search_exa", return_value=[
        {"title": "Exa Result", "url": "https://exa.example.com", "source": "exa"},
    ]):
        result = agent._web_search("test")

    assert result["sources"] == ["exa"]
    assert result["results"][0]["source"] == "exa"


def test_multi_source_merges_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("EXA_API_KEY", "test-exa")
    agent = _make_agent(tmp_path, monkeypatch)

    brave_results = [
        {"title": "SSRF Labs", "url": "https://portswigger.net/ssrf", "source": "brave"},
        {"title": "PI CTF", "url": "https://github.com/pi-ctf", "source": "brave"},
    ]
    tavily_results = [
        {"title": "SSRF Labs (Tavily)", "url": "https://portswigger.net/ssrf", "source": "tavily"},
        {"title": "Tavily Unique", "url": "https://tavily-unique.com", "source": "tavily"},
    ]
    exa_results = [
        {"title": "Exa Unique", "url": "https://exa-unique.com", "source": "exa"},
    ]

    with patch.object(agent, "_search_brave", return_value=brave_results), \
         patch.object(agent, "_search_tavily", return_value=tavily_results), \
         patch.object(agent, "_search_exa", return_value=exa_results):
        result = agent._web_search("SSRF labs")

    assert result["result_count"] == 4  # 5 total - 1 duplicate URL
    urls = [r["url"] for r in result["results"]]
    assert len(set(urls)) == 4
    assert "https://portswigger.net/ssrf" in urls
    assert "https://github.com/pi-ctf" in urls
    assert "https://tavily-unique.com" in urls
    assert "https://exa-unique.com" in urls
    assert len(result["sources"]) == 3


def test_partial_provider_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    agent = _make_agent(tmp_path, monkeypatch)

    with patch.object(agent, "_search_brave", return_value=[
        {"title": "Brave Result", "url": "https://brave.example.com", "source": "brave"},
    ]), patch.object(agent, "_search_tavily", side_effect=Exception("Tavily timeout")):
        result = agent._web_search("test")

    assert result["result_count"] == 1
    assert "brave" in result["sources"]
    assert "tavily" not in result["sources"]
    assert result["errors"]["tavily"] == "Tavily timeout"


@patch("httpx.get")
def test_search_brave_returns_formatted_results(mock_get, tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave")
    agent = _make_agent(tmp_path, monkeypatch)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {
                    "title": "PortSwigger SSRF",
                    "url": "https://portswigger.net/ssrf",
                    "description": "SSRF labs",
                },
            ]
        }
    }
    mock_get.return_value = mock_response

    results = agent._search_brave("SSRF", 5)

    assert len(results) == 1
    assert results[0]["title"] == "PortSwigger SSRF"
    assert results[0]["source"] == "brave"
    mock_get.assert_called_once()
    assert mock_get.call_args[1]["params"]["count"] == 5


@patch("httpx.post")
def test_search_tavily_returns_formatted_results(mock_post, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    agent = _make_agent(tmp_path, monkeypatch)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Tavily SSRF",
                "url": "https://tavily.example.com",
                "content": "Deep analysis of SSRF vulnerabilities",
                "score": 0.95,
            },
        ]
    }
    mock_post.return_value = mock_response

    results = agent._search_tavily("SSRF", 5)

    assert len(results) == 1
    assert results[0]["title"] == "Tavily SSRF"
    assert results[0]["source"] == "tavily"
    assert results[0]["score"] == 0.95
    assert "Deep analysis" in results[0]["description"]

    call_json = mock_post.call_args[1]["json"]
    assert call_json["search_depth"] == "advanced"
    assert call_json["max_results"] == 5


@patch("httpx.post")
def test_search_exa_returns_formatted_results(mock_post, tmp_path, monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa")
    agent = _make_agent(tmp_path, monkeypatch)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Exa Paper",
                "url": "https://arxiv.org/abs/1234",
                "text": "Neural search result about prompt injection",
                "publishedDate": "2025-11-15",
            },
        ]
    }
    mock_post.return_value = mock_response

    results = agent._search_exa("prompt injection", 5)

    assert len(results) == 1
    assert results[0]["title"] == "Exa Paper"
    assert results[0]["source"] == "exa"
    assert results[0]["published_date"] == "2025-11-15"
    assert "Neural search" in results[0]["description"]

    call_json = mock_post.call_args[1]["json"]
    assert call_json["numResults"] == 5


def test_disabled_provider_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    agent = _make_agent(
        tmp_path, monkeypatch,
        search_overrides={"tavily": {"enabled": False}},
    )

    with patch.object(agent, "_search_brave", return_value=[
        {"title": "Brave", "url": "https://brave.com", "source": "brave"},
    ]) as mock_brave:
        result = agent._web_search("test")
        mock_brave.assert_called_once()

    assert result["sources"] == ["brave"]


@patch("planner_agent.agent.base.anthropic.Anthropic")
def test_agent_loop_dispatches_web_search(mock_anthropic_cls, tmp_path, monkeypatch):
    """Verify the agent loop dispatches web_search tool calls correctly."""
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    config = AppConfig(llm={"model": "claude-sonnet-4-20250514"})

    from planner_agent.state.store import StateStore

    store = StateStore(str(tmp_path / "data"))

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    agent = PlannerAgent(config, store)

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "web_search"
    tool_use_block.input = {"query": "SSRF labs"}
    tool_use_block.id = "tool_123"

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_use_block]
    tool_response.usage.input_tokens = 500
    tool_response.usage.output_tokens = 100

    final_text = MagicMock()
    final_text.type = "text"
    final_text.text = json.dumps({"tasks": [], "focus_track": "ai_security"})

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [final_text]
    final_response.usage.input_tokens = 500
    final_response.usage.output_tokens = 200

    mock_client.messages.create.side_effect = [tool_response, final_response]

    with patch.object(agent, "_web_search", return_value={"results": []}) as mock_ws:
        result = agent._run_agent_loop("test context")
        mock_ws.assert_called_once_with(query="SSRF labs")

    parsed = json.loads(result)
    assert parsed["focus_track"] == "ai_security"
