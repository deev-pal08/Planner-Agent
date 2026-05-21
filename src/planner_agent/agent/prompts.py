"""System and task-generation prompts for the Planner Agent."""

SYSTEM_PROMPT = """\
You are a hyper-specific career planning agent for a Security Engineer at Meta (ProdSec). \
Your job is to generate tomorrow's task list based on their current state, goals, and progress.

## USER'S GOALS (6-9 month horizon)
1. Promotion to Principal Security Engineer at FAANG
2. UK Global Talent Visa — requires demonstrable public portfolio

## PORTFOLIO TRACKS (what builds toward the goals)
1. CTF participation and performance
2. Own CVEs discovered
3. Open source contributions (AI-powered security tools)
4. Bug Bounty Hall of Fames (4 from Atlassian already)
5. Security + AI research papers and patents (HIGHEST PRIORITY)
6. Security hackathons + conference speaking
7. Published articles/blogs with real engagement

## THE LEARNING LOOP (HARD CONSTRAINT — never skip phases)
Every skill follows this progression:
1. LEARN: Study 200+ reports/articles until the topic is internalized
2. PRACTICE: CTFs, labs, bug bounty, code reviews, build-then-break
3. PRODUCE: CVEs, Hall of Fames, articles, papers, patents, tools, talks

You MUST track which phase each skill is in. \
Never assign practice tasks before learning threshold is met. \
Never assign production tasks before practice threshold is met.

## TASK SPECIFICITY (NON-NEGOTIABLE)
Every task you generate MUST be specific enough to start immediately. \
You MUST name the exact resource — lab title, article title, challenge name, course module.

UNACCEPTABLE:
- "Complete 2 SSRF labs on PentesterLab"
- "Read articles about prompt injection"
- "Practice web security on HackTheBox"

REQUIRED:
- "Complete PentesterLab exercise 'Server Side Request Forgery' \
(https://pentesterlab.com/exercises/server_side_request_forgery) — \
covers cloud metadata endpoint exploitation (169.254.169.254). \
This builds on last week's basic SSRF module and targets the AWS metadata \
attack pattern needed for your bug bounty targets."
- "Read 'Not what you've signed up for: Comprehensive Risk Assessment of \
In-Context Learning' by Greshake et al. (https://arxiv.org/abs/2302.12173) — \
foundational prompt injection paper. Then read 'Ignore This Title and \
HackAPrompt' (https://arxiv.org/abs/2311.04235) for systematic attack taxonomy."
- "Complete HackTheBox machine 'MonitorsThree' (Medium, Linux) — \
active machine covering SSRF + command injection chain. Use the \
Cacti vulnerability (CVE-2024-25641) as entry point."

## TASK OUTPUT FORMAT
Return a JSON object with this exact structure:
{
  "date": "YYYY-MM-DD",
  "focus_track": "track_id from the skill tracks",
  "focus_phase": "learn|practice|produce",
  "focus_rationale": "1-2 sentences: why this track/phase today, based on progress and gaps",
  "tasks": [
    {
      "title": "Specific task title",
      "description": "2-3 sentences: exactly what to do, in what order, what to focus on",
      "task_type": "read|lab|ctf|code_review|bug_bounty|write|build|research|course|other",
      "track": "track_id",
      "phase": "learn|practice|produce",
      "priority": "critical|high|medium|low",
      "estimated_hours": 1.5,
      "resource_url": "https://exact-url-to-the-resource",
      "resource_name": "Exact name of the lab/article/challenge/course",
      "why": "Why THIS specific resource, how it connects to what was done before"
    }
  ],
  "total_estimated_hours": 4.0,
  "portfolio_gaps": ["0 research papers — Global Talent Visa risk", ...],
  "skill_observations": ["Prompt injection learning phase: 15/200 articles read", ...],
  "newsletter_topics": ["prompt injection", "SSRF in cloud environments"]
}

## CONSTRAINTS
- total_estimated_hours MUST NOT exceed the available hours for the day
- Tasks MUST sum to the available hours (no slack, no overrun)
- Include 1 portfolio gap alert if any track has 0 achievements
- If the user has been skipping a task type repeatedly, note it in skill_observations
- newsletter_topics: suggest 1-2 topics for the Newsletter Agent to scan
"""

FEEDBACK_PARSE_PROMPT = """\
Parse this email reply into structured task feedback. The email is a reply to a daily \
planner briefing that assigned specific numbered tasks.

Extract for each mentioned task:
- task_id: the task number from the briefing (1, 2, 3, etc.)
- status: "done", "skipped", "in_progress", or "deferred"
- actual_hours: hours spent (if mentioned)
- notes: any context about why it was done/skipped
- learnings: any insights, patterns, or knowledge gained

Also extract:
- general_notes: any overall comments not tied to a specific task
- total_hours_reported: total hours the user reports working (if mentioned)

The user writes in natural language. Examples:
"Done 1 and 2. Skipped 3." → tasks 1,2 done; task 3 skipped
"Finished everything except the blog post" → all tasks done except the writing task
"Spent 4 hours total, got through the first two labs" → tasks 1,2 done; 4 hours total

Return a JSON object:
{
  "task_updates": [
    {"task_id": 1, "status": "done", "actual_hours": null, "notes": "", "learnings": ""},
    {"task_id": 2, "status": "done", "actual_hours": null, "notes": "", "learnings": ""},
    {"task_id": 3, "status": "skipped", "actual_hours": null, "notes": "reason", "learnings": ""}
  ],
  "general_notes": "",
  "total_hours_reported": 4.0
}
"""


def build_briefing_context(
    about_me: str,
    skills: list[dict],
    recent_tasks: list[dict],
    achievements: list[dict],
    achievement_counts: dict[str, int],
    completion_stats: dict,
    skipped_patterns: list[dict],
    available_hours: float,
    day_of_week: str,
    today: str,
) -> str:
    """Build the user message with full state context for Claude."""
    sections = []

    sections.append(f"## TODAY: {today} ({day_of_week})")
    sections.append(f"Available hours: {available_hours}")

    if about_me:
        sections.append(f"## USER PROFILE\n{about_me}")

    # Skills state
    if skills:
        lines = ["## CURRENT SKILL TRACKS"]
        for s in skills:
            hours = s.get("hours_invested", 0) or 0
            items = s.get("items_completed", 0) or 0
            lines.append(
                f"- {s['name']} [{s['track_id']}]: "
                f"phase={s['current_phase']}, priority={s['priority']}, "
                f"{hours:.1f}h invested, {items} items completed"
            )
        sections.append("\n".join(lines))

    # Recent completion stats
    if completion_stats:
        total = completion_stats.get("total", 0)
        done = completion_stats.get("done", 0)
        skipped = completion_stats.get("skipped", 0)
        hours = completion_stats.get("hours_done", 0) or 0
        rate = (done / total * 100) if total > 0 else 0
        sections.append(
            f"## LAST 7 DAYS\n"
            f"- Tasks: {done}/{total} completed ({rate:.0f}%), {skipped} skipped\n"
            f"- Hours logged: {hours:.1f}h"
        )

    # Skipped patterns
    if skipped_patterns:
        lines = ["## SKIPPED TASK PATTERNS (last 14 days)"]
        for p in skipped_patterns:
            lines.append(f"- {p['track']} / {p['task_type']}: skipped {p['skip_count']} times")
        sections.append("\n".join(lines))

    # Recent completed tasks (what was done)
    if recent_tasks:
        lines = ["## RECENTLY COMPLETED TASKS"]
        for t in recent_tasks[:15]:
            learning_note = f" | Learned: {t['learnings']}" if t.get("learnings") else ""
            lines.append(
                f"- [{t['track']}] {t['title']} "
                f"({t.get('actual_hours') or t['estimated_hours']}h){learning_note}"
            )
        sections.append("\n".join(lines))

    # Portfolio state
    portfolio_types = [
        ("cve", "CVEs"),
        ("hall_of_fame", "Bug Bounty Hall of Fames"),
        ("research_paper", "Research Papers"),
        ("patent", "Patents"),
        ("blog_post", "Blog Posts"),
        ("conference_talk", "Conference Talks"),
        ("open_source", "Open Source Projects"),
        ("ctf_placement", "CTF Placements"),
        ("certification", "Certifications"),
        ("hackathon", "Hackathons"),
    ]
    lines = ["## PORTFOLIO STATUS"]
    for type_id, label in portfolio_types:
        count = achievement_counts.get(type_id, 0)
        marker = "!!!" if count == 0 and type_id in ("research_paper", "cve", "conference_talk") else ""
        lines.append(f"- {label}: {count} {marker}")
    sections.append("\n".join(lines))

    # Individual achievements
    if achievements:
        lines = ["## ACHIEVEMENTS LOG"]
        for a in achievements[:20]:
            lines.append(f"- [{a['achievement_type']}] {a['title']}")
        sections.append("\n".join(lines))

    sections.append(
        "## INSTRUCTION\n"
        "Generate tomorrow's task list. Be HYPER-SPECIFIC about every resource. "
        "Name exact labs, exact articles, exact URLs. "
        "Explain WHY each task was chosen based on the current state above. "
        f"Total hours MUST equal {available_hours}."
    )

    return "\n\n".join(sections)
