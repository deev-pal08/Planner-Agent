"""Scout brain — discovers time-sensitive opportunities via web search."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime

import httpx

from planner_agent.agent.base import BaseBrain
from planner_agent.agent.prompts.scout import (
    SCOUT_SYSTEM_PROMPT,
    build_scout_context,
)
from planner_agent.config import AppConfig
from planner_agent.models import Opportunity, OpportunityType, Priority
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)

SCOUT_TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for real, upcoming security events, CTFs, "
            "conference CFPs, bug bounty programs, and training opportunities. "
            "Batch multiple queries in a single turn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'security CTF 2026 upcoming registration'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_url",
        "description": (
            "Check if a URL is live and retrieve the page title. "
            "Verify every opportunity URL before including it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to verify",
                },
            },
            "required": ["url"],
        },
    },
]


class ScoutBrain(BaseBrain):
    brain_name = "scout"

    def __init__(self, config: AppConfig, state: StateStore):
        super().__init__(config, state)

    def _get_model(self) -> str:
        override = self.config.brains.scout.model_override
        return override or self.config.llm.model

    def needs_run(self, interval_days: int = 3) -> bool:
        last_run = self.state.get_meta("scout_last_run")
        if not last_run:
            return True
        try:
            last_dt = datetime.fromisoformat(last_run)
            now = datetime.now(UTC)
            return (now - last_dt).days >= interval_days
        except ValueError:
            return True

    def _web_search(self, query: str) -> dict:
        if not self.config.search.enabled:
            return {"error": "Web search is disabled"}

        from concurrent.futures import ThreadPoolExecutor, as_completed

        max_results = self.config.search.max_results
        providers: dict[str, callable] = {}

        if self.config.search.brave.enabled and self.config.search.brave.api_key:
            providers["brave"] = lambda q=query: self._search_brave(q, max_results)
        if self.config.search.tavily.enabled and self.config.search.tavily.api_key:
            providers["tavily"] = lambda q=query: self._search_tavily(q, max_results)
        if self.config.search.exa.enabled and self.config.search.exa.api_key:
            providers["exa"] = lambda q=query: self._search_exa(q, max_results)

        if not providers:
            return {"error": "No search providers configured"}

        all_results: list[dict] = []
        seen_urls: set[str] = set()
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(fn): name for name, fn in providers.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results = future.result()
                    for r in results:
                        url = r.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(r)
                except Exception as e:
                    errors.append(f"{name}: {e}")

        output: dict = {"query": query, "results": all_results[:max_results * 2]}
        if errors:
            output["provider_errors"] = errors
        return output

    def _search_brave(self, query: str, max_results: int) -> list[dict]:
        api_key = self.config.search.brave.api_key
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": (r.get("description", "") or "")[:120],
                "source": "brave",
            }
            for r in data.get("web", {}).get("results", [])[:max_results]
        ]

    def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        api_key = self.config.search.tavily.api_key
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "api_key": api_key,
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": (r.get("content", "") or "")[:120],
                "source": "tavily",
            }
            for r in data.get("results", [])[:max_results]
        ]

    def _search_exa(self, query: str, max_results: int) -> list[dict]:
        api_key = self.config.search.exa.api_key
        resp = httpx.post(
            "https://api.exa.ai/search",
            json={
                "query": query,
                "numResults": max_results,
                "type": "neural",
                "useAutoprompt": True,
            },
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": "",
                "source": "exa",
            }
            for r in data.get("results", [])[:max_results]
        ]

    def _verify_url(self, url: str) -> dict:
        try:
            with httpx.Client(follow_redirects=True, timeout=10) as client:
                r = client.get(url)
                result: dict = {
                    "url": url,
                    "live": r.status_code < 400,
                    "status_code": r.status_code,
                }
                if r.status_code < 400:
                    match = re.search(
                        r"<title[^>]*>([^<]+)</title>",
                        r.text[:10000],
                        re.IGNORECASE,
                    )
                    if match:
                        result["page_title"] = match.group(1).strip()
                return result
        except Exception as e:
            return {"url": url, "live": False, "error": str(e)}

    def _run_scout_loop(self, context: str) -> str:
        model = self._get_model()
        messages: list[dict] = [{"role": "user", "content": context}]
        max_iterations = 5
        _api_call_interval = 20
        _last_call = 0.0

        for _ in range(max_iterations):
            elapsed = time.monotonic() - _last_call
            if _last_call and elapsed < _api_call_interval:
                wait = _api_call_interval - elapsed
                logger.info("Scout pacing: waiting %.0fs", wait)
                time.sleep(wait)

            _last_call = time.monotonic()
            response = self._call_claude(
                model=model,
                max_tokens=4096,
                system=SCOUT_SYSTEM_PROMPT,
                tools=SCOUT_TOOLS,
                messages=messages,
            )
            self._log_usage(response, model)

            if response.stop_reason == "end_turn":
                return next(b.text for b in response.content if b.type == "text")

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if block.name == "web_search":
                            result = self._web_search(**block.input)
                        elif block.name == "verify_url":
                            result = self._verify_url(**block.input)
                        else:
                            result = {"error": f"Unknown tool: {block.name}"}
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        logger.warning("Scout hit max iterations — extracting partial response")
        if response:
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
        return "{}"

    def run(self, today: str | None = None) -> list[Opportunity]:
        now = datetime.now(UTC)
        today = today or now.strftime("%Y-%m-%d")

        context = build_scout_context(
            skills=self.state.get_all_skills(),
            goals=self.state.get_active_goals(),
            existing_opportunities=self.state.get_all_opportunities(),
            achievements=self.state.get_all_achievements(),
            today=today,
        )

        raw = self._run_scout_loop(context)

        try:
            data = self._parse_json_response(raw)
        except Exception:
            logger.warning("Scout JSON parse failed — retrying extraction")
            msg = f"Extract the JSON from this text:\n\n{raw}"
            response = self._call_claude(
                model=self._get_model(),
                max_tokens=4096,
                system="Output ONLY valid JSON, nothing else.",
                messages=[{"role": "user", "content": msg}],
            )
            self._log_usage(response, self._get_model())
            data = self._parse_json_response(
                response.content[0].text
            )

        opportunities = []

        for o in data.get("opportunities", []):
            try:
                opp_type = OpportunityType(o.get("opportunity_type", "other"))
            except ValueError:
                opp_type = OpportunityType.OTHER

            try:
                priority = Priority(o.get("priority", "medium"))
            except ValueError:
                priority = Priority.MEDIUM

            opp = Opportunity(
                title=o.get("title", ""),
                description=o.get("description", ""),
                opportunity_type=opp_type,
                url=o.get("url", ""),
                deadline=o.get("deadline"),
                event_start=o.get("event_start"),
                event_end=o.get("event_end"),
                tracks=o.get("tracks", []),
                priority=priority,
                notes=o.get("notes", ""),
                location=o.get("location", ""),
                source="scout",
            )

            opp_id = self.state.add_opportunity(opp)
            opp.id = opp_id
            opportunities.append(opp)
            logger.info(
                "Scout discovered: [%s] %s (deadline: %s)",
                opp.opportunity_type, opp.title, opp.deadline,
            )

        self.state.set_meta("scout_last_run", now.isoformat())

        logger.info(
            "Scout complete: %d opportunities discovered",
            len(opportunities),
        )
        return opportunities
