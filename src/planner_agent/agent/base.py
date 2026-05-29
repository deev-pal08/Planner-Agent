"""Base brain class with shared API call logic for all brains."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from planner_agent.config import AppConfig
from planner_agent.state.store import StateStore

logger = logging.getLogger(__name__)


class BriefingParseError(Exception):
    """Raised when a brain's response cannot be parsed as valid JSON."""


class BaseBrain:
    """Shared API call infrastructure for all brains."""

    brain_name: str = "base"

    def __init__(self, config: AppConfig, state: StateStore):
        self.config = config
        self.state = state
        self._client = anthropic.Anthropic(
            api_key=config.llm.api_key,
            base_url="https://api.anthropic.com",
        )

    @retry(
        retry=retry_if_exception_type(anthropic.APIStatusError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_claude(self, **kwargs: Any) -> Any:
        return self._client.messages.create(**kwargs)

    def _log_usage(self, response: Any, model_name: str) -> None:
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        logger.info(
            "API usage [%s/%s] — input: %d tokens, output: %d tokens",
            self.brain_name, model_name, input_tokens, output_tokens,
        )
        self._track_cost(input_tokens, output_tokens)

    def _track_cost(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token usage per brain in the meta table."""
        if not hasattr(self, "state") or self.state is None:
            return
        key = f"tokens_{self.brain_name}"
        raw = self.state.get_meta(key)
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"input": 0, "output": 0, "calls": 0}
        else:
            data = {"input": 0, "output": 0, "calls": 0}
        data["input"] += input_tokens
        data["output"] += output_tokens
        data["calls"] += 1
        self.state.set_meta(key, json.dumps(data))

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from Claude's response, handling markdown code fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines)
            for i in range(1, len(lines)):
                if lines[i].strip() == "```":
                    end = i
                    break
            text = "\n".join(lines[start:end])

        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            start_idx = text.find("{")
            end_idx = text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    return json.loads(text[start_idx:end_idx], strict=False)
                except json.JSONDecodeError:
                    pass
            logger.error("Failed to parse JSON from response: %s", text[:500])
            raise BriefingParseError(
                f"[{self.brain_name}] Failed to parse JSON. "
                f"Raw text (first 500 chars): {text[:500]}"
            ) from None

    def _single_turn(
        self,
        model: str,
        system: str,
        user_message: str,
        max_tokens: int = 2048,
    ) -> str:
        """Single-turn Claude call (no tools). Returns the text response."""
        response = self._call_claude(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        self._log_usage(response, model)
        return response.content[0].text.strip()
