# Planner Agent

Adaptive daily task orchestrator for security career growth. Generates hyper-specific daily tasks using Claude, sends HTML briefings via email, receives natural-language feedback via email replies, and adapts future plans based on your progress.

## How It Works

```
planner daily → Claude generates tasks → HTML email sent
                                              ↓
                                     You reply with progress
                                              ↓
planner process-replies → Parses feedback → Updates DB state
                                              ↓
                              Next planner daily sees updated state
                                     and adapts accordingly
```

1. **Briefing generation**: Reads your full state (skills, completed tasks, skipped patterns, portfolio gaps, newsletter articles) and sends it to Claude, which generates hyper-specific tasks with exact resources, URLs, and rationale.
2. **Email delivery**: Renders tasks as a styled HTML email with priority-colored task cards, a newsletter reading block, portfolio gap alerts, and skill observations.
3. **Feedback loop**: You reply to the email naturally ("Done 1 and 3. Skipped 2 — too long."). Run `planner process-replies` to parse your reply and update task statuses, hours, and learnings in the DB.
4. **Adaptation**: The next briefing sees your accumulated progress — hours invested per track, completion patterns, skip patterns, learnings noted — and adjusts difficulty, focus, and task types accordingly.

## Skill Progression

Every skill track follows a three-phase loop:

- **Learn**: Papers, articles, videos, courses — building foundational knowledge
- **Practice**: Labs, CTFs, bug bounty, code review — applying knowledge hands-on
- **Produce**: CVEs, research papers, conference talks, tools — creating portfolio evidence

Phase transitions are Claude's judgment call based on hours invested, breadth of topics covered, quality of learnings, and completion consistency.

## Newsletter Integration

Reads articles from the [Newsletter Agent](https://github.com/deev-pal08/newsletter-agent)'s SQLite DB (read-only). Newsletter articles appear as a single reading block at the end of the briefing, separate from the main tasks. Articles you've already completed (matched by URL) are automatically excluded.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
git clone https://github.com/deev-pal08/Planner-Agent.git
cd Planner-Agent
uv sync
```

### Configure

1. Copy and fill in environment variables:

```bash
cp .env.example .env
# Fill in:
#   ANTHROPIC_API_KEY
#   RESEND_API_KEY
#   IMAP_EMAIL
#   IMAP_PASSWORD (Gmail app password)
```

2. Edit `config.yaml` for email addresses, schedule, time budget, and skill tracks.

3. Edit `AboutMe.md` with your profile, goals, and skill self-assessment.

4. Initialize skill tracks:

```bash
uv run planner init
```

## Commands

```bash
uv run planner daily                    # Generate briefing + send email
uv run planner daily --no-email         # Generate briefing, print to terminal only
uv run planner process-replies          # Parse latest email reply, update task state
uv run planner briefing                 # Generate briefing (no email, no reply processing)
uv run planner complete <task_id>       # Mark task done via CLI
uv run planner skip <task_id>           # Mark task skipped via CLI
uv run planner status                   # Show progress across all tracks
uv run planner portfolio                # Show portfolio status and gaps
uv run planner log-achievement          # Record a CVE, paper, talk, etc.
uv run planner init                     # Initialize skill tracks from config
uv run planner history                  # Show recent completed tasks
uv run planner install-schedule         # Install daily launchd/cron job
uv run planner install-schedule --uninstall
```

## Tech Stack

- **Claude Sonnet** for briefing generation, **Claude Haiku** for feedback parsing
- **Resend** for outbound HTML emails
- **IMAP** (stdlib) for inbound email reply polling
- **SQLite** for all state persistence
- **Click** CLI, **Pydantic** models, **python-dotenv**

## Project Structure

```
src/planner_agent/
  agent/
    loop.py          # Claude API agent — briefing generation + feedback parsing
    prompts.py       # System prompt + briefing context builder
  email/
    sender.py        # Resend API email sender
    receiver.py      # IMAP reply polling
    templates.py     # HTML email template rendering
  state/
    store.py         # SQLite state manager
    newsletter.py    # Read-only Newsletter Agent DB reader
  models.py          # Pydantic models (Task, Skill, Achievement, etc.)
  config.py          # Config validation
  cli.py             # Click CLI
  scheduling.py      # launchd/cron scheduling
config.yaml          # Operational config
AboutMe.md           # User profile shared with agent
data/planner.db      # SQLite database (auto-created)
```

## Database Tables

| Table | Purpose |
|---|---|
| `skills` | Skill tracks with phase, hours invested, items completed |
| `tasks` | All assigned tasks with status, time estimates, learnings |
| `achievements` | Portfolio items (CVEs, papers, talks, etc.) |
| `daily_briefings` | Briefing history with tasks JSON and email message IDs |
| `feedback_log` | All feedback received (email or CLI) |
| `meta` | Key-value metadata (last briefing date, etc.) |
