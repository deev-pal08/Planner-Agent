# Planner Agent

Multi-brain adaptive career planning agent for security career growth. Five specialized AI brains operate at different time horizons — strategic (weekly), tactical (daily), analytical (per-feedback), critical (weekly review), and discovery (periodic). All brains auto-coordinate through a single command.

## How It Works

```
planner daily → Orchestrator auto-runs needed brains:

┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Analyst  │──▶│  Scout   │──▶│    Critic    │──▶│  Strategist  │──▶│  Tactician   │
│ Bootstrap │   │ (Haiku)  │   │  (Sonnet)    │   │   (Opus)     │   │  (Sonnet)    │
│ (Haiku)   │   │ if stale │   │ if new week  │   │ if no dir.   │   │   always     │
└──────────┘   └──────────┘   └──────────────┘   └──────────────┘   └──────────────┘
    once         every 3d       before strategist    weekly              daily

                                                                          │
                                                                    HTML email sent
                                                                          │
                                                                You reply with progress
                                                                          │
                                                              planner process-replies
                                                                          │
                                                            Analyst updates profile
                                                                          │
                                                          Next run sees updated state
                                                              and all brains adapt
```

## The Five Brains

| Brain | Model | When | What It Does |
|-------|-------|------|-------------|
| **Strategist** | Opus | Weekly | Reads goals, milestones, Critic review, opportunities → produces a binding weekly directive with per-track hour allocations, phase transitions, and constraints |
| **Tactician** | Sonnet | Daily | Reads directive → searches the web for specific resources → generates hyper-specific daily tasks linked to milestones |
| **Critic** | Sonnet | Weekly | Reviews planned vs actual — grades A-F, per-track trajectory, milestone confidence, strategic recommendations |
| **Analyst** | Haiku | After feedback | Maintains structured competence profile — per-track skill levels, learning velocity, engagement patterns, phase readiness |
| **Scout** | Haiku | Every 3 days | Searches the web for real upcoming CTFs, conference CFPs, bug bounty programs, training events with deadlines |

## Research-First Task Generation

The Tactician doesn't rely on training data for resource names or URLs. It runs a strict 4-turn agent loop:

1. **search_learnings** — checks what you've already studied (prevents repeats)
2. **web_search** — multi-source search via Brave, Tavily, and Exa APIs in parallel, finds specific resources from any platform
3. **verify_url** — verifies every URL is live, extracts actual page title
4. **Output JSON** — composes the final task list with verified resources

Tasks come from any platform — PentesterLab, HackTheBox, TryHackMe, PortSwigger, picoCTF, CryptoHack, HackerOne, Bugcrowd, GitHub repos, arxiv papers, conference workshops, and anything else the search discovers.

## Task Specificity

Every task is specific enough to start immediately:

**Unacceptable:**
- "Complete 2 SSRF labs on PentesterLab"
- "Read articles about prompt injection"

**Required:**
- "Complete PentesterLab exercise 'Server Side Request Forgery' (https://pentesterlab.com/exercises/server_side_request_forgery) — covers cloud metadata endpoint exploitation. This builds on last week's basic SSRF module."
- "Solve picoCTF challenge 'Web Gauntlet 3' (300 points, Web Exploitation) — SQLi filter bypass challenge. Practice crafting payloads that evade WAF rules."
- "Start bug bounty on HackerOne program 'Acronis' — focus on IDOR in their cloud management API endpoints."

## Skill Progression — The 4-Phase Mastery Loop

Every skill track follows a strict 4-phase learning loop. Each phase has a mastery gate — no phase is ever skipped. This loop is built on a proven methodology that produced $4k in 3 months from bug bounty.

| Phase | What you do | Examples |
|-------|-------------|---------|
| **Learn** | Drain ALL foundational sources until the topic is internalized | HackTricks, PortSwigger Web Security Academy, OWASP guides, official docs, YouTube tutorials, cheat sheets, courses |
| **Examples** | Read extensive real-world reports — see how attacks manifest in production | HackerOne Hacktivity, bug bounty writeups, CVE analyses, Medium security articles, disclosed bug reports, conference case studies |
| **Practice** | Hands-on exercises — build muscle memory | PentesterLab, HackTheBox, TryHackMe, PortSwigger labs, picoCTF, CryptoHack, OverTheWire, OWASP WebGoat |
| **Execute** | Apply skills on real targets — produce portfolio items | Bug bounty hunting (HackerOne, Bugcrowd), real code audits, CVE advisories, security tools, research papers, conference talks |

**Depth over breadth.** Master one topic through all 4 phases rather than spreading thin across many topics in the learn phase. Read 100s of articles on a single topic before advancing.

Phase transitions are decided by the Strategist based on the Analyst's competence assessment and Critic's trajectory analysis — not arbitrary item counts.

## Goal → Task Traceability

```
Goals (6-9 month objectives)
  └── Milestones (intermediate targets with deadlines)
        └── Strategic Directive (weekly plan with hour allocations)
              └── Daily Tasks (specific, verified, linked to milestones)
```

## Newsletter Integration

Reads articles from the [Newsletter Agent](https://github.com/deev-pal08/newsletter-agent)'s SQLite database (read-only). Newsletter articles appear as a reading block (5-10 articles per briefing) at the end of each email. Articles you've already completed are automatically excluded.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [Anthropic API key](https://console.anthropic.com/) for all brains
- [Resend API key](https://resend.com/) for email delivery
- [Brave Search API key](https://brave.com/search/api/) for web search
- [Tavily API key](https://tavily.com/) for web search (optional)
- [Exa API key](https://exa.ai/) for web search (optional)
- Gmail account with [App Password](https://support.google.com/accounts/answer/185833) for IMAP reply polling

## Quick Start

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/deev-pal08/Planner-Agent.git
cd Planner-Agent
uv sync

# 3. Configure
cp AboutMe.example.md AboutMe.md    # Edit with your profile
cp config.example.yaml config.yaml  # Edit email, time budget, tracks
cp .env.example .env                # Fill in API keys

# 4. Initialize and run
uv run planner init                 # Set up skill tracks
uv run planner daily --no-email     # Preview first briefing
uv run planner daily                # Send for real

# 5. Feedback loop
uv run planner process-replies      # Parse email reply, update state
```

## Commands

| Command | Description |
|---------|-------------|
| `planner daily` | Full cycle: all brains auto-trigger → email |
| `planner daily --no-email` | Generate briefing, print to terminal only |
| `planner daily --force` | Regenerate even if briefing exists for today |
| `planner process-replies` | Parse email reply, confirm, update state + analyst |
| `planner process-replies --yes` | Skip confirmation (for automation/cron) |
| `planner complete <id>` | Mark task done via CLI (triggers Analyst) |
| `planner skip <id>` | Mark task skipped (triggers Analyst) |
| `planner status` | Goals, milestones, directive, skills, profile, API usage |
| `planner portfolio` | Portfolio status and gaps |
| `planner log-achievement` | Record a CVE, paper, talk, etc. |
| `planner history` | Show recent completed tasks |
| `planner install-schedule` | Install daily launchd/cron job |

All commands are prefixed with `uv run`.

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

- **llm.model**: `claude-haiku-4-5` for feedback parsing, analyst, scout
- **llm.research_model**: `claude-sonnet-4-6` for tactician and critic
- **llm.strategic_model**: `claude-opus-4-8` for strategist
- **email**: Resend delivery settings (from/to addresses)
- **imap**: Gmail IMAP settings for reply polling
- **time_budget**: Available hours per weekday/weekend
- **brains**: Enable/disable each brain, model overrides
- **search**: Web search providers (brave, tavily, exa) with per-provider enable/disable
- **newsletter**: Newsletter Agent project directory

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API for all brains |
| `RESEND_API_KEY` | Yes | Resend API for email delivery |
| `BRAVE_API_KEY` | Yes | Brave Search API for web search |
| `TAVILY_API_KEY` | No | Tavily API for web search (optional, adds depth) |
| `EXA_API_KEY` | No | Exa API for neural/semantic search (optional) |
| `IMAP_EMAIL` | Yes | Gmail address for IMAP reply polling |
| `IMAP_PASSWORD` | Yes | Gmail App Password for IMAP login |

All keys are stored in `.env` (gitignored) and auto-loaded via python-dotenv.

## Project Structure

```
src/planner_agent/
├── cli.py               # Click CLI — all commands
├── config.py            # Pydantic config with brain settings
├── models.py            # All Pydantic models (resilient to LLM output variations)
├── scheduling.py        # launchd/cron scheduling
├── agent/
│   ├── orchestrator.py  # Single entry point, auto-coordinates all brains
│   ├── base.py          # BaseBrain — shared API call logic, retry, cost tracking
│   ├── loop.py          # Tactician — agent loop with web search + tools
│   ├── strategist.py    # Strategist — weekly directive from Opus
│   ├── critic.py        # Critic — weekly review
│   ├── analyst.py       # Analyst — competence assessment
│   ├── scout.py         # Scout — opportunity discovery via web search
│   ├── tools.py         # Shared tool implementations
│   └── prompts/         # Prompt modules for each brain
├── email/
│   ├── sender.py        # Resend sender (briefing + fallback)
│   ├── receiver.py      # IMAP reply polling
│   └── templates.py     # HTML email templates
└── state/
    ├── store.py         # SQLite state manager (auto-migration)
    └── newsletter.py    # Read-only Newsletter Agent DB reader
```

## Cost

| Brain | Per run | Notes |
|-------|---------|-------|
| Strategist (Opus) | ~$0.16 | 1 call/week |
| Tactician (Sonnet) | ~$0.04 | 4-turn agent loop/day |
| Critic (Sonnet) | ~$0.03 | 1 call/week |
| Scout (Haiku) | ~$0.01 | 3-turn agent loop every 3 days |
| Analyst (Haiku) | ~$0.003 | 1 call per feedback event |
| Feedback parsing (Haiku) | ~$0.001 | 1 call per reply |

**Estimated weekly cost: ~$0.50**

## Tests

```bash
uv run pytest tests/ -v
```

91 tests across 10 test files covering all brains, database operations, schema migration, web search, email templates, and end-to-end integration.

## License

MIT
