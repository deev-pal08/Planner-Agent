# Planner Agent

Adaptive daily task orchestrator for security career growth. Reads your current skill state, generates hyper-specific daily tasks using a Claude agent loop with tool use, delivers styled HTML briefings via email, parses natural-language feedback from your replies, and adapts future plans based on accumulated progress.

## How It Works

1. **Reads your state** from SQLite — skill tracks, completed tasks, skip patterns, feedback notes, portfolio gaps, newsletter articles
2. **Generates** hyper-specific daily tasks via a Claude Sonnet agent loop — verifies every resource URL is live, searches your past learnings to avoid repeats, names exact lab titles, paper URLs, challenge names, and rationale for each task
3. **Delivers** a styled HTML briefing email via Resend with priority-colored task cards, newsletter reading block, portfolio gap alerts, and skill observations
4. **Receives feedback** via email reply — you reply naturally ("Done 1 and 3. Skipped 2 — too dense. Spent 3h total.")
5. **Parses feedback** via Claude Haiku into structured task updates, shows parsed results for confirmation before writing to the database
6. **Adapts** — the next briefing sees your accumulated progress, feedback notes, and learnings, then adjusts difficulty, focus track, task types, and phase progression accordingly

```
planner daily → Claude agent loop → verifies URLs → searches learnings
                    → generates tasks → HTML email sent
                                                        ↓
                                               You reply with progress
                                                        ↓
planner process-replies → Claude Haiku parses reply → shows parsed feedback
                    → you confirm → updates DB (tasks, skills, hours)
                                                        ↓
                                        Next planner daily sees updated state
                                             and adapts accordingly
```

## Skill Progression

Every skill track follows a three-phase learning loop:

| Phase | What you do | Examples |
|-------|-------------|---------|
| **Learn** | Papers, articles, videos, courses | Read Greshake et al. prompt injection paper, watch LiveOverflow talk |
| **Practice** | Labs, CTFs, bug bounty, code review | Complete PentesterLab SSRF exercise, solve HackTheBox machine |
| **Produce** | CVEs, research papers, talks, tools | Disclose a CVE, submit a conference CFP, publish a security tool |

Phase transitions are Claude's judgment call based on hours invested, breadth of topics covered, quality of learnings noted, and completion consistency — not a fixed item count.

## Agent Loop and Tools

Unlike a simple prompt-and-respond setup, the briefing generator runs as a multi-turn agent loop with two tools:

| Tool | Purpose | How it works |
|------|---------|--------------|
| `verify_url` | Checks if a resource URL is live | HEAD request via httpx, follows redirects, 5s timeout |
| `search_learnings` | Searches your past task learnings | SQLite LIKE query against completed task titles and learnings |

Claude calls `search_learnings` before assigning tasks to check what you've already studied, and calls `verify_url` on every resource URL before including it in a task. Dead links are replaced with alternatives. The loop runs up to 10 iterations before extracting the final JSON output.

## Newsletter Integration

Reads articles from the [Newsletter Agent](https://github.com/deev-pal08/newsletter-agent)'s SQLite database (read-only, `?mode=ro`). Newsletter articles appear as a single reading block at the end of the briefing, separate from Claude's generated tasks. Articles you've already completed (matched by URL against done tasks) are automatically excluded.

- Graceful degradation: if the newsletter DB is missing or unreadable, the briefing generates normally
- Each Newsletter Agent run costs ~$5-6 — the Planner never runs it, only suggests topic searches when coverage gaps exist
- Articles are grouped by priority (CRITICAL, IMPORTANT, INTERESTING, REFERENCE) with configurable caps

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [Anthropic API key](https://console.anthropic.com/) for task generation and feedback parsing
- [Resend API key](https://resend.com/) for email delivery (free tier: 100 emails/day)
- Gmail account with [App Password](https://support.google.com/accounts/answer/185833) for IMAP reply polling

## Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repo
git clone https://github.com/deev-pal08/Planner-Agent.git
cd Planner-Agent

# 3. Install dependencies
uv sync

# 4. Set up your profile
cp AboutMe.example.md AboutMe.md
# Edit AboutMe.md — your skills, experience, goals, and honest self-assessment

# 5. Set up your config
cp config.example.yaml config.yaml
# Edit config.yaml — email addresses, time budget, skill tracks

# 6. Set up API keys
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, RESEND_API_KEY, IMAP_EMAIL, IMAP_PASSWORD

# 7. Initialize skill tracks
uv run planner init

# 8. Preview your first briefing
uv run planner daily --no-email

# 9. Send for real
uv run planner daily

# 10. Reply to the email with your progress, then:
uv run planner process-replies

# 11. (Optional) Install daily schedule
uv run planner install-schedule --time 07:00
```

## Commands

| Command | Description |
|---------|-------------|
| `planner daily` | Generate briefing + send email |
| `planner daily --no-email` | Generate briefing, print to terminal only |
| `planner daily --force` | Regenerate even if a briefing already exists for today |
| `planner daily --date 2026-05-22` | Generate briefing for a specific date |
| `planner process-replies` | Parse latest email reply, show feedback, confirm, update state |
| `planner process-replies --yes` | Skip confirmation prompt (for automation/cron) |
| `planner briefing` | Generate briefing (no email) |
| `planner briefing --force` | Regenerate briefing for today |
| `planner complete <task_id>` | Mark task done via CLI |
| `planner skip <task_id>` | Mark task skipped via CLI |
| `planner status` | Show progress across all tracks |
| `planner portfolio` | Show portfolio status and gaps |
| `planner log-achievement` | Record a CVE, paper, talk, etc. |
| `planner init` | Initialize skill tracks from config |
| `planner history` | Show recent completed tasks |
| `planner install-schedule` | Install daily launchd/cron job |
| `planner install-schedule --uninstall` | Remove installed schedule |

All commands are prefixed with `uv run` (e.g., `uv run planner daily`).

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

- **about_me**: Path to your `AboutMe.md` profile
- **llm.model**: `claude-haiku-4-5` for feedback parsing (cheap, fast)
- **llm.research_model**: `claude-sonnet-4-6` for briefing generation (smarter)
- **llm.max_tokens**: Output token limit for briefing generation (default: 8192)
- **email**: Resend delivery settings (from/to addresses)
- **imap**: Gmail IMAP settings for reply polling
- **schedule**: Daily briefing time (must be HH:MM format) and timezone
- **time_budget**: Available hours per weekday/weekend
- **newsletter**: Newsletter Agent project directory and stale threshold
- **tracks**: Skill tracks with name, starting phase, and priority

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API for briefing generation and feedback parsing |
| `RESEND_API_KEY` | Yes | Resend API for email delivery |
| `IMAP_EMAIL` | Yes | Gmail address for IMAP reply polling |
| `IMAP_PASSWORD` | Yes | Gmail App Password for IMAP login |
| `IMAP_SERVER` | No | IMAP server (default: `imap.gmail.com`) |

All keys are stored in `.env` (gitignored) and auto-loaded via python-dotenv.

## User Profile (AboutMe.md)

The `AboutMe.md` file tells the agent who you are. It's injected into Claude's briefing prompt so tasks are personalized to your background:

- **Who I Am** — role, company, career level
- **Skills & Expertise** — current abilities with honest ratings
- **Experience** — professional background, notable achievements
- **Learning Goals** — what you're working toward (promotion, visa, certifications)
- **Skill Tracks** — specific domains to develop, with current phase and priority

## Adaptive Feedback Loop

The agent adapts through accumulated state, not hardcoded rules:

| Signal | What Claude sees | How it adapts |
|--------|-----------------|---------------|
| Hours invested per track | `ai_security: 12.5h, web_appsec: 3.0h` | Balances focus across tracks |
| Completion rate | `18/22 tasks done (82%)` | Adjusts task count and difficulty |
| Skip patterns | `web_appsec/lab skipped 4 times` | Flags the pattern, may switch resource types |
| Learnings noted | `"TOCTOU races need two operations on same resource"` | Gauges comprehension depth |
| Feedback notes | `"SSRF lab too basic, already know cloud metadata"` | Avoids repeating rejected material |
| Portfolio gaps | `0 research papers, 0 CVEs` | Prioritizes tracks that close gaps |
| Past learnings (via tool) | `search_learnings("JWT")` → prior work found | Assigns advanced material, not basics |
| Newsletter coverage | `13 unread articles, 0 on AI security` | Suggests newsletter agent searches for missing topics |

## Task Specificity Rule

Every generated task must be specific enough to start immediately. The system prompt enforces this:

**Unacceptable:**
- "Complete 2 SSRF labs on PentesterLab"
- "Read articles about prompt injection"

**Required:**
- "Complete PentesterLab exercise 'Server Side Request Forgery' (https://pentesterlab.com/exercises/server_side_request_forgery) — covers cloud metadata endpoint exploitation. This builds on last week's basic SSRF module."
- "Read 'Not what you've signed up for' by Greshake et al. (https://arxiv.org/abs/2302.12173) — foundational prompt injection paper. Focus on Section 3: indirect prompt injection threat model."

Every URL is verified live via the `verify_url` tool before being included in a task.

## Project Structure

```
src/planner_agent/
├── cli.py               # Click CLI — all commands
├── config.py            # Pydantic config validation with field validators
├── models.py            # Pydantic models (Task, Skill, Achievement, NewsletterReading)
├── scheduling.py        # launchd/cron scheduling
├── agent/
│   ├── loop.py          # Claude API agent loop — tools, retry, token logging
│   └── prompts.py       # System prompt + context builder (with feedback notes)
├── email/
│   ├── sender.py        # Resend API email sender (briefing + plain-text fallback)
│   ├── receiver.py      # IMAP reply polling (dynamic lookback)
│   └── templates.py     # HTML email template rendering
└── state/
    ├── store.py         # SQLite state manager
    └── newsletter.py    # Read-only Newsletter Agent DB reader
```

## Database Schema

All state lives in `data/planner.db` (SQLite, WAL mode):

| Table | Purpose |
|-------|---------|
| `skills` | Skill tracks with phase, priority, hours invested, items completed |
| `tasks` | All assigned tasks with status, time estimates, resource URLs, learnings |
| `achievements` | Portfolio items — CVEs, papers, talks, Hall of Fames, etc. |
| `daily_briefings` | Briefing history with full tasks JSON and email message IDs |
| `feedback_log` | All feedback received (email or CLI) with notes and learnings |
| `meta` | Key-value metadata (last briefing date, etc.) |

## Architecture

- **Agent loop with tools**: Claude Sonnet runs a multi-turn loop (up to 10 iterations) with `verify_url` and `search_learnings` tools. URLs are verified live; past learnings are searched to avoid repeating material.
- **Two models**: Claude Sonnet for briefing generation (needs reasoning + tool use), Claude Haiku for feedback parsing (cheap, fast)
- **Retry logic**: All API calls wrapped with tenacity — 3 attempts with exponential backoff on transient errors
- **Token logging**: Input/output token counts logged after every API call; warning when output tokens exceed 80% of `max_tokens`
- **Dedup protection**: Same-day briefing runs blocked unless `--force` passed; stale pending tasks cleaned on force
- **Feedback confirmation**: `process-replies` shows parsed feedback and prompts for confirmation before writing to DB; `--yes` bypasses for automation
- **Fallback email**: If briefing generation fails, a plain-text notification email is sent with error details and last known state
- **Separation of concerns**: Agent generates tasks → Templates render HTML → Sender delivers → Receiver polls → Agent parses feedback → Store persists state
- **Newsletter integration**: Read-only access to a separate project's SQLite DB. Newsletter articles are rendered as a single reading block (last task) and persisted as a real Task so the feedback loop tracks them.
- **Graceful degradation**: Missing newsletter DB, IMAP failures, and email send errors don't block briefing generation
- **No frameworks**: Raw Anthropic SDK + Pydantic + SQLite. The intelligence is in the prompts.

## Scheduling

Install a daily schedule with one command:

| OS | Method |
|----|--------|
| macOS | LaunchAgent (plist) via `launchctl` |
| Linux | crontab |

```bash
uv run planner install-schedule --time 07:00
uv run planner install-schedule --uninstall
```

## Cost

| Service | Per run | Notes |
|---------|---------|-------|
| Claude Sonnet (briefing) | ~$0.03-0.05 | Agent loop with tool calls (typically 3-4 API turns) |
| Claude Haiku (feedback) | ~$0.001 | 1 API call per reply parsed |

Total: ~$0.03-0.05 per daily run.

## Tests

```bash
uv run pytest tests/ -v
```

| Test file | Tests | What it covers |
|-----------|-------|----------------|
| `tests/test_store.py` | 5 | Task CRUD, status updates, skill hour accumulation, feedback notes retrieval, briefing dedup |
| `tests/test_loop.py` | 4 | JSON parsing (clean, markdown-fenced, invalid input, empty input) |

## License

MIT
