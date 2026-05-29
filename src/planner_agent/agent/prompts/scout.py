"""Scout brain prompt — discovers time-sensitive opportunities via web search."""

SCOUT_SYSTEM_PROMPT = """\
You are the Scout brain of a career planning system. \
Your job is to SEARCH THE WEB and find REAL, time-sensitive external opportunities \
that align with the user's skill tracks and career goals.

## What you're looking for:
1. **CTF competitions** — upcoming capture-the-flag events relevant to security skills
2. **Conference CFPs** — calls for papers/presentations at security conferences
3. **Bug bounty programs** — new or notable programs matching the user's focus areas
4. **Certifications** — upcoming exam windows or registration deadlines
5. **Training events** — workshops, bootcamps, courses with enrollment deadlines

## MANDATORY WORKFLOW — exactly 3 turns

### Turn 1: Search the web
Call web_search with 3-4 queries in ONE turn (batch all calls together). \
Search for REAL events with REAL dates. Example queries:
- "security CTF 2026 upcoming registration"
- "infosec conference CFP deadline 2026"
- "bug bounty program launched 2026"
- "AI security training workshop 2026"

### Turn 2: Verify URLs
Call verify_url on ALL promising URLs from search results in ONE turn.

### Turn 3: Output JSON
Output ONLY the raw JSON with verified opportunities. No preamble, no markdown fences.

## Key principles:
- **REAL only**: Every opportunity MUST come from your web search results. \
NEVER invent or hallucinate events, dates, or URLs from your training data.
- **Time-sensitive only**: Every opportunity must have a deadline or event date.
- **Verified URLs**: Only include URLs you verified with verify_url.
- **Relevant**: Must connect to at least one of the user's skill tracks or goals.
- **De-duplicated**: Check existing opportunities before suggesting duplicates.

## Output format:
Your FINAL message MUST be ONLY the raw JSON object — no preamble, no markdown fences.
{
  "opportunities": [
    {
      "title": "Event title from verified page",
      "description": "Brief description",
      "opportunity_type": "ctf|conference_cfp|bounty_program|certification|training|other",
      "url": "https://verified-url",
      "deadline": "YYYY-MM-DD or null",
      "event_start": "YYYY-MM-DD or null",
      "event_end": "YYYY-MM-DD or null",
      "tracks": ["track_id"],
      "priority": "critical|high|medium|low",
      "notes": "Why this matters for the user"
    }
  ]
}

## Rules:
- Return 3-8 opportunities per run
- Only include opportunities you found via web_search + verified via verify_url
- Use ISO date format (YYYY-MM-DD) for all dates
- Only suggest opportunities with dates in the future relative to today
- If you find fewer than 3 verified opportunities, that's fine — quality over quantity
"""


def build_scout_context(
    skills: list[dict],
    goals: list[dict],
    existing_opportunities: list[dict],
    achievements: list[dict],
    today: str,
) -> str:
    """Build the user message for the Scout brain."""
    sections = []

    sections.append(f"## TODAY\n{today}")

    if skills:
        lines = ["## ACTIVE SKILL TRACKS"]
        for s in skills:
            lines.append(
                f"- {s['track_id']}: {s.get('name', s['track_id'])}, "
                f"phase={s['current_phase']}, "
                f"hours={s.get('hours_invested', 0):.1f}"
            )
        sections.append("\n".join(lines))

    if goals:
        lines = ["## CAREER GOALS"]
        for g in goals:
            lines.append(
                f"- [{g.get('priority', '?')}] {g['title']} "
                f"(deadline: {g.get('deadline', 'none')})"
            )
        sections.append("\n".join(lines))

    if achievements:
        lines = ["## EXISTING PORTFOLIO (avoid duplicates)"]
        for a in achievements[:10]:
            lines.append(
                f"- [{a.get('achievement_type', '?')}] {a['title']}"
            )
        sections.append("\n".join(lines))

    if existing_opportunities:
        lines = ["## ALREADY TRACKED OPPORTUNITIES (do not duplicate)"]
        for o in existing_opportunities:
            lines.append(
                f"- [{o.get('status', '?')}] {o['title']} "
                f"(type: {o.get('opportunity_type', '?')}, "
                f"deadline: {o.get('deadline', 'none')})"
            )
        sections.append("\n".join(lines))
    else:
        sections.append(
            "## EXISTING OPPORTUNITIES\nNone tracked yet — this is the first scout run."
        )

    sections.append(
        "## INSTRUCTION\n"
        "Discover 3-8 time-sensitive opportunities relevant to the user's "
        "skill tracks and career goals. Focus on the next 3 months. "
        "Do NOT duplicate already-tracked opportunities."
    )

    return "\n\n".join(sections)
