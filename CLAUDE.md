# Planner Agent

## Project Overview
Multi-brain adaptive career planning agent for a 6-9 month security career sprint.
Five specialized AI brains operate at different time horizons — strategic (weekly), tactical (daily), analytical (per-feedback), critical (weekly review), and discovery (periodic).
All brains auto-coordinate through a single `planner daily` command.

## Tech Stack
- Python 3.12, managed with uv
- Claude API (anthropic SDK) — Opus for strategic planning, Sonnet for daily tasks + weekly reviews, Haiku for feedback parsing + analysis + opportunity scouting
- Resend API for outbound daily briefing emails
- IMAP (stdlib) for inbound feedback via email replies
- Click for CLI
- Pydantic for config validation and data models
- SQLite for all state persistence
- tenacity for API retry logic
- httpx for URL verification and web search provider calls
- python-dotenv for auto-loading .env

## Multi-Brain Architecture

```
DAILY CYCLE (auto-triggered by `planner daily`)
┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Analyst  │──▶│  Scout   │──▶│    Critic    │──▶│  Strategist  │──▶│  Tactician   │
│ Bootstrap │   │ (Haiku)  │   │  (Sonnet)    │   │   (Opus)     │   │  (Sonnet)    │
│ (Haiku)   │   │ if stale │   │ if new week  │   │ if no dir.   │   │   always     │
└──────────┘   └──────────┘   └──────────────┘   └──────────────┘   └──────────────┘
    once         every 3d       before strategist    weekly              daily
```

| Brain | Model | When | What It Does | Cost/Run |
|-------|-------|------|-------------|----------|
| **Strategist** | Opus | Weekly (auto) | Goal decomposition → milestones → weekly directive with time allocation + phase transitions | ~$0.16 |
| **Tactician** | Sonnet | Daily (auto) | Reads directive → researches via multi-source web search → generates hyper-specific daily tasks linked to milestones | ~$0.04 |
| **Analyst** | Haiku | After feedback | Structured competence assessment, learning velocity, engagement patterns | ~$0.003 |
| **Critic** | Sonnet | Weekly (auto, before Strategist) | Planned vs actual, trajectory scoring, honest review, recommendations | ~$0.03 |
| **Scout** | Haiku | Every 3 days (auto) | Searches the web for real CTFs, conference CFPs, bounty programs with deadlines | ~$0.01 |

**Estimated weekly cost: ~$0.50**

The Orchestrator auto-decides which brains to run based on DB state — no separate commands needed.

## Project Structure
- `src/planner_agent/` — main package (src layout)
- `src/planner_agent/agent/` — all brains and orchestrator
  - `orchestrator.py` — single entry point, auto-coordinates all brains
  - `base.py` — BaseBrain class with shared API call logic and cost tracking
  - `loop.py` — Tactician brain (daily tasks with agent loop + tools)
  - `strategist.py` — Strategist brain (weekly directive from Opus)
  - `critic.py` — Critic brain (weekly review)
  - `analyst.py` — Analyst brain (competence assessment)
  - `scout.py` — Scout brain (opportunity discovery via web search agent loop)
  - `tools.py` — verify_url, search_learnings, web_search (Brave Search API)
  - `prompts/` — prompt modules for each brain
    - `tactician.py` — daily task generation prompt + context builder
    - `strategist.py` — strategic planning prompt + context builder
    - `critic.py` — weekly review prompt + context builder
    - `analyst.py` — competence assessment prompt + context builder
    - `scout.py` — opportunity discovery prompt + context builder
    - `feedback.py` — feedback parsing prompt
- `src/planner_agent/email/` — Resend sender + IMAP receiver + HTML templates
- `src/planner_agent/state/` — SQLite state persistence + newsletter DB reader
- `src/planner_agent/models.py` — all Pydantic models (Task, Goal, Milestone, StrategicDirective, WeeklyReview, UserIntelligenceProfile, etc.)
- `src/planner_agent/config.py` — Pydantic config with brain settings
- `src/planner_agent/scheduling.py` — launchd/cron scheduling
- `AboutMe.md` — user profile (shared with Newsletter Agent)
- `config.yaml` — operational config including brain settings
- `tests/` — test suite (91 tests across 10 test files)

## Key Commands
```bash
uv run planner daily                    # full cycle: all brains auto-trigger → email
uv run planner daily --no-email         # generate briefing, print to terminal only
uv run planner daily --force            # regenerate even if briefing exists for today
uv run planner daily --date 2026-05-22  # generate briefing for a specific date
uv run planner process-replies          # parse email reply, confirm, update state + analyst
uv run planner process-replies --yes    # skip confirmation (for automation/cron)
uv run planner briefing                 # generate briefing without email
uv run planner briefing --force         # regenerate briefing
uv run planner complete <task_id>       # mark task done via CLI (triggers Analyst)
uv run planner skip <task_id>           # mark task skipped (triggers Analyst)
uv run planner status                   # goals, milestones, directive, skills, profile, API usage
uv run planner portfolio                # portfolio status and gaps
uv run planner log-achievement          # record a CVE, paper, talk, etc.
uv run planner init                     # initialize skill tracks from config
uv run planner history                  # show recent completed tasks
uv run planner install-schedule         # install daily launchd/cron job
uv run planner install-schedule --uninstall  # remove schedule
uv run pytest tests/                    # run tests (91 tests)
uv run ruff check src/                  # lint
```

## Architecture
- **Orchestrator**: Single entry point (`Orchestrator.run_daily()`) that auto-decides which brains to run based on DB state. Each brain checks its own preconditions. 20s pacing between brain API calls.
- **Strategic layer**: Strategist (Opus) produces a weekly StrategicDirective with per-track hour allocations, priority rankings, phase transitions, constraints, and alerts. The directive is binding — the Tactician must follow it.
- **Tactical layer**: Tactician (Sonnet) runs a strict 4-turn agent loop with `web_search`, `verify_url`, and `search_learnings` tools, generating hyper-specific daily tasks linked to milestones and the active directive. Max 6 iterations, 20s pacing between API calls.
- **Intelligence layer**: Analyst (Haiku) maintains a UserIntelligenceProfile with per-track competence assessments, learning velocity, engagement patterns, and phase readiness signals. Updated after every feedback event.
- **Accountability layer**: Critic (Sonnet) reviews planned vs actual each week — grades A-F, per-track trajectory, milestone confidence, strategic recommendations. Fed into the Strategist's next planning cycle.
- **Discovery layer**: Scout (Haiku) discovers time-sensitive opportunities via web search agent loop (CTFs, CFPs, bounty programs) every 3+ days, persisted to DB and surfaced to the Strategist.
- **Cost tracking**: Per-brain token usage (input/output/calls) accumulated in the meta table. Visible in `planner status`.
- **Goal-milestone-directive chain**: Goals → Milestones → StrategicDirective → Daily Tasks. Full traceability from career objectives to individual tasks.
- **Phase transitions**: learn → practice → produce, executed by directive decision, applied after briefing generation.
- **Newsletter integration**: Reads Newsletter Agent's SQLite DB (read-only). Articles rendered as a reading block (5-10 articles per briefing) in the briefing email.
- **Retry logic**: All API calls wrapped with tenacity (3 attempts, exponential backoff on APIStatusError)
- **JSON retry fallback**: If any brain outputs text instead of pure JSON, a one-shot retry extracts valid JSON
- **Dedup protection**: Same-day briefing runs blocked unless `--force` is passed
- **Fallback email**: If briefing generation fails, a plain-text notification email is sent
- **No frameworks**: Raw Anthropic SDK + Pydantic + SQLite. The intelligence is in the prompts.

## Agent Tools

### Tactician Tools (agent loop, 4-turn budget)
- **`web_search`** — Multi-source search via Brave, Tavily, and Exa APIs in parallel. Results are deduplicated by URL across all sources. Searches for specific resources on any platform (PentesterLab, HackTheBox, TryHackMe, PortSwigger, picoCTF, HackerOne, etc.). The Tactician MUST batch all searches in a single turn.
- **`verify_url`** — GET request via httpx (follows redirects, 10s timeout). Extracts `<title>` tag from HTML and returns `page_title`. Claude must use the returned title as the task title. All URLs verified in a single turn.
- **`search_learnings`** — SQLite LIKE query against completed task learnings, titles, descriptions, and resource URLs. Prevents assigning material the user has already studied. All queries batched in a single turn.

### Scout Tools (agent loop, 3-turn budget)
- **`web_search`** — Same multi-source search as Tactician, used to find real upcoming CTFs, conference CFPs, bug bounty programs, and training events.
- **`verify_url`** — Verifies discovered opportunity URLs are live.

## Pydantic Model Resilience
All models are bulletproofed for LLM output variations:
- `PhaseTransition`: normalizes `from`/`to` → `from_phase`/`to_phase` via model_validator
- `StrategicAlert`: normalizes `action` → `action_required`, all fields default
- `WeeklyTarget`: filters invalid task types, coerces milestone_ids and priority_rank to int
- `MilestoneTarget`: coerces milestone_id string to int
- `OpportunityAction`: all fields optional with defaults
- `StrategicDirective`: coerces string lists to objects for alerts, milestone_targets, opportunity_actions, filters non-dict phase_transitions
- Task parsing in Tactician: try/except for TaskType, Phase, Priority enum construction with fallbacks

## Newsletter Integration
- `state/newsletter.py` — NewsletterReader reads Newsletter Agent's SQLite DB (read-only, `?mode=ro`)
- Newsletter articles appear in a separate `newsletter_reading` block in Claude's JSON output
- Converted to a real Task on persist so it's trackable via feedback
- Articles already completed (matched by URL) are excluded
- Claude includes 5-10 articles per briefing (CRITICAL + IMPORTANT + relevant INTERESTING)
- Per-priority limits: CRITICAL=15, IMPORTANT=20, INTERESTING=15, REFERENCE=10
- Each Newsletter Agent run costs $5-6 — Planner never runs it, only suggests when needed
- Graceful degradation: if newsletter DB missing/unreadable, briefing generates normally

## Adaptive Loop
1. `planner daily` triggers the Orchestrator, which auto-runs all needed brains
2. Scout discovers opportunities (if stale). Analyst bootstraps (if first run). Critic reviews last week (if new week). Strategist plans (if no directive). Tactician generates tasks (always).
3. User receives email with directive banner, tasks linked to milestones, newsletter reading
4. User completes tasks at their own pace (1-5+ days)
5. User replies to briefing email with natural language progress update
6. `planner process-replies` parses reply → updates tasks → triggers Analyst profile update
7. Next `planner daily` sees updated state and all brains adapt accordingly

## Async Workflow
The planner is designed for flexible, user-driven pacing — not daily cron:
- **No auto-expiry**: pending tasks stay pending indefinitely until completed or skipped
- **Count-based context**: completion stats, recent tasks, skip patterns, and feedback notes are all retrieved by count (last N items), not by time window
- **No forced cadence**: same-day dedup prevents accidental double-runs, but any multi-day gap is fine

## Learning Loop
Every skill follows: Learn → Practice → Produce. Phase transitions are decided by the Strategist based on the Analyst's competence assessment and Critic's trajectory analysis — not arbitrary item counts.

## Task Specificity Rule
The system prompt enforces hyper-specific tasks. Never "Complete 2 SSRF labs" — always exact lab titles, URLs, and rationale for why that specific resource. Resources discovered from ANY platform via web search, not limited to a fixed list.

## Environment Variables
- `ANTHROPIC_API_KEY` — required for Claude API
- `RESEND_API_KEY` — required for sending briefing emails
- `BRAVE_API_KEY` — web search provider (Brave Search API)
- `TAVILY_API_KEY` — web search provider (Tavily, advanced depth)
- `EXA_API_KEY` — web search provider (Exa, neural/semantic search)
- `IMAP_SERVER` — IMAP server for receiving replies (default: imap.gmail.com)
- `IMAP_EMAIL` — email address for IMAP login
- `IMAP_PASSWORD` — app password for IMAP login

## Config
- `config.yaml` — all operational settings including brain enable/disable and model overrides
- `briefing_time` must be HH:MM format (e.g. `"07:00"`)
- `max_tokens` defaults to 16384
- `brains` section controls each brain's `enabled`, `auto_trigger`, and `model_override`
- Scout `auto_trigger` defaults to false — set true in config.yaml to enable periodic discovery
- `search` section controls web search providers (brave, tavily, exa) with enable/disable per provider

## State (SQLite)
All state lives in `data/planner.db` (auto-migrated on startup):
- `skills` — skill tracks with phase, hours invested, competence level
- `tasks` — all assigned tasks with status, milestone_id, directive_id
- `goals` — top-level strategic objectives with deadlines
- `milestones` — intermediate targets linked to goals with dependency chains
- `strategic_directives` — weekly plans from the Strategist
- `weekly_reviews` — Critic's assessments
- `competence_log` — per-skill competence assessments over time
- `opportunities` — time-sensitive external opportunities from Scout
- `achievements` — portfolio items (CVEs, papers, talks, etc.)
- `daily_briefings` — briefing history with directive_id linkage
- `feedback_log` — all feedback received (email or CLI) with notes and learnings
- `meta` — key-value store (learning summary, intelligence profile, token usage, scout_last_run, etc.)

## Error Handling
- `BriefingParseError` — raised when any brain's response cannot be parsed as valid JSON. Caught in CLI, prints clear error, exits with code 1.
- JSON retry fallback — if parsing fails, a one-shot retry with a "JSON formatter" system prompt extracts valid JSON
- Invalid task IDs in `complete` and `skip` commands print an error and exit with code 1.
- API failures trigger 3 retries with exponential backoff before raising.
- Briefing generation failures send a plain-text notification email with error details.

## Tests
- `tests/test_store.py` — 5 database roundtrip tests
- `tests/test_loop.py` — 4 JSON parse tests
- `tests/test_migration.py` — 13 schema migration and CRUD tests
- `tests/test_analyst.py` — 5 Analyst brain tests
- `tests/test_strategist.py` — 8 Strategist + Orchestrator tests
- `tests/test_phase3.py` — 14 directive-aware Tactician + email template tests
- `tests/test_critic.py` — 14 Critic brain tests
- `tests/test_scout.py` — 13 Scout brain tests
- `tests/test_integration.py` — 3 end-to-end integration tests (full daily cycle, bootstrap, cost tracking)
- `tests/test_web_search.py` — 12 multi-source web search tests (Brave, Tavily, Exa, dedup, partial failure)
