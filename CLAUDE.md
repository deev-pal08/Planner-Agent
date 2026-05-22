# Planner Agent

## Project Overview
Adaptive daily task orchestrator for security career growth.
Generates hyper-specific daily tasks based on current progress, skill gaps, and portfolio needs.
Sends daily briefing via email, receives feedback via email reply, adapts planning accordingly.

## Tech Stack
- Python 3.12, managed with uv
- Claude API (anthropic SDK) — Sonnet for briefing generation (agent loop with tools), Haiku for feedback parsing
- Resend API for outbound daily briefing emails
- IMAP (stdlib) for inbound feedback via email replies
- Click for CLI
- Pydantic for config validation and data models
- SQLite for all state persistence
- tenacity for API retry logic
- httpx for URL verification
- python-dotenv for auto-loading .env

## Project Structure
- `src/planner_agent/` — main package (src layout)
- `src/planner_agent/agent/` — Claude API agent loop, tools, and prompts
- `src/planner_agent/email/` — Resend sender + IMAP receiver + HTML templates
- `src/planner_agent/state/` — SQLite state persistence + newsletter DB reader
- `src/planner_agent/models.py` — Pydantic models (Task, Skill, Achievement, NewsletterReading, etc.)
- `src/planner_agent/config.py` — Pydantic config validation with field validators
- `src/planner_agent/scheduling.py` — launchd/cron scheduling
- `AboutMe.md` — user profile (shared with Newsletter Agent)
- `config.yaml` — operational config
- `tests/` — test suite (test_store.py, test_loop.py)

## Key Commands
```bash
uv run planner daily                    # generate briefing + send email
uv run planner daily --no-email         # generate briefing, print to terminal only
uv run planner daily --force            # regenerate even if briefing exists for today
uv run planner daily --date 2026-05-22  # generate briefing for a specific date
uv run planner process-replies          # parse latest email reply, confirm, update state
uv run planner process-replies --yes    # skip confirmation (for automation/cron)
uv run planner briefing                 # generate briefing without email
uv run planner briefing --force         # regenerate briefing
uv run planner complete <task_id>       # mark task done via CLI
uv run planner skip <task_id>           # mark task skipped via CLI
uv run planner status                   # show progress across all tracks
uv run planner portfolio                # show portfolio status and gaps
uv run planner log-achievement          # record a CVE, paper, talk, etc.
uv run planner init                     # initialize skill tracks from config
uv run planner history                  # show recent completed tasks
uv run planner install-schedule         # install daily launchd/cron job
uv run planner install-schedule --uninstall  # remove schedule
uv run pytest tests/                    # run tests (9 tests)
uv run ruff check src/                  # lint
```

## Architecture
- **Agent loop**: Read state from SQLite → build context prompt (with feedback notes, cumulative stats, learning summary) → Claude Sonnet runs agent loop with `verify_url` and `search_learnings` tools → generates structured JSON → parse into Task objects → persist to DB → render HTML → send via Resend
- **Tool use**: `verify_url` does a GET request, extracts `<title>` tag from HTML, returns `page_title`. Claude must use the returned title, not titles from its own memory. `search_learnings` searches completed task learnings to avoid repeating material.
- **Long-term memory**: Two layers injected into every briefing prompt:
  1. **Cumulative track stats** (SQL, $0): all-time per-track done/skipped counts, completion rate, hours, top task types, first/last active dates
  2. **Rolling learning summary** (Haiku, ~$0.001/update): Claude-maintained ~800-word summary of user preferences, difficulty calibration, skip reasons, key learnings, resource quality feedback, phase readiness signals. Stored in `meta` table as `learning_summary`. Updated after `process-replies`, `complete` (with notes), `skip` (with reason).
- **Feedback loop**: `process-replies` polls IMAP → finds latest reply → Claude Haiku parses feedback → shows parsed results → prompts for confirmation → updates task statuses, hours, learnings → updates rolling learning summary
- **Newsletter integration**: Reads Newsletter Agent's SQLite DB (read-only). Newsletter articles are rendered as a single reading block (last task), separate from Claude's generated tasks. Persisted as a real task so feedback tracking works.
- **Retry logic**: All API calls wrapped with tenacity (3 attempts, exponential backoff on APIStatusError)
- **Dedup protection**: Same-day briefing runs are blocked unless `--force` is passed
- **Fallback email**: If briefing generation fails, a plain-text notification email is sent with error details and last known state
- **No frameworks**: Raw Anthropic SDK + Pydantic + SQLite. The intelligence is in the prompts.

## Adaptive Loop
1. `planner daily` reads full state (skills, cumulative stats, learning summary, tasks, achievements, completion stats, skip patterns, feedback notes, newsletter articles) and sends to Claude
2. Claude runs agent loop — searches past learnings, verifies URLs, generates tasks adapted to current progress and long-term memory
3. User replies to briefing email with natural language progress update
4. `planner process-replies` parses the latest reply, shows parsed feedback, prompts for confirmation, updates task statuses and skill hours, then updates the rolling learning summary
5. Next `planner daily` sees updated state (including the evolved learning summary capturing all historical preferences and insights) and adapts

## Task Specificity Rule
The system prompt enforces hyper-specific tasks. Never "Complete 2 SSRF labs" — always exact lab titles, URLs, and rationale for why that specific resource.

## Agent Tools
Claude has two tools available during briefing generation:
- **`verify_url`** — GET request via httpx (follows redirects, 10s timeout). Extracts `<title>` tag from HTML and returns `page_title`. Claude must use the returned title as the task title — titles from its own memory are often outdated or wrong.
- **`search_learnings`** — SQLite LIKE query against completed task learnings and titles. Prevents assigning material the user has already studied.

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

## Config Validation
- `briefing_time` must be HH:MM format (e.g. `"07:00"`). Invalid formats like `"7am"` raise a Pydantic ValidationError at config load time.
- `max_tokens` defaults to 16384. Token usage is logged after every API call; a warning fires when output tokens exceed 80% of the limit.

## State (SQLite)
All state lives in `data/planner.db`:
- `skills` — skill tracks with phase, hours invested, items completed
- `tasks` — all assigned tasks with status, time estimates, learnings
- `achievements` — portfolio items (CVEs, papers, talks, etc.)
- `daily_briefings` — briefing history with tasks JSON and email message IDs
- `feedback_log` — all feedback received (email or CLI) with notes and learnings
- `meta` — key-value store (last briefing date, rolling learning summary, etc.)

## Error Handling
- `BriefingParseError` — raised when Claude's response cannot be parsed as valid briefing JSON. Caught in CLI, prints clear error, exits with code 1.
- Invalid task IDs in `complete` and `skip` commands print an error and exit with code 1.
- API failures trigger 3 retries with exponential backoff before raising.
- Briefing generation failures send a plain-text notification email with error details.

## Tests
- `tests/test_store.py` — 5 database roundtrip tests (task CRUD, status updates, skill hours, feedback notes, briefing dedup)
- `tests/test_loop.py` — 4 JSON parse tests (clean JSON, markdown-fenced, invalid input, empty input)
