"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class LLMConfig(BaseModel):
    model: str = "claude-haiku-4-5"
    research_model: str = "claude-sonnet-4-6"
    max_tokens: int = 16384
    api_key_env: str = "ANTHROPIC_API_KEY"

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise ValueError(f"Environment variable {self.api_key_env} is not set")
        return key


class EmailConfig(BaseModel):
    enabled: bool = True
    from_address: str = "planner@yourdomain.com"
    to_addresses: list[str] = Field(default_factory=list)
    api_key_env: str = "RESEND_API_KEY"

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise ValueError(f"Environment variable {self.api_key_env} is not set")
        return key


class IMAPConfig(BaseModel):
    enabled: bool = True
    server: str = "imap.gmail.com"
    port: int = 993
    mailbox: str = "INBOX"
    email_env: str = "IMAP_EMAIL"
    password_env: str = "IMAP_PASSWORD"

    @property
    def email(self) -> str:
        return os.environ.get(self.email_env, "")

    @property
    def password(self) -> str:
        return os.environ.get(self.password_env, "")


class ScheduleConfig(BaseModel):
    briefing_time: str = "07:00"
    timezone: str = "Europe/London"

    @field_validator("briefing_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        from datetime import datetime as _dt

        try:
            _dt.strptime(v, "%H:%M")
        except ValueError as e:
            raise ValueError(
                f"briefing_time must be HH:MM format (e.g. '07:00'), got: '{v}'"
            ) from e
        return v


class TimeBudgetConfig(BaseModel):
    weekday: float = 4.0
    weekend_day: float = 6.0
    max_weekly: float = 25.0


class TrackConfig(BaseModel):
    name: str
    current_phase: str = "learn"
    priority: str = "medium"


class NewsletterConfig(BaseModel):
    project_dir: str = ""
    enabled: bool = False
    stale_threshold_days: int = 7


class AppConfig(BaseModel):
    about_me: str = "AboutMe.md"
    llm: LLMConfig = LLMConfig()
    email: EmailConfig = EmailConfig()
    imap: IMAPConfig = IMAPConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    time_budget: TimeBudgetConfig = TimeBudgetConfig()
    newsletter: NewsletterConfig = NewsletterConfig()
    tracks: dict[str, TrackConfig] = Field(default_factory=lambda: {
        "web_appsec": TrackConfig(
            name="Web Application Security",
            current_phase="learn",
            priority="high",
        ),
        "ai_security": TrackConfig(
            name="AI/ML Security",
            current_phase="learn",
            priority="critical",
        ),
        "agent_engineering": TrackConfig(
            name="AI Agent Engineering",
            current_phase="learn",
            priority="high",
        ),
        "bug_bounty": TrackConfig(
            name="Bug Bounty Hunting",
            current_phase="learn",
            priority="high",
        ),
        "content_creation": TrackConfig(
            name="Content & Research Publishing",
            current_phase="learn",
            priority="medium",
        ),
        "code_review": TrackConfig(
            name="Advanced Code Review",
            current_phase="learn",
            priority="medium",
        ),
    })
    state_dir: str = "data"


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        return AppConfig()
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig.model_validate(raw)


def load_about_me(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text().strip()
