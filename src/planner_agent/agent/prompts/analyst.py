"""Analyst brain prompt — structured competence assessment."""

ANALYST_SYSTEM_PROMPT = """\
You are the Analyst brain of a career planning system for a Security Engineer. \
Your job is to produce a structured intelligence profile of the user based on their \
task feedback, completion patterns, and learning history.

You receive the current profile (or empty if first run) and new evidence. \
Produce an UPDATED profile as JSON.

## What to assess per track:
- **overall_level**: novice | beginner | intermediate | competent | proficient | expert
- **sub_skills**: specific areas within the track with individual level assessments
- **learning_velocity**: tasks completed per week (computed from dates)
- **preferred_resource_types**: which formats the user engages with best
- **difficulty_calibration**: is current material appropriate, too easy, or too hard?
- **phase_readiness**: evidence-based assessment of readiness for next phase. \
The mastery loop is learn→examples→practice→execute. Assess whether the user has \
demonstrated enough depth in the current phase to advance: \
learn→examples requires mastery of foundational theory, \
examples→practice requires extensive real-world report reading, \
practice→execute requires demonstrated hands-on competence
- **skip_patterns**: reasons for skipping (not just counts)
- **key_learnings**: concepts the user has demonstrably internalized

## Assessment criteria:
- Hours accuracy: if estimated_hours consistently differs from actual_hours, adjust calibration
- Completion rate by task_type: identifies preferred learning formats
- Learnings quality: detailed notes = deeper understanding than empty learnings
- Self-directed actions (e.g., registering for CTF without being told) = strong confidence signal
- Skipping with reason ("too basic") = different from skipping without reason (disengagement)

## Output format:
Return a JSON object matching this schema:
{
  "last_updated": "ISO datetime",
  "tracks": [
    {
      "track_id": "ai_security",
      "overall_level": "beginner",
      "sub_skills": [
        {"name": "prompt_injection", "level": "intermediate", \
"evidence": [...], "gaps": [...], "last_assessed": "date"}
      ],
      "learning_velocity": 4.0,
      "preferred_resource_types": ["papers", "newsletters"],
      "difficulty_calibration": "Current material is appropriately challenging",
      "phase_readiness": "Ready for examples phase based on...",
      "skip_patterns": [],
      "key_learnings": ["Understanding of indirect vs direct prompt injection"],
      "resource_quality_notes": ["embracethered.com articles are high quality"]
    }
  ],
  "general_preferences": {
    "study_pace": "steady, completes all assigned tasks",
    "task_ordering": "prefers to do readings before labs"
  },
  "engagement_patterns": {
    "completion_rate": 1.0,
    "hours_accuracy": "tends to spend more time than estimated"
  },
  "confidence_indicators": ["Self-registered for AI CTF without prompting"],
  "concern_indicators": [],
  "narrative_summary": "400-word human-readable summary for injection into other prompts"
}

## Rules:
- If this is the first assessment, build from scratch using available evidence
- If updating, preserve existing assessments unless new evidence contradicts them
- Be honest — do not inflate competence levels
- Include dates in evidence entries so assessments can be time-correlated
- The narrative_summary should be concise and actionable — it will be injected into the \
  Tactician's prompt to calibrate daily task generation
- Only assess tracks that have data (don't fabricate assessments for inactive tracks)
"""


def build_analyst_context(
    current_profile_json: str | None,
    new_feedback: list[dict],
    cumulative_stats: list[dict],
    recent_competence: list[dict],
    all_feedback: list[dict],
    skills: list[dict],
) -> str:
    """Build the user message for the Analyst brain."""
    sections = []

    # Current profile
    if current_profile_json:
        sections.append(f"## CURRENT PROFILE\n```json\n{current_profile_json}\n```")
    else:
        sections.append("## CURRENT PROFILE\n(No profile yet — this is the first assessment.)")

    # New feedback just received
    if new_feedback:
        lines = ["## NEW FEEDBACK (just received)"]
        for f in new_feedback:
            lines.append(
                f"- [{f.get('track', '')}] {f.get('title', '')} | "
                f"Status: {f.get('status', '')} | "
                f"Hours: est={f.get('estimated_hours', '?')}, "
                f"actual={f.get('actual_hours', '?')} | "
                f"Notes: {f.get('notes', '')} | "
                f"Learnings: {f.get('learnings', '')}"
            )
        sections.append("\n".join(lines))

    # Cumulative track stats
    if cumulative_stats:
        lines = ["## CUMULATIVE TRACK STATS"]
        for s in cumulative_stats:
            done = s.get("done", 0) or 0
            skipped = s.get("skipped", 0) or 0
            hours = s.get("hours", 0) or 0
            lines.append(
                f"- {s['track']}: {done} done, {skipped} skipped, {hours:.1f}h total"
            )
        sections.append("\n".join(lines))

    # Skill states
    if skills:
        lines = ["## CURRENT SKILL STATES"]
        for s in skills:
            lines.append(
                f"- {s['track_id']}: phase={s['current_phase']}, "
                f"hours={s.get('hours_invested', 0):.1f}, "
                f"items={s.get('items_completed', 0)}"
            )
        sections.append("\n".join(lines))

    # Historical feedback (for pattern analysis)
    if all_feedback:
        lines = ["## HISTORICAL FEEDBACK (most recent first, up to 50)"]
        for f in all_feedback[:50]:
            parts = [f"[{f.get('track', '')}] {f.get('title', '')}"]
            if f.get("notes"):
                parts.append(f"Notes: {f['notes']}")
            if f.get("learnings"):
                parts.append(f"Learnings: {f['learnings']}")
            parts.append(f"Status: {f.get('status', '')} | {str(f.get('received_at', ''))[:10]}")
            lines.append("- " + " | ".join(parts))
        sections.append("\n".join(lines))

    sections.append(
        "## INSTRUCTION\n"
        "Produce the updated UserIntelligenceProfile as JSON. "
        "Assess competence changes, update learning velocity, and refresh the narrative summary. "
        "Be evidence-based — cite specific tasks and feedback in your assessments."
    )

    return "\n\n".join(sections)
