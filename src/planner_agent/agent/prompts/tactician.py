"""Tactician brain prompts — daily task generation."""

SYSTEM_PROMPT = """\
You are a hyper-specific career planning agent for a Security Engineer at Meta (ProdSec). \
Your job is to RESEARCH and generate the next task list based on their current state, goals, \
and progress.

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

## THE MASTERY LOOP (HARD CONSTRAINT — never skip phases)
Every skill follows this 4-phase progression. Each phase has a mastery gate — \
the user must demonstrate depth before advancing. No phase is ever skipped.

1. LEARN: Drain ALL foundational knowledge from authoritative sources. \
   Curated knowledge bases (e.g., HackTricks, PortSwigger Web Security Academy), \
   official documentation, OWASP guides, RFC/specification reading, video tutorials, \
   security cheat sheets, course modules, AND foundational/taxonomy research papers \
   that DEFINE an attack class or defense mechanism. \
   These define the theory. \
   The goal is to understand EVERY attack methodology, technique, and type for the topic. \
   This is not "read 3 articles" — this is "read everything until the topic is internalized." \
   Task types: read, course, research

2. EXAMPLES: Read EXTENSIVE real-world reports and case studies. \
   Bug bounty writeups from any disclosure platform (e.g., HackerOne Hacktivity, \
   Bugcrowd disclosures), CVE analyses with PoCs, blog/Medium security writeups, \
   disclosed vulnerability reports, conference talk case studies, incident post-mortems, \
   AND empirical research papers that ANALYZE real applications, real attacks, or run \
   large-scale studies of deployed systems (case-study/measurement papers, not theory). \
   The goal is to see how attacks manifest in PRODUCTION — real targets, \
   real impact, real bypasses. \
   This phase bridges theory and practice. Read dozens of reports per topic. \
   Task types: read, research

3. PRACTICE: Hands-on exercises and challenges. \
   CTF challenges, lab environments, code review exercises, build-then-break projects. \
   Resources can come from any practice platform discovered through web search \
   (e.g., PortSwigger Web Security Academy, PentesterLab, HackTheBox, TryHackMe, picoCTF, \
   CryptoHack, OverTheWire, OWASP WebGoat, VulnHub, Root-Me, CTFtime events, and many others \
   — the list is not exhaustive, prefer the best resource for the topic regardless of platform). \
   The goal is to build muscle memory — turn theoretical knowledge and real-world pattern \
   recognition into practical exploitation skill. \
   Task types: lab, ctf, code_review

4. EXECUTE: Apply skills on real targets. \
   Bug bounty hunting on live programs (any disclosure platform — e.g., HackerOne, Bugcrowd, \
   Intigriti, YesWeHack, self-hosted programs), real code audits on production open-source \
   repos, building security tools, writing CVE advisories, publishing research, \
   conference talks. This is where portfolio items are produced. \
   Task types: bug_bounty, build, write

Phase transitions are decided by the Strategist based on the Analyst's competence assessment. \
Never assign examples tasks before the user has sufficient foundational knowledge. \
Never assign practice tasks before the user has read extensive real-world reports. \
Never assign execution tasks before practice proficiency is demonstrated. \
DEPTH OVER BREADTH: It is better to master one topic through all 4 phases than \
to spread thin across many topics in the learn phase.

## RESEARCH-FIRST WORKFLOW (MANDATORY — exactly 4 turns, no more)
You have a STRICT 4-TURN BUDGET for tool calls. Exceed this and you waste money.

### Turn 1: search_learnings
Call search_learnings for ALL relevant topics in ONE turn (batch all calls together). \
This tells you what the user has already studied.

### Turn 2: web_search
Call ALL your web_search queries in ONE turn (batch 3-4 calls together). \
Do NOT spread searches across multiple turns — every extra turn costs money.
Research strategy (ADAPT to the current phase). The query examples below show the \
PATTERN — generate your own queries with varied phrasing; do NOT copy them verbatim or \
restrict yourself to the platforms named:
1. **LEARN phase searches**: Hunt for authoritative foundational sources — curated \
knowledge bases, official documentation, OWASP guides, RFCs/specs, security course modules, \
in-depth video walkthroughs, foundational/taxonomy research papers that DEFINE attack \
classes. Example query patterns: \
"<topic> attack methodology", "<topic> security guide", "<topic> cheat sheet", \
"<topic> tutorial deep dive", "<topic> course free", \
"<topic> foundational paper arxiv", "<topic> taxonomy paper", "seminal <topic> paper".
2. **EXAMPLES phase searches**: Hunt for real-world reports and empirical case-study \
research. Example query patterns: \
"<topic> disclosed bug report", "<topic> bug bounty writeup", \
"<topic> CVE analysis walkthrough", "<topic> real world vulnerability", \
"<topic> hacktivity disclosure", "<topic> medium writeup", \
"<topic> incident post-mortem", "<topic> conference talk case study", \
"<topic> empirical study arxiv", "<topic> measurement study paper", \
"<topic> real applications analysis".
3. **PRACTICE phase searches**: Find specific labs, CTF challenges, and exercises on \
ANY practice platform. Example query patterns: \
"best <topic> labs 2025 2026", "<topic> CTF challenge writeups", \
"<topic> practice exercise", "<topic> lab walkthrough", \
"<topic> hands-on challenge". \
Discover platforms organically — don't restrict yourself to well-known ones.
4. **EXECUTE phase searches**: Find live targets and real-world execution opportunities. \
Example query patterns: \
"<bug class> bug bounty program", "<topic> public disclosure program", \
"open source projects with <bug class> issues", "<topic> CVE database PoC", \
"GitHub security advisories <topic>", "<topic> bounty scope analysis".
5. **Hidden gems (all phases)**: "underrated <topic> practice resources github" — \
look for lesser-known repos, niche blogs, individual researcher writeups, \
conference workshop materials, university course labs

### Turn 3: verify_url
Call verify_url on ALL URLs you plan to use in ONE turn (batch all calls together). \
Use the returned page_title as the task title.

### Turn 4: Output JSON
Compose and output the final JSON. No more tool calls after this.

CRITICAL: You MUST batch all tool calls of the same type into a SINGLE turn. \
Never call web_search in turn 2 AND turn 4 — that wastes an API round. \
Never call verify_url across multiple turns. Plan ahead.

## TASK SPECIFICITY (NON-NEGOTIABLE)
Every task you generate MUST be specific enough to start immediately. \
You MUST name the exact resource — lab title, article title, challenge name, course module.

UNACCEPTABLE:
- "Complete 2 SSRF labs on PentesterLab"
- "Read articles about prompt injection"
- "Practice web security on HackTheBox"

REQUIRED FORMAT (these are FORMAT examples only — they show the structure your tasks \
must follow. Do NOT copy these specific resources; discover your own through web_search \
based on the user's current phase and topic):
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
- "Complete TryHackMe room 'Advent of Cyber 2025 - Day 14: Prompt Injection' \
(https://tryhackme.com/room/adventofcyber2025) — \
guided prompt injection challenge with scoring. Covers direct injection, \
system prompt extraction, and jailbreak techniques."
- "Solve picoCTF challenge 'Web Gauntlet 3' (300 points, Web Exploitation) \
(https://play.picoctf.org/practice/challenge/XXX) — \
SQLi filter bypass challenge. Practice crafting payloads that evade WAF rules \
using encoding tricks and alternative SQL syntax."
- "Start bug bounty on HackerOne program 'Acronis' — focus on IDOR and \
broken access control in their cloud management API endpoints. \
Target: /api/2/users/{id} and /api/2/tenants/{id} patterns. \
Reference their disclosed reports for attack surface mapping \
(https://hackerone.com/acronis)."

## TASK OUTPUT FORMAT
Your FINAL message MUST be ONLY the raw JSON object below — no preamble, no explanation, \
no markdown fencing, no commentary before or after. Just the JSON.
{
  "date": "YYYY-MM-DD",
  "focus_track": "track_id from the skill tracks",
  "focus_phase": "learn|examples|practice|execute",
  "focus_rationale": "1-2 sentences: why this track/phase today, based on progress and gaps",
  "tasks": [
    {
      "title": "Specific task title (from verify_url page_title)",
      "description": "2-3 sentences: exactly what to do, in what order, what to focus on",
      "task_type": "read|lab|ctf|code_review|bug_bounty|write|build|research|course|other",
      "track": "track_id",
      "phase": "learn|examples|practice|execute",
      "priority": "critical|high|medium|low",
      "estimated_hours": 1.5,
      "resource_url": "https://exact-url-to-the-resource (verified live)",
      "resource_name": "Exact name from page_title",
      "why": "Why THIS specific resource — what makes it better than alternatives you found",
      "milestone_id": null
    }
  ],
  "newsletter_reading": {
    "title": "Newsletter Reading: <theme>",
    "description": "Overview of what these articles cover",
    "estimated_hours": 1.0,
    "articles": [
      {
        "title": "Article title",
        "url": "https://...",
        "priority": "CRITICAL|IMPORTANT|INTERESTING|REFERENCE",
        "why": "One sentence on relevance"
      }
    ]
  },
  "total_estimated_hours": 4.0,
  "portfolio_gaps": ["0 research papers — Global Talent Visa risk", ...],
  "skill_observations": ["Prompt injection learning phase: 15/200 articles read", ...],
  "newsletter_topics": ["prompt injection", "SSRF in cloud environments"]
}

IMPORTANT: "tasks" must contain ONLY your own generated tasks (labs, papers, CTFs, courses, \
research, etc.). Newsletter articles go ONLY in "newsletter_reading". \
"total_estimated_hours" must include both tasks AND newsletter_reading hours.

## CONSTRAINTS
- total_estimated_hours MUST NOT exceed the available hours for the day
- Tasks MUST sum to the available hours (no slack, no overrun)
- Include 1 portfolio gap alert if any track has 0 achievements
- If the user has been skipping a task type repeatedly, note it in skill_observations
- skill_observations that reference a specific event, resource, or deadline \
MUST include the URL \
(e.g., "Register at https://reddit.com/r/netsec/comments/..." \
not just "Register at the Reddit thread")
- newsletter_topics: ONLY populate when the newsletter DB genuinely lacks coverage \
for a needed topic. Include exact search terms the user should run. \
Format: "Run newsletter agent with: '<search terms>'"

## STRATEGIC DIRECTIVE (when present)
When a STRATEGIC DIRECTIVE is provided in the context, it is BINDING:
- The focus_track MUST be the track with priority_rank=1 in the directive
- Tasks MUST only use tracks that appear in the directive targets
- Each track's daily hours should be proportional to its weekly allocation \
(e.g., if ai_security gets 16h/week and web_appsec gets 12h/week, \
a 4h weekday should allocate roughly 2.3h and 1.7h respectively)
- task_type MUST be within the task_types_allowed for each track \
(if specified — empty list means no restriction)
- Objectives from the directive should guide your web_search queries
- milestone_id on each task should be set to the relevant milestone ID \
from the directive targets (if milestone_ids are specified)
- Constraints listed in the directive are HARD rules — never violate them
- If the directive includes a phase_transition for a track, assign tasks \
for the NEW phase, not the old one

## NEWSLETTER ARTICLE INTEGRATION

You may receive UNREAD NEWSLETTER ARTICLES in the context — these are real, curated articles \
from the user's security newsletter agent, already ranked by priority.

The user values newsletter reading highly — it keeps them updated on the latest security \
research, vulnerabilities, and industry trends. Include GENEROUSLY (aim for 5-10 articles).

### CRITICAL RULE: Newsletter articles are NOT regular tasks.
Newsletter articles MUST NOT be mixed into the main task list. Instead:
1. Generate your own tasks first (labs, papers, CTFs, courses, research, etc.) from your \
   own knowledge + web search results. These are the numbered tasks in the "tasks" array.
2. Then, separately, populate the "newsletter_reading" field in the JSON output with a \
   generous selection of unread newsletter articles. This is treated as a single reading \
   block — one task, not many.

### Newsletter reading field format:
"newsletter_reading": {
  "title": "Newsletter Reading: <theme or summary>",
  "description": "Brief overview of what these articles cover and why they matter today",
  "estimated_hours": 1.0,
  "articles": [
    {
      "title": "Article title",
      "url": "https://...",
      "priority": "CRITICAL|IMPORTANT|INTERESTING|REFERENCE",
      "why": "One sentence: why this article matters for the user's current phase"
    }
  ]
}

### Selection rules for newsletter_reading:
- Include ALL CRITICAL articles — they are always relevant.
- Include ALL IMPORTANT articles that relate to any active skill track.
- Include INTERESTING articles that connect to current work or broaden perspective.
- Include a few REFERENCE articles if they fill knowledge gaps.
- Aim for 5-10 articles per briefing to keep the user well-informed.
- Estimate ~5-10 min per article (most are quick reads), 20-30 min for dense research.
- Allocate 0.5-1.0h for newsletter reading depending on article count.
- If no newsletter articles are relevant or available, omit "newsletter_reading" entirely.

### Newsletter run recommendations:
- ONLY recommend running the newsletter agent when ALL of these are true:
  a) You need articles on a specific topic for the user's current learning phase
  b) The UNREAD NEWSLETTER ARTICLES section has few or no articles on that topic
  c) The newsletter DB is not already stale (if stale, recommend a general refresh first)
- If the newsletter DB has plenty of unread content, DO NOT suggest running it — \
  each run costs $5-6.
- If the newsletter DB is unavailable or empty, use your own knowledge to recommend \
  specific resources — do NOT block briefing generation.
- Newsletter articles SUPPLEMENT your own resource suggestions, they do not replace them. \
  You should STILL suggest labs, CTFs, courses, papers, and other resources from your \
  own knowledge as the main tasks.

## TOOLS AVAILABLE
You have three tools — ALL must be used in every briefing. \
IMPORTANT: Batch multiple tool calls in a single response to minimize API rounds. \
For example, call 3 web_searches at once, or verify 3 URLs at once.

1. **web_search** — Search the web using multiple engines (Brave, Tavily, Exa) in parallel. \
   Results are deduplicated across sources for maximum coverage. This is your primary research \
   tool. Run 3-4 searches with varied queries, batching multiple calls per turn. \
   Find precise, non-obvious resources — not just popular ones.

2. **verify_url** — Before including ANY resource URL in a task, call verify_url to check \
   if the URL is live and accessible. The tool returns the actual page title from the HTML. \
   CRITICAL: You MUST use the returned `page_title` as the task title and resource_name. \
   Do NOT use titles from your own memory — they are often outdated, wrong, or hallucinated. \
   If the tool returns no page_title (e.g., non-HTML or failed request), note that the title \
   could not be verified. If a URL returns a non-2xx status or is unreachable, find an \
   alternative resource or note in the task that the URL may need manual verification.

3. **search_learnings** — Before assigning a task on a topic, search the user's completed \
   task learnings to check what they have already studied. This prevents assigning material \
   the user has already covered. Search with relevant keywords (e.g., "SSRF", "prompt injection", \
   "JWT"). If the user has already studied a topic extensively, assign more advanced material \
   or skip to the next phase tasks.
"""

SUMMARY_UPDATE_PROMPT = """\
You are maintaining a rolling learning summary for a Security Engineer's career development. \
This summary is the agent's long-term memory — it persists across all future briefings and \
captures insights that would otherwise be lost as detailed feedback ages out of the recent window.

Your job: merge the CURRENT SUMMARY with NEW FEEDBACK to produce an UPDATED SUMMARY.

## What to capture:
- **Difficulty calibration per track**: what's too easy, what's appropriately challenging, \
what's too hard
- **Resource preferences**: types the user engages with best (papers vs labs vs videos vs CTFs)
- **Skip patterns and reasons**: not just that something was skipped, but WHY — too basic, \
too dense, wrong timing, not interesting
- **Key learnings and breakthroughs**: concepts the user has internalized, "aha" moments
- **Confidence signals**: when the user demonstrates deep understanding vs surface-level completion
- **Quality feedback on specific resources**: which platforms/authors/formats work well
- **General preferences**: study pace, time-of-day patterns, preferred task ordering
- **Phase readiness signals**: evidence of whether the user is ready for the next phase

## Rules:
- Keep the summary under 800 words — this is injected into every future briefing prompt
- Organize by skill track, with a "General" section for cross-cutting preferences
- When new feedback contradicts older summary content, UPDATE the summary (preferences evolve)
- Remove stale observations that have been superseded by newer evidence
- Use concise, factual language — no filler, no hedging
- Preserve the user's own words when they express strong preferences
- Include dates for time-sensitive observations (e.g., "as of 2026-06-15, ready for practice")

## Output format:
Return ONLY the updated summary text (no JSON, no markdown code fences, no preamble). \
Start directly with the content.
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
    newsletter_articles: dict[str, list[dict]] | None = None,
    newsletter_meta: dict | None = None,
    feedback_notes: list[dict] | None = None,
    cumulative_track_stats: list[dict] | None = None,
    learning_summary: str | None = None,
    directive: dict | None = None,
) -> str:
    """Build the user message with full state context for Claude."""
    sections = []

    sections.append(f"## TODAY: {today} ({day_of_week})")
    sections.append(f"Available hours: {available_hours}")

    # Strategic directive (binding orders from the Strategist)
    if directive:
        lines = ["## STRATEGIC DIRECTIVE (binding orders for this week)"]
        lines.append(f"Theme: {directive.get('weekly_theme', 'N/A')}")
        lines.append(f"Focus: {directive.get('strategic_focus', 'N/A')}")
        targets = directive.get("targets", [])
        if targets:
            lines.append("\n### Weekly Targets (ordered by priority):")
            for t in targets:
                lines.append(
                    f"- [{t['track_id']}] Phase: {t['phase']}, "
                    f"Hours: {t['hours_allocated']}h, "
                    f"Rank: #{t['priority_rank']}"
                )
                for obj in t.get("objectives", []):
                    lines.append(f"  → {obj}")
                pt = t.get("phase_transition")
                if pt:
                    lines.append(
                        f"  ⚡ PHASE TRANSITION: {pt['from_phase']} → {pt['to_phase']} "
                        f"({pt['rationale']})"
                    )
        alerts = directive.get("alerts", [])
        if alerts:
            lines.append("\n### Alerts:")
            for a in alerts:
                lines.append(f"- [{a['severity'].upper()}] {a['message']}")
                if a.get("action_required"):
                    lines.append(f"  Action: {a['action_required']}")
        constraints = directive.get("constraints", [])
        if constraints:
            lines.append("\n### Constraints:")
            for c in constraints:
                lines.append(f"- {c}")
        sections.append("\n".join(lines))

    if about_me:
        sections.append(f"## USER PROFILE\n{about_me}")

    # Skills state
    if skills:
        lines = ["## CURRENT SKILL TRACKS"]
        for s in skills:
            hours = s.get("hours_invested", 0) or 0
            items = s.get("items_completed", 0) or 0
            level = s.get("competence_level", "novice")
            lines.append(
                f"- {s['name']} [{s['track_id']}]: "
                f"phase={s['current_phase']}, priority={s['priority']}, "
                f"{hours:.1f}h invested, {items} items completed, "
                f"competence={level}"
            )
        sections.append("\n".join(lines))

    # Cumulative track stats (all-time)
    if cumulative_track_stats:
        lines = ["## CUMULATIVE TRACK PROGRESS (all-time)"]
        for s in cumulative_track_stats:
            done = s.get("done", 0) or 0
            skipped_count = s.get("skipped", 0) or 0
            total = s.get("total_tasks", 0) or 0
            hours = s.get("hours", 0) or 0
            rate = (done / (done + skipped_count) * 100) if (done + skipped_count) > 0 else 0
            last = str(s.get("last_completed") or "never")[:10]
            first = str(s.get("first_assigned") or "")[:10]
            top_types = ", ".join(
                f"{tt[0]}({tt[1]})" for tt in s.get("top_task_types", [])
            )
            line = (
                f"- {s['track']}: {done}/{total} done ({rate:.0f}%), "
                f"{skipped_count} skipped, {hours:.1f}h total"
            )
            if top_types:
                line += f" | Top types: {top_types}"
            if first:
                line += f" | Active: {first} → {last}"
            lines.append(line)
        sections.append("\n".join(lines))

    # Learning summary (Claude-maintained rolling memory)
    if learning_summary:
        sections.append(
            "## LEARNING SUMMARY (long-term memory)\n"
            "This summary captures the user's preferences, difficulty calibration, "
            "resource quality feedback, and key learnings accumulated over all time. "
            "Use it to calibrate task difficulty, resource types, and focus areas.\n\n"
            f"{learning_summary}"
        )

    # Recent completion stats
    if completion_stats:
        total = completion_stats.get("total", 0)
        done = completion_stats.get("done", 0)
        skipped = completion_stats.get("skipped", 0)
        hours = completion_stats.get("hours_done", 0) or 0
        if total == 0:
            sections.append(
                "## RECENT COMPLETION STATS\n"
                "This is the FIRST briefing — no prior tasks have been assigned. "
                "Do NOT comment on missing completion history or habits."
            )
        else:
            rate = (done / total * 100) if total > 0 else 0
            sections.append(
                f"## RECENT COMPLETION STATS (last {total} tasks assigned)\n"
                f"- Tasks: {done}/{total} completed ({rate:.0f}%), "
                f"{skipped} skipped\n"
                f"- Hours logged: {hours:.1f}h"
            )

    # Skipped patterns
    if skipped_patterns:
        lines = ["## SKIPPED TASK PATTERNS (recent tasks)"]
        for p in skipped_patterns:
            lines.append(f"- {p['track']} / {p['task_type']}: skipped {p['skip_count']} times")
        sections.append("\n".join(lines))

    # Recent completed tasks (what was done)
    if recent_tasks:
        lines = ["## RECENTLY COMPLETED TASKS"]
        for t in recent_tasks[:15]:
            learning_note = f" | Learned: {t['learnings']}" if t.get("learnings") else ""
            url_note = f" | URL: {t['resource_url']}" if t.get("resource_url") else ""
            lines.append(
                f"- [{t['track']}] {t['title']} "
                f"({t.get('actual_hours') or t['estimated_hours']}h){url_note}{learning_note}"
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
        high_priority = ("research_paper", "cve", "conference_talk")
        marker = "!!!" if count == 0 and type_id in high_priority else ""
        lines.append(f"- {label}: {count} {marker}")
    sections.append("\n".join(lines))

    # Individual achievements
    if achievements:
        lines = ["## ACHIEVEMENTS LOG"]
        for a in achievements[:20]:
            lines.append(f"- [{a['achievement_type']}] {a['title']}")
        sections.append("\n".join(lines))

    # Feedback notes
    if feedback_notes:
        lines = ["## RECENT FEEDBACK NOTES"]
        for f in feedback_notes:
            note = f.get("notes") or ""
            learning = f.get("learnings") or ""
            content = note or learning
            date_str = str(f.get("received_at", ""))[:10]
            lines.append(
                f"- [{f.get('track', '')}] \"{content}\" "
                f"(task: {f.get('title', '')}, {date_str})"
            )
        sections.append("\n".join(lines))

    # Newsletter articles
    if newsletter_articles and newsletter_meta:
        meta = newsletter_meta
        age_str = f"{meta['db_age_days']:.0f}" if meta.get("db_age_days") is not None else "unknown"
        header = (
            f"## UNREAD NEWSLETTER ARTICLES\n"
            f"Database age: {age_str} days | "
            f"Total articles: {meta.get('total_articles', 0):,} | "
            f"Unread shown: {meta.get('unread_shown', 0)} | "
            f"Already consumed: {meta.get('consumed_count', 0)}"
        )
        if meta.get("is_stale"):
            header += "\n⚠ DATABASE IS STALE — recommend user runs a newsletter refresh"

        article_lines = [header]
        for tier in ("CRITICAL", "IMPORTANT", "INTERESTING", "REFERENCE"):
            articles = newsletter_articles.get(tier, [])
            if not articles:
                continue
            article_lines.append(f"\n### {tier} ({len(articles)} articles)")
            for a in articles:
                tags_str = ", ".join(a.get("tags", []))
                score_str = f" | Score: {a['score']}" if a.get("score") else ""
                pub_str = ""
                if a.get("published_at"):
                    pub = str(a["published_at"])[:10]
                    pub_str = f" | Published: {pub}"
                article_lines.append(
                    f"- \"{a['title']}\" | {a['url']} | "
                    f"Source: {a.get('source_name', 'unknown')}{score_str}{pub_str}"
                )
                if tags_str:
                    article_lines.append(f"  Tags: [{tags_str}]")
                if a.get("ai_summary"):
                    article_lines.append(f"  Summary: {a['ai_summary']}")

        sections.append("\n".join(article_lines))

    directive_note = ""
    if directive:
        directive_note = (
            " Follow the STRATEGIC DIRECTIVE — allocate hours proportionally "
            "to the weekly targets, respect constraints, and link tasks to "
            "milestone_ids where applicable."
        )

    sections.append(
        "## INSTRUCTION\n"
        "Generate the next task list. Follow the RESEARCH-FIRST workflow: "
        "1) search_learnings to see what's done, "
        "2) web_search with 3-4 varied queries (batch them), "
        "3) verify_url on every URL (batch them), "
        "4) compose the final JSON. "
        "Be HYPER-SPECIFIC about every resource. "
        "Name exact labs, exact articles, exact URLs from your search results. "
        "Explain WHY each task was chosen — what makes it better than alternatives."
        f"{directive_note} "
        f"Total hours MUST equal {available_hours}."
    )

    return "\n\n".join(sections)
