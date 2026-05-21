# Planner Agent

## Project Overview
Adaptive daily task orchestrator for security career growth.
Generates hyper-specific daily tasks based on current progress, skill gaps, and portfolio needs.
Sends daily briefing via email, receives feedback via email reply, adapts planning accordingly.

## Tech Stack
- Python 3.12, managed with uv
- Claude API (anthropic SDK) for task generation and feedback parsing
- Resend API for outbound daily briefing emails
- IMAP (stdlib) for inbound feedback via email replies
- Click for CLI
- Pydantic for config validation and data models
- SQLite for all state persistence
- python-dotenv for auto-loading .env

## Project Structure
- `src/planner_agent/` — main package (src layout)
- `src/planner_agent/agent/` — Claude API agent loop and prompts
- `src/planner_agent/email/` — Resend sender + IMAP receiver + HTML templates
- `src/planner_agent/state/` — SQLite state persistence + newsletter DB reader
- `src/planner_agent/models.py` — Pydantic models (Task, Skill, Achievement, NewsletterReading, etc.)
- `src/planner_agent/config.py` — Pydantic config validation
- `src/planner_agent/scheduling.py` — launchd/cron scheduling
- `AboutMe.md` — user profile (shared with Newsletter Agent)
- `config.yaml` — operational config
- `tests/` — test suite

## Key Commands
```bash
uv run planner daily                    # generate briefing + send email
uv run planner daily --no-email         # generate briefing, print to terminal only
uv run planner process-replies          # parse latest email reply, update task state
uv run planner briefing                 # generate briefing without email
uv run planner complete <task_id>       # mark task done via CLI
uv run planner skip <task_id>           # mark task skipped via CLI
uv run planner status                   # show progress across all tracks
uv run planner portfolio                # show portfolio status and gaps
uv run planner log-achievement          # record a CVE, paper, talk, etc.
uv run planner init                     # initialize skill tracks from config
uv run planner history                  # show recent completed tasks
uv run planner install-schedule         # install daily launchd/cron job
uv run planner install-schedule --uninstall  # remove schedule
```

## Architecture
- **Agent loop**: Read state from SQLite → build context prompt → Claude generates structured JSON → parse into Task objects → persist to DB → render HTML → send via Resend
- **Feedback loop**: `process-replies` polls IMAP → finds latest reply to `[Planner]` email → Claude Haiku parses natural language into structured feedback → updates task statuses, hours, and learnings
- **Newsletter integration**: Reads Newsletter Agent's SQLite DB (read-only). Newsletter articles are rendered as a single reading block (last task), separate from Claude's generated tasks. Persisted as a real task so feedback tracking works.
- **No frameworks**: Raw Anthropic SDK + Pydantic + SQLite. The intelligence is in the prompts.

## Adaptive Loop
1. `planner daily` reads full state (skills, tasks, achievements, completion stats, skip patterns, newsletter articles) and sends to Claude
2. Claude generates tasks adapted to current progress — won't repeat completed resources, adjusts difficulty as hours accumulate, flags skip patterns
3. User replies to briefing email with natural language progress update
4. `planner process-replies` parses the latest reply, updates task statuses and skill hours
5. Next `planner daily` sees updated state and adapts

## Task Specificity Rule
The system prompt enforces hyper-specific tasks. Never "Complete 2 SSRF labs" — always exact lab titles, URLs, and rationale for why that specific resource.

## Newsletter Integration
- `state/newsletter.py` — NewsletterReader reads Newsletter Agent's SQLite DB (read-only, `?mode=ro`)
- Newsletter articles appear in a separate `newsletter_reading` block in Claude's JSON output
- Converted to a real Task on persist so it's trackable via feedback
- Articles already completed (matched by URL) are excluded
- Claude decides which articles to include based on relevance to current focus track
- Each Newsletter Agent run costs $5-6 — Planner never runs it, only suggests when needed
- Graceful degradation: if newsletter DB missing/unreadable, briefing generates normally

## Learning Loop
Every skill follows: Learn → Practice → Produce. The planner tracks which phase each skill is in and assigns tasks accordingly. Phase transitions are Claude's judgment call based on demonstrated understanding, completion patterns, and confidence signals — not a fixed item count.

## Environment Variables
- `ANTHROPIC_API_KEY` — required for Claude API
- `RESEND_API_KEY` — required for sending briefing emails
- `IMAP_SERVER` — IMAP server for receiving replies (default: imap.gmail.com)
- `IMAP_EMAIL` — email address for IMAP login
- `IMAP_PASSWORD` — app password for IMAP login

## State (SQLite)
All state lives in `data/planner.db`:
- `skills` — skill tracks with phase, hours invested, items completed
- `tasks` — all assigned tasks with status, time estimates, learnings
- `achievements` — portfolio items (CVEs, papers, talks, etc.)
- `daily_briefings` — briefing history with tasks JSON and email message IDs
- `feedback_log` — all feedback received (email or CLI)
- `meta` — key-value store (last briefing date, etc.)
