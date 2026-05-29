"""Core data models for the Planner Agent."""

from __future__ import annotations

import contextlib
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

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


class CompetenceLevel(StrEnum):
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    COMPETENT = "competent"
    PROFICIENT = "proficient"
    EXPERT = "expert"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"
    PAUSED = "paused"


class MilestoneStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"


class DirectiveStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"


class OpportunityType(StrEnum):
    CTF = "ctf"
    CONFERENCE_CFP = "conference_cfp"
    BOUNTY_PROGRAM = "bounty_program"
    JOB_POSTING = "job_posting"
    CERTIFICATION = "certification"
    TRAINING = "training"
    OTHER = "other"


class OpportunityStatus(StrEnum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class Trajectory(StrEnum):
    ACCELERATING = "accelerating"
    ON_TRACK = "on_track"
    SLOWING = "slowing"
    STALLED = "stalled"
    REGRESSING = "regressing"


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
    milestone_id: int | None = None
    directive_id: int | None = None


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


# ---------------------------------------------------------------------------
# v3 Multi-Brain Models
# ---------------------------------------------------------------------------

class Goal(BaseModel):
    """A top-level strategic objective with a deadline."""

    id: int | None = None
    title: str
    description: str = ""
    deadline: str | None = None
    success_criteria: list[str] = Field(default_factory=list)
    status: GoalStatus = GoalStatus.ACTIVE
    priority: Priority = Priority.HIGH
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Milestone(BaseModel):
    """An intermediate target linked to a goal."""

    id: int | None = None
    goal_id: int
    title: str
    description: str = ""
    target_date: str
    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    completion_date: str | None = None
    depends_on: list[int] = Field(default_factory=list)
    tracks: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Opportunity(BaseModel):
    """A time-sensitive external opportunity."""

    id: int | None = None
    title: str
    description: str = ""
    opportunity_type: OpportunityType
    url: str = ""
    deadline: str | None = None
    event_start: str | None = None
    event_end: str | None = None
    tracks: list[str] = Field(default_factory=list)
    status: OpportunityStatus = OpportunityStatus.DISCOVERED
    priority: Priority = Priority.MEDIUM
    notes: str = ""
    location: str = ""
    source: str = ""
    discovered_at: datetime | None = None
    updated_at: datetime | None = None


# --- Strategic Directive (Strategist output) ---

class PhaseTransition(BaseModel):
    """An explicit phase change decision from the Strategist."""

    track_id: str = ""
    from_phase: Phase = Field(alias=None)
    to_phase: Phase = Field(alias=None)
    rationale: str
    conditions: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_field_names(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if "from" in data and "from_phase" not in data:
                data["from_phase"] = data.pop("from")
            if "to" in data and "to_phase" not in data:
                data["to_phase"] = data.pop("to")
        return data


class StrategicAlert(BaseModel):
    """An urgent item the Strategist wants surfaced."""

    severity: str = "info"
    message: str = ""
    action_required: str = ""
    action: str = ""
    deadline: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_action_field(cls, data: dict) -> dict:
        if isinstance(data, dict) and "action" in data and "action_required" not in data:
            data["action_required"] = data.pop("action")
        return data


class WeeklyTarget(BaseModel):
    """Per-track weekly target within a strategic directive."""

    track_id: str
    phase: Phase
    hours_allocated: float
    priority_rank: int = 1
    objectives: list[str] = Field(default_factory=list)
    task_types_allowed: list[TaskType] = Field(default_factory=list)
    milestone_ids: list[int] = Field(default_factory=list)
    phase_transition: PhaseTransition | None = None

    @field_validator("task_types_allowed", mode="before")
    @classmethod
    def filter_invalid_task_types(cls, v: list) -> list:
        valid = {t.value for t in TaskType}
        return [x for x in v if x in valid]

    @field_validator("milestone_ids", mode="before")
    @classmethod
    def coerce_milestone_ids(cls, v: list) -> list[int]:
        result = []
        for item in v:
            with contextlib.suppress(ValueError, TypeError):
                result.append(int(item))
        return result

    @field_validator("priority_rank", mode="before")
    @classmethod
    def coerce_priority_rank(cls, v: int | str) -> int:
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1

    @model_validator(mode="after")
    def fill_phase_transition_track_id(self) -> WeeklyTarget:
        if self.phase_transition and not self.phase_transition.track_id:
            self.phase_transition.track_id = self.track_id
        return self


class MilestoneTarget(BaseModel):
    """Expected milestone progress for the week."""

    milestone_id: int = 0
    expected_progress: str = ""
    notes: str = ""

    @field_validator("milestone_id", mode="before")
    @classmethod
    def coerce_milestone_id(cls, v: int | str) -> int:
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0


class OpportunityAction(BaseModel):
    """Action to take on an opportunity this week."""

    opportunity_id: int = 0
    opportunity: str = ""
    action: str = ""
    notes: str = ""
    priority: str = ""


class StrategicDirective(BaseModel):
    """The Strategist's weekly plan — binding orders for the Tactician."""

    week_start: str
    week_end: str
    strategic_focus: str
    weekly_theme: str
    targets: list[WeeklyTarget]
    total_hours_available: float
    hours_by_track: dict[str, float] = Field(default_factory=dict)
    phase_transitions: list[PhaseTransition] = Field(default_factory=list)
    milestone_targets: list[MilestoneTarget] = Field(default_factory=list)

    @field_validator("phase_transitions", mode="before")
    @classmethod
    def coerce_phase_transitions(cls, v: list) -> list:
        return [item for item in v if isinstance(item, dict)]
    alerts: list[StrategicAlert] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    opportunity_actions: list[OpportunityAction] = Field(default_factory=list)

    @field_validator("alerts", mode="before")
    @classmethod
    def coerce_alerts(cls, v: list) -> list:
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"message": item})
            else:
                result.append(item)
        return result

    @field_validator("milestone_targets", mode="before")
    @classmethod
    def coerce_milestone_targets(cls, v: list) -> list:
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"expected_progress": item})
            else:
                result.append(item)
        return result

    @field_validator("opportunity_actions", mode="before")
    @classmethod
    def coerce_opportunity_actions(cls, v: list) -> list:
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"action": item})
            else:
                result.append(item)
        return result


# --- Weekly Review (Critic output) ---

class TrackAssessment(BaseModel):
    """Critic's assessment of one track's weekly performance."""

    track_id: str
    planned_hours: float
    actual_hours: float
    planned_tasks: int
    completed_tasks: int
    skipped_tasks: int
    quality_assessment: str
    trajectory: Trajectory
    concerns: list[str] = Field(default_factory=list)


class MilestoneProgress(BaseModel):
    """Critic's assessment of milestone trajectory."""

    milestone_id: int
    title: str
    target_date: str
    status: str
    progress_notes: str
    weeks_remaining: int
    confidence: float


class WeeklyReview(BaseModel):
    """The Critic's honest assessment of the previous week."""

    week_start: str
    week_end: str
    overall_grade: str  # A/B/C/D/F
    overall_narrative: str
    track_assessments: list[TrackAssessment] = Field(default_factory=list)
    milestone_progress: list[MilestoneProgress] = Field(default_factory=list)
    planned_total_hours: float
    actual_total_hours: float
    adherence_score: float
    positive_patterns: list[str] = Field(default_factory=list)
    negative_patterns: list[str] = Field(default_factory=list)
    strategic_recommendations: list[str] = Field(default_factory=list)
    risks: list[dict] = Field(default_factory=list)


# --- User Intelligence Profile (Analyst output) ---

class SubSkillAssessment(BaseModel):
    """Assessment of a specific sub-skill within a track."""

    name: str
    level: CompetenceLevel
    evidence: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    last_assessed: str | None = None


class TrackIntelligence(BaseModel):
    """Everything the Analyst knows about the user's competence in one track."""

    track_id: str
    overall_level: CompetenceLevel
    sub_skills: list[SubSkillAssessment] = Field(default_factory=list)
    learning_velocity: float = 0.0
    preferred_resource_types: list[str] = Field(default_factory=list)
    difficulty_calibration: str = ""
    phase_readiness: str = ""
    skip_patterns: list[str] = Field(default_factory=list)
    key_learnings: list[str] = Field(default_factory=list)
    resource_quality_notes: list[str] = Field(default_factory=list)


class UserIntelligenceProfile(BaseModel):
    """The Analyst's structured understanding of the user."""

    last_updated: str
    tracks: list[TrackIntelligence] = Field(default_factory=list)
    general_preferences: dict = Field(default_factory=dict)
    engagement_patterns: dict = Field(default_factory=dict)
    confidence_indicators: list[str] = Field(default_factory=list)
    concern_indicators: list[str] = Field(default_factory=list)
    narrative_summary: str = ""
