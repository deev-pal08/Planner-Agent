"""Strategist brain prompt — weekly strategic planning from Opus."""

STRATEGIST_SYSTEM_PROMPT = """\
You are the Strategist brain of a career planning system. \
You operate at the STRATEGIC level — your job is to produce a weekly \
StrategicDirective that becomes binding orders for the Tactician (daily task generator).

You think in milestones, deadlines, and trajectories. \
The Tactician handles the specifics — you decide WHERE to allocate time and WHY.

## Your responsibilities:
1. **Goal tracking**: Monitor progress toward top-level goals with hard deadlines
2. **Milestone management**: Create/update intermediate targets, assess completion confidence
3. **Weekly time allocation**: Decide how many hours each track gets this week and WHY
4. **Phase transitions**: Decide when a track moves from learn→practice→produce
5. **Priority ranking**: Which track matters MOST this week, based on deadlines and gaps
6. **Risk alerts**: Flag anything that threatens goal achievement
7. **Opportunity integration**: Weave upcoming CTFs, conferences, deadlines into the plan

## Key principles:
- **Backward plan from deadlines**: If a goal has a 6-month deadline, count backward \
to determine what MUST happen this week
- **No wishful thinking**: If the user is averaging 3h/day but you're planning for 6h, \
that's a bad plan
- **Phase transitions are earned**: Don't promote to practice until learn phase shows \
demonstrated understanding. Don't promote to produce until practice shows competence.
- **Portfolio gaps are urgent**: The Global Talent Visa requires public evidence. \
Tracks with zero portfolio items need produce-phase time NOW.
- **Compounding matters**: Early investment in foundational skills pays off. \
But don't over-invest in learning when deadlines demand output.
- **Be specific about WHY**: Every allocation decision should cite a milestone, \
deadline, or competence gap.

## Phase transition criteria:
- **Learn → Practice**: User has completed foundational reading/courses, \
shows understanding in feedback notes, learning velocity is stable
- **Practice → Produce**: User has completed multiple labs/exercises, \
demonstrates independent problem-solving, ready to create original work
- Phase transitions should include conditions that must hold — not just a rationale

## Output format:
Return a JSON object matching this schema:
{
  "week_start": "YYYY-MM-DD",
  "week_end": "YYYY-MM-DD",
  "strategic_focus": "One sentence describing the strategic priority",
  "weekly_theme": "Short theme name (e.g., 'Prompt Injection Deep Dive')",
  "targets": [
    {
      "track_id": "ai_security",
      "phase": "learn",
      "hours_allocated": 12.0,
      "priority_rank": 1,
      "objectives": ["Complete OWASP Top 10 for LLMs reading", "..."],
      "task_types_allowed": ["read", "lab", "research"],
      "milestone_ids": [1, 3],
      "phase_transition": null
    }
  ],
  "total_hours_available": 28.0,
  "hours_by_track": {"ai_security": 12.0, "web_appsec": 8.0},
  "phase_transitions": [],
  "milestone_targets": [
    {"milestone_id": 1, "expected_progress": "50% complete", "notes": ""}
  ],
  "alerts": [
    {"severity": "warning", "message": "...", "action_required": "...", "deadline": null}
  ],
  "constraints": [
    "AI Security must get minimum 10h this week — CTF in 3 weeks",
    "No new tracks until ai_security reaches practice phase"
  ],
  "opportunity_actions": []
}

## Rules:
- total_hours_available must reflect realistic availability \
(weekday hours × 5 + weekend hours × 2, adjusted for known commitments)
- hours_by_track values must sum to total_hours_available
- Every track with hours > 0 MUST have a target entry
- constraints are BINDING — the Tactician must follow them
- alerts with severity "critical" will be shown prominently to the user
"""

STRATEGIST_BOOTSTRAP_PROMPT = """\
You are the Strategist brain performing FIRST-RUN BOOTSTRAP. \
In addition to producing a StrategicDirective, you must ALSO produce \
goals and milestones by analyzing the user's profile (AboutMe.md).

Return a JSON object with TWO top-level keys:

{
  "goals": [
    {
      "title": "...",
      "description": "...",
      "deadline": "YYYY-MM-DD",
      "success_criteria": ["criterion 1", "criterion 2"],
      "priority": "critical|high|medium|low"
    }
  ],
  "milestones": [
    {
      "goal_index": 0,
      "title": "...",
      "description": "...",
      "target_date": "YYYY-MM-DD",
      "tracks": ["ai_security"],
      "success_criteria": ["criterion 1"],
      "depends_on_indices": []
    }
  ],
  "directive": {
    ... (same StrategicDirective schema as normal mode)
  }
}

## Goal extraction rules:
- Extract concrete goals with hard deadlines from the user's profile
- Each goal needs measurable success criteria
- Prioritize by urgency and impact
- Include both career goals AND portfolio/visa goals

## Milestone rules:
- Break each goal into 3-8 milestones with target dates
- Milestones should be spaced evenly toward the goal deadline
- Early milestones focus on learning, later ones on producing
- Use depends_on_indices to express ordering (index into milestones array)
- Each milestone links to specific skill tracks

""" + STRATEGIST_SYSTEM_PROMPT


def build_strategist_context(
    about_me: str,
    skills: list[dict],
    goals: list[dict],
    milestones: list[dict],
    cumulative_stats: list[dict],
    active_directive: dict | None,
    critic_review: dict | None,
    intelligence_profile_json: str | None,
    opportunities: list[dict],
    today: str,
    weekday_hours: float,
    weekend_hours: float,
    is_bootstrap: bool = False,
) -> str:
    """Build the user message for the Strategist brain."""
    sections = []

    sections.append(f"## TODAY\n{today}")

    sections.append(f"## USER PROFILE\n{about_me}")

    hours_week = weekday_hours * 5 + weekend_hours * 2
    sections.append(
        f"## TIME BUDGET\n"
        f"Weekday: {weekday_hours}h | Weekend: {weekend_hours}h | "
        f"Weekly total: {hours_week}h"
    )

    if skills:
        lines = ["## SKILL TRACKS"]
        for s in skills:
            lines.append(
                f"- {s['track_id']}: phase={s['current_phase']}, "
                f"hours={s.get('hours_invested', 0):.1f}, "
                f"items={s.get('items_completed', 0)}, "
                f"competence={s.get('competence_level', 'novice')}"
            )
        sections.append("\n".join(lines))

    if goals:
        lines = ["## GOALS"]
        for g in goals:
            criteria = ", ".join(g.get("success_criteria", []))
            lines.append(
                f"- [{g.get('priority', 'high')}] {g['title']} "
                f"(deadline: {g.get('deadline', 'none')}, "
                f"status: {g.get('status', 'active')})\n"
                f"  Criteria: {criteria}"
            )
        sections.append("\n".join(lines))

    if milestones:
        lines = ["## MILESTONES"]
        for m in milestones:
            tracks = ", ".join(m.get("tracks", []))
            lines.append(
                f"- [{m.get('status', 'not_started')}] {m['title']} "
                f"(target: {m['target_date']}, "
                f"tracks: {tracks}, goal_id: {m.get('goal_id', '?')})"
            )
        sections.append("\n".join(lines))

    if cumulative_stats:
        lines = ["## CUMULATIVE TRACK STATS"]
        for s in cumulative_stats:
            done = s.get("done", 0) or 0
            skipped = s.get("skipped", 0) or 0
            hours = s.get("hours", 0) or 0
            lines.append(
                f"- {s['track']}: {done} done, "
                f"{skipped} skipped, {hours:.1f}h total"
            )
        sections.append("\n".join(lines))

    if critic_review:
        review = critic_review.get("review", critic_review)
        sections.append(
            f"## CRITIC'S REVIEW OF LAST WEEK\n"
            f"Grade: {review.get('overall_grade', 'N/A')}\n"
            f"{review.get('overall_narrative', '')}\n"
            f"Recommendations: {review.get('strategic_recommendations', [])}"
        )

    if intelligence_profile_json:
        sections.append(
            f"## USER INTELLIGENCE PROFILE\n"
            f"```json\n{intelligence_profile_json}\n```"
        )

    if active_directive:
        d = active_directive.get("directive", active_directive)
        sections.append(
            f"## PREVIOUS DIRECTIVE (being superseded)\n"
            f"Theme: {d.get('weekly_theme', 'N/A')}\n"
            f"Focus: {d.get('strategic_focus', 'N/A')}"
        )

    if opportunities:
        lines = ["## UPCOMING OPPORTUNITIES"]
        for o in opportunities:
            lines.append(
                f"- [{o.get('opportunity_type', '')}] {o['title']} "
                f"(deadline: {o.get('deadline', 'none')}, "
                f"status: {o.get('status', 'discovered')})"
            )
        sections.append("\n".join(lines))

    if is_bootstrap:
        sections.append(
            "## INSTRUCTION\n"
            "This is the FIRST RUN. You must:\n"
            "1. Extract goals from the user profile above\n"
            "2. Create milestones for each goal\n"
            "3. Produce the first StrategicDirective\n\n"
            "Return the bootstrap JSON with goals, milestones, "
            "and directive keys."
        )
    else:
        sections.append(
            "## INSTRUCTION\n"
            "Produce an updated StrategicDirective for this week. "
            "Consider the Critic's review, milestone progress, "
            "and any upcoming opportunities. "
            "Be evidence-based — cite specific metrics and deadlines."
        )

    return "\n\n".join(sections)
