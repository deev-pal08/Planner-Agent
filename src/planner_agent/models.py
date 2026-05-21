"""Core data models for the Planner Agent."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Phase(StrEnum):
    LEARN = "learn"
    PRACTICE = "practice"
    PRODUCE = "produce"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"
    DEFERRED = "deferred"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(StrEnum):
    READ = "read"
    LAB = "lab"
    CTF = "ctf"
    CODE_REVIEW = "code_review"
    BUG_BOUNTY = "bug_bounty"
    WRITE = "write"
    BUILD = "build"
    RESEARCH = "research"
    COURSE = "course"
    OTHER = "other"


class AchievementType(StrEnum):
    CVE = "cve"
    HALL_OF_FAME = "hall_of_fame"
    RESEARCH_PAPER = "research_paper"
    PATENT = "patent"
    BLOG_POST = "blog_post"
    CONFERENCE_TALK = "conference_talk"
    OPEN_SOURCE = "open_source"
    CTF_PLACEMENT = "ctf_placement"
    CERTIFICATION = "certification"
    HACKATHON = "hackathon"
    OTHER = "other"


class Task(BaseModel):
    """A single actionable task assigned by the planner."""

    id: int | None = None
    title: str
    description: str
    task_type: TaskType
    track: str
    phase: Phase
    priority: Priority = Priority.MEDIUM
    estimated_hours: float
    actual_hours: float | None = None
    status: TaskStatus = TaskStatus.PENDING
    resource_url: str = ""
    resource_name: str = ""
    why: str = ""
    learnings: str = ""
    assigned_date: datetime | None = None
    completed_date: datetime | None = None


class Skill(BaseModel):
    """A skill track with current assessment."""

    track_id: str
    name: str
    current_phase: Phase
    priority: Priority
    hours_invested: float = 0.0
    items_completed: int = 0
    confidence_note: str = ""
    last_assessed: datetime | None = None


class Achievement(BaseModel):
    """A portfolio item — something publicly visible."""

    id: int | None = None
    achievement_type: AchievementType
    title: str
    url: str = ""
    description: str = ""
    track: str = ""
    date_achieved: datetime | None = None


class FeedbackEntry(BaseModel):
    """Parsed feedback from an email reply."""

    task_id: int
    status: TaskStatus
    actual_hours: float | None = None
    notes: str = ""
    learnings: str = ""


class NewsletterArticle(BaseModel):
    """A single newsletter article for the reading block."""

    title: str
    url: str
    priority: str
    why: str = ""


class NewsletterReading(BaseModel):
    """The newsletter reading block — one combined task."""

    title: str
    description: str
    estimated_hours: float
    articles: list[NewsletterArticle] = Field(default_factory=list)


class DailyBriefing(BaseModel):
    """Structured output from the Claude agent — the daily plan."""

    date: str
    focus_track: str
    focus_phase: Phase
    focus_rationale: str
    tasks: list[Task]
    total_estimated_hours: float
    portfolio_gaps: list[str] = Field(default_factory=list)
    skill_observations: list[str] = Field(default_factory=list)
    newsletter_topics: list[str] = Field(default_factory=list)
    newsletter_reading: NewsletterReading | None = None


class EmailFeedback(BaseModel):
    """Structured output from Claude parsing an email reply."""

    task_updates: list[FeedbackEntry]
    general_notes: str = ""
    total_hours_reported: float | None = None
