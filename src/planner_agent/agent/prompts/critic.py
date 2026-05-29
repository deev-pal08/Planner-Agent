"""Critic brain prompt — honest weekly review of planned vs actual."""

CRITIC_SYSTEM_PROMPT = """\
You are the Critic brain of a career planning system. \
Your job is HONEST ASSESSMENT — you review the previous week's performance \
and produce a WeeklyReview that feeds into the Strategist's next planning cycle.

You are the user's accountability partner. Be direct, specific, and evidence-based. \
Praise real progress. Flag real problems. Never sugarcoat.

## Your responsibilities:
1. **Planned vs Actual**: Compare what the directive allocated vs what was completed
2. **Per-track assessment**: Grade each track's progress, identify trajectory
3. **Milestone tracking**: Assess whether milestones are on track given deadlines
4. **Pattern recognition**: Identify positive patterns to reinforce and negative ones to correct
5. **Strategic recommendations**: Concrete suggestions for the Strategist's next directive
6. **Risk identification**: Flag anything that threatens goal achievement

## Grading criteria:
- **A**: Exceeded plan — completed more than allocated, high quality
- **B**: Met plan — completed what was planned, solid execution
- **C**: Partially met — completed 50-80% of plan, some gaps
- **D**: Underperformed — completed < 50% of plan, significant gaps
- **F**: Failed — minimal completion, no meaningful progress

## Trajectory assessment:
- **accelerating**: Completion rate and hours are increasing week-over-week
- **on_track**: Steady pace, meeting or near expectations
- **slowing**: Declining completion rate or hours vs previous weeks
- **stalled**: Near-zero progress for this track
- **regressing**: Going backward (e.g., skipping previously mastered material)

## Output format:
Return a JSON object:
{
  "overall_grade": "B",
  "overall_narrative": "Solid week on AI security fundamentals, but web appsec fell behind...",
  "track_assessments": [
    {
      "track_id": "ai_security",
      "planned_hours": 16.0,
      "actual_hours": 14.5,
      "planned_tasks": 5,
      "completed_tasks": 4,
      "skipped_tasks": 1,
      "quality_assessment": "Strong engagement with OWASP materials...",
      "trajectory": "on_track",
      "concerns": []
    }
  ],
  "milestone_progress": [
    {
      "milestone_id": 1,
      "title": "Complete AI Security fundamentals",
      "target_date": "2026-07-15",
      "status": "in_progress",
      "progress_notes": "40% through foundational reading...",
      "weeks_remaining": 7,
      "confidence": 0.75
    }
  ],
  "planned_total_hours": 28.0,
  "actual_total_hours": 22.5,
  "adherence_score": 0.80,
  "positive_patterns": ["Consistent daily study sessions", "Good URL verification habits"],
  "negative_patterns": ["Skipping labs when tired", "Avoiding content creation"],
  "strategic_recommendations": [
    "Reduce web_appsec allocation — user consistently under-delivers here",
    "Add 1 execute-phase task per week to build portfolio"
  ],
  "risks": [
    {
      "severity": "warning",
      "description": "No portfolio items produced in 3 weeks",
      "mitigation": "Force one blog post or writeup this week"
    }
  ]
}

## Rules:
- adherence_score = actual_total_hours / planned_total_hours (capped at 1.0)
- Be specific in quality_assessment — cite specific tasks, not generalities
- strategic_recommendations should be actionable and concrete
- Milestone confidence is 0.0 to 1.0 — estimate likelihood of hitting target_date
- If a track had 0 planned hours, don't include it in track_assessments
"""


def build_critic_context(
    week_start: str,
    week_end: str,
    directive: dict | None,
    tasks: list[dict],
    skills: list[dict],
    goals: list[dict],
    milestones: list[dict],
    cumulative_stats: list[dict],
    feedback_notes: list[dict],
    today: str,
) -> str:
    """Build the user message for the Critic brain."""
    sections = []

    sections.append(f"## REVIEW PERIOD\n{week_start} to {week_end}")
    sections.append(f"## TODAY\n{today}")

    if directive:
        d = directive.get("directive", directive)
        targets_lines = []
        for t in d.get("targets", []):
            targets_lines.append(
                f"  - {t['track_id']}: {t.get('hours_allocated', 0)}h, "
                f"phase={t.get('phase', '?')}, rank={t.get('priority_rank', '?')}"
            )
        sections.append(
            f"## STRATEGIC DIRECTIVE FOR THIS WEEK\n"
            f"Theme: {d.get('weekly_theme', 'N/A')}\n"
            f"Focus: {d.get('strategic_focus', 'N/A')}\n"
            f"Total hours planned: {d.get('total_hours_available', 0)}\n"
            f"Targets:\n" + "\n".join(targets_lines)
        )
        constraints = d.get("constraints", [])
        if constraints:
            sections.append(
                "Constraints:\n" + "\n".join(f"  - {c}" for c in constraints)
            )
    else:
        sections.append(
            "## STRATEGIC DIRECTIVE\nNo directive was active this week "
            "(pre-Strategist era). Assess based on available data."
        )

    if tasks:
        done = [t for t in tasks if t.get("status") == "done"]
        skipped = [t for t in tasks if t.get("status") == "skipped"]
        pending = [t for t in tasks if t.get("status") == "pending"]
        in_progress = [t for t in tasks if t.get("status") == "in_progress"]

        lines = [
            f"## TASKS THIS WEEK ({len(tasks)} total, "
            f"{len(done)} done, {len(skipped)} skipped, "
            f"{len(pending)} pending, {len(in_progress)} in progress)"
        ]
        for t in tasks:
            hours_str = ""
            if t.get("actual_hours"):
                hours_str = f"actual={t['actual_hours']}h"
            elif t.get("estimated_hours"):
                hours_str = f"est={t['estimated_hours']}h"
            learnings = ""
            if t.get("learnings"):
                learnings = f" | Learnings: {t['learnings'][:100]}"
            lines.append(
                f"  - [{t.get('status', '?')}] [{t.get('track', '?')}] "
                f"{t.get('title', '?')} ({hours_str}){learnings}"
            )
        sections.append("\n".join(lines))

        track_hours: dict[str, dict] = {}
        for t in tasks:
            track = t.get("track", "unknown")
            if track not in track_hours:
                track_hours[track] = {
                    "done": 0, "skipped": 0, "pending": 0,
                    "actual_h": 0.0, "estimated_h": 0.0,
                }
            status = t.get("status", "pending")
            track_hours[track][status] = track_hours[track].get(status, 0) + 1
            if status == "done":
                track_hours[track]["actual_h"] += (
                    t.get("actual_hours") or t.get("estimated_hours", 0)
                )
            track_hours[track]["estimated_h"] += t.get("estimated_hours", 0)

        summary_lines = ["## PER-TRACK SUMMARY"]
        for track, data in sorted(track_hours.items()):
            summary_lines.append(
                f"  - {track}: {data['done']} done, "
                f"{data['skipped']} skipped, "
                f"{data['pending']} pending, "
                f"actual_hours={data['actual_h']:.1f}, "
                f"estimated_hours={data['estimated_h']:.1f}"
            )
        sections.append("\n".join(summary_lines))
    else:
        sections.append("## TASKS THIS WEEK\nNo tasks were assigned this week.")

    if skills:
        lines = ["## CURRENT SKILL STATE"]
        for s in skills:
            lines.append(
                f"  - {s['track_id']}: phase={s['current_phase']}, "
                f"hours={s.get('hours_invested', 0):.1f}, "
                f"items={s.get('items_completed', 0)}, "
                f"competence={s.get('competence_level', 'novice')}"
            )
        sections.append("\n".join(lines))

    if goals:
        lines = ["## ACTIVE GOALS"]
        for g in goals:
            lines.append(
                f"  - [{g.get('priority', '?')}] {g['title']} "
                f"(deadline: {g.get('deadline', 'none')})"
            )
        sections.append("\n".join(lines))

    if milestones:
        lines = ["## MILESTONES"]
        for m in milestones:
            tracks = ", ".join(m.get("tracks", []))
            lines.append(
                f"  - [{m.get('status', 'not_started')}] {m['title']} "
                f"(target: {m['target_date']}, tracks: {tracks})"
            )
        sections.append("\n".join(lines))

    if cumulative_stats:
        lines = ["## CUMULATIVE TRACK STATS (all time)"]
        for s in cumulative_stats:
            done = s.get("done", 0) or 0
            skipped = s.get("skipped", 0) or 0
            hours = s.get("hours", 0) or 0
            lines.append(
                f"  - {s['track']}: {done} done, "
                f"{skipped} skipped, {hours:.1f}h total"
            )
        sections.append("\n".join(lines))

    if feedback_notes:
        lines = ["## RECENT FEEDBACK (from user)"]
        for f in feedback_notes[:20]:
            lines.append(
                f"  - [{f.get('track', '?')}] {f.get('title', '?')}: "
                f"{f.get('notes', '')}"
            )
        sections.append("\n".join(lines))

    sections.append(
        "## INSTRUCTION\n"
        "Produce a WeeklyReview JSON for the period above. "
        "Be honest and specific. Compare planned vs actual rigorously. "
        "Your recommendations will directly shape next week's directive."
    )

    return "\n\n".join(sections)
