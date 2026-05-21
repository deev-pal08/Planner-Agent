"""CLI interface for the Planner Agent."""

from __future__ import annotations

import json
import logging
import sys

import click
from dotenv import load_dotenv

from planner_agent.config import load_config

load_dotenv()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--config", "-c", default="config.yaml", help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, config: str, verbose: bool) -> None:
    """Planner Agent — Adaptive Daily Task Orchestrator"""
    ctx.ensure_object(dict)
    _setup_logging(verbose)
    ctx.obj["config"] = load_config(config)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--date", "-d", default=None, help="Generate briefing for a specific date (YYYY-MM-DD)")
@click.option("--no-email", is_flag=True, help="Print briefing to terminal, don't send email")
@click.pass_context
def daily(ctx: click.Context, date: str | None, no_email: bool) -> None:
    """Full daily cycle: process email replies, generate briefing, send email."""
    config = ctx.obj["config"]

    from planner_agent.agent.loop import PlannerAgent
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    agent = PlannerAgent(config, state)

    # Step 1: Process any email replies from yesterday
    if config.imap.enabled and not no_email:
        replies_processed = _process_replies_impl(config, state, agent)
        if replies_processed > 0:
            click.echo(f"Processed {replies_processed} email replies.\n")

    # Step 2: Generate today's briefing
    click.echo("Generating daily briefing...")
    briefing = agent.generate_briefing(target_date=date)

    # Step 3: Print briefing to terminal
    _print_briefing(briefing)

    # Step 4: Send email
    if not no_email and config.email.enabled and config.email.to_addresses:
        try:
            from planner_agent.email.sender import EmailSender

            sender = EmailSender(
                api_key=config.email.api_key,
                from_address=config.email.from_address,
                to_addresses=config.email.to_addresses,
            )
            message_id = sender.send_briefing(briefing)

            last_briefing = state.get_last_briefing()
            if last_briefing:
                state.update_briefing_email(last_briefing["id"], message_id)

            click.echo(f"\nBriefing email sent to {', '.join(config.email.to_addresses)}")
        except Exception as e:
            click.echo(click.style(f"\nEmail send failed: {e}", fg="red"))
    elif no_email:
        click.echo("\n(--no-email: email not sent)")


@cli.command()
@click.option("--date", "-d", default=None, help="Generate for a specific date")
@click.pass_context
def briefing(ctx: click.Context, date: str | None) -> None:
    """Generate and display daily briefing (no email)."""
    config = ctx.obj["config"]

    from planner_agent.agent.loop import PlannerAgent
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    agent = PlannerAgent(config, state)

    click.echo("Generating daily briefing...")
    b = agent.generate_briefing(target_date=date)
    _print_briefing(b)


@cli.command(name="process-replies")
@click.pass_context
def process_replies(ctx: click.Context) -> None:
    """Poll inbox for email replies and update task statuses."""
    config = ctx.obj["config"]

    from planner_agent.agent.loop import PlannerAgent
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    agent = PlannerAgent(config, state)

    count = _process_replies_impl(config, state, agent)
    if count > 0:
        click.echo(f"Processed {count} task updates from email replies.")
    else:
        click.echo("No email replies found.")


@cli.command()
@click.argument("task_id", type=int)
@click.option("--hours", "-h", type=float, default=None, help="Actual hours spent")
@click.option("--notes", "-n", default="", help="Notes or learnings")
@click.pass_context
def complete(ctx: click.Context, task_id: int, hours: float | None, notes: str) -> None:
    """Mark a task as completed (manual, via CLI)."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    state.update_task_status(
        task_id=task_id, status="done", actual_hours=hours, learnings=notes,
    )
    state.log_feedback(
        task_id=task_id, status="done", actual_hours=hours,
        learnings=notes, source="cli",
    )

    task = state.get_tasks_for_date("")
    click.echo(f"Task #{task_id} marked as done.")
    if hours:
        click.echo(f"  Hours: {hours}")
    if notes:
        click.echo(f"  Notes: {notes}")


@cli.command()
@click.argument("task_id", type=int)
@click.option("--reason", "-r", default="", help="Why was it skipped")
@click.pass_context
def skip(ctx: click.Context, task_id: int, reason: str) -> None:
    """Mark a task as skipped."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    state.update_task_status(task_id=task_id, status="skipped", learnings=reason)
    state.log_feedback(
        task_id=task_id, status="skipped", notes=reason, source="cli",
    )
    click.echo(f"Task #{task_id} marked as skipped.")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current state across all tracks."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)

    click.echo("\nPlanner Agent Status")
    click.echo("=" * 50)

    # Last briefing
    last = state.get_last_briefing()
    if last:
        click.echo(f"  Last briefing: {last['date'][:10]} ({last['focus_track']})")
    else:
        click.echo("  Last briefing: never (run `planner init` first)")

    # Completion stats
    stats = state.get_completion_stats(days=7)
    total = stats.get("total", 0)
    done = stats.get("done", 0)
    hours = stats.get("hours_done", 0) or 0
    rate = (done / total * 100) if total > 0 else 0
    click.echo(f"\n  Last 7 days: {done}/{total} tasks ({rate:.0f}%), {hours:.1f}h logged")

    # Skill tracks
    skills = state.get_all_skills()
    if skills:
        click.echo("\n  Skill Tracks:")
        for s in skills:
            h = s.get("hours_invested", 0) or 0
            items = s.get("items_completed", 0) or 0
            phase_icon = {"learn": "📖", "practice": "🔬", "produce": "🚀"}.get(
                s["current_phase"], "?"
            )
            click.echo(
                f"    {phase_icon} {s['name']:<30} "
                f"phase={s['current_phase']:<10} "
                f"{h:>5.1f}h  {items:>3} items"
            )

    # Achievements
    counts = state.get_achievement_counts()
    if counts:
        click.echo("\n  Portfolio:")
        for atype, count in sorted(counts.items()):
            click.echo(f"    {atype}: {count}")
    else:
        click.echo("\n  Portfolio: empty (use `planner log-achievement` to add)")

    # Skipped patterns
    skipped = state.get_skipped_patterns(days=14)
    if skipped:
        click.echo(click.style("\n  Skipping patterns (last 14 days):", fg="yellow"))
        for p in skipped:
            click.echo(
                click.style(
                    f"    {p['track']}/{p['task_type']}: skipped {p['skip_count']}x",
                    fg="yellow",
                )
            )


@cli.command()
@click.pass_context
def portfolio(ctx: click.Context) -> None:
    """Show portfolio status — achievements vs gaps."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    achievements = state.get_all_achievements()
    counts = state.get_achievement_counts()

    click.echo("\nPortfolio Status")
    click.echo("=" * 50)

    target_types = [
        ("cve", "CVEs Discovered"),
        ("hall_of_fame", "Bug Bounty Hall of Fames"),
        ("research_paper", "Research Papers"),
        ("patent", "Patents"),
        ("blog_post", "Blog Posts / Articles"),
        ("conference_talk", "Conference Talks"),
        ("open_source", "Open Source Projects"),
        ("ctf_placement", "CTF Placements"),
        ("certification", "Certifications"),
        ("hackathon", "Hackathons"),
    ]

    critical_gaps = []
    for type_id, label in target_types:
        count = counts.get(type_id, 0)
        if count == 0 and type_id in ("research_paper", "cve", "conference_talk", "patent"):
            click.echo(click.style(f"  {label}: {count}  ← GAP", fg="red", bold=True))
            critical_gaps.append(label)
        elif count == 0:
            click.echo(click.style(f"  {label}: {count}", fg="yellow"))
        else:
            click.echo(click.style(f"  {label}: {count}", fg="green"))

    if achievements:
        click.echo(f"\n  Recent achievements:")
        for a in achievements[:10]:
            click.echo(f"    [{a['achievement_type']}] {a['title']}")
            if a.get("url"):
                click.echo(click.style(f"      {a['url']}", fg="bright_black"))

    if critical_gaps:
        click.echo(click.style(
            f"\n  {len(critical_gaps)} critical gaps for Global Talent Visa",
            fg="red", bold=True,
        ))


@cli.command(name="log-achievement")
@click.option("--type", "-t", "atype", required=True,
              type=click.Choice([
                  "cve", "hall_of_fame", "research_paper", "patent",
                  "blog_post", "conference_talk", "open_source",
                  "ctf_placement", "certification", "hackathon", "other",
              ]),
              help="Achievement type")
@click.option("--title", required=True, help="Achievement title")
@click.option("--url", "-u", default="", help="URL to the achievement")
@click.option("--description", "-d", default="", help="Description")
@click.option("--track", default="", help="Related skill track")
@click.pass_context
def log_achievement(ctx: click.Context, atype: str, title: str, url: str,
                    description: str, track: str) -> None:
    """Record a portfolio achievement (CVE, paper, talk, etc.)."""
    config = ctx.obj["config"]

    from planner_agent.models import Achievement, AchievementType
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    achievement = Achievement(
        achievement_type=AchievementType(atype),
        title=title,
        url=url,
        description=description,
        track=track,
    )
    aid = state.add_achievement(achievement)
    click.echo(f"Achievement logged (ID: {aid}): [{atype}] {title}")


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize the planner with skill tracks from config."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)

    for track_id, track_config in config.tracks.items():
        state.upsert_skill(
            track_id=track_id,
            name=track_config.name,
            current_phase=track_config.current_phase,
            priority=track_config.priority,
        )
        click.echo(f"  Initialized: {track_config.name} (phase={track_config.current_phase})")

    # Log existing achievements
    click.echo("\nSkill tracks initialized from config.yaml.")
    click.echo("Next steps:")
    click.echo("  1. Log existing achievements: planner log-achievement --type hall_of_fame --title 'Atlassian HoF #1'")
    click.echo("  2. Generate first briefing: planner daily --no-email")
    click.echo("  3. Configure email in config.yaml and .env")
    click.echo("  4. Install schedule: planner install-schedule")


@cli.command(name="install-schedule")
@click.option("--time", "-t", "time_str", default=None, help="Briefing time (HH:MM)")
@click.option("--uninstall", is_flag=True, help="Remove installed schedule")
@click.pass_context
def install_schedule_cmd(ctx: click.Context, time_str: str | None, uninstall: bool) -> None:
    """Install or remove daily schedule (launchd/cron)."""
    from planner_agent.scheduling import install_schedule, uninstall_schedule

    config = ctx.obj["config"]

    if uninstall:
        if uninstall_schedule():
            click.echo("Schedule removed.")
        else:
            click.echo("No schedule found to remove.")
        return

    briefing_time = time_str or config.schedule.briefing_time
    config_path = ctx.obj["config_path"]
    result = install_schedule(time_str=briefing_time, config_path=config_path)
    click.echo(f"Schedule installed: daily at {briefing_time}")
    click.echo(f"  {result}")


@cli.command()
@click.option("--days", "-d", type=int, default=7, help="Number of days to show")
@click.pass_context
def history(ctx: click.Context, days: int) -> None:
    """Show recent task history."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    tasks = state.get_recent_completed(days=days)

    if not tasks:
        click.echo("No completed tasks found.")
        return

    click.echo(f"\nCompleted tasks (last {days} days):")
    click.echo("-" * 60)

    for t in tasks:
        hours = t.get("actual_hours") or t.get("estimated_hours", 0)
        click.echo(f"  [{t['track']}] {t['title']} ({hours}h)")
        if t.get("learnings"):
            click.echo(click.style(f"    Learned: {t['learnings']}", fg="cyan"))


# --- Internal helpers ---

def _process_replies_impl(config, state, agent) -> int:  # type: ignore[no-untyped-def]
    """Process email replies and update task statuses."""
    from planner_agent.email.receiver import EmailReceiver

    receiver = EmailReceiver(config.imap)
    last_date = state.last_briefing_date
    replies = receiver.fetch_replies(since_date=last_date)

    if not replies:
        return 0

    last_briefing = state.get_last_briefing()
    if not last_briefing:
        return 0

    briefing_tasks = json.loads(last_briefing.get("tasks_json", "[]"))
    total_updated = 0

    for reply in replies:
        feedback = agent.parse_feedback(reply["body"], briefing_tasks)
        updated = agent.apply_feedback(feedback, briefing_tasks)
        total_updated += updated

    return total_updated


def _print_briefing(briefing) -> None:  # type: ignore[no-untyped-def]
    """Print a briefing to the terminal."""
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  DAILY BRIEFING — {briefing.date}")
    click.echo(f"  Focus: {briefing.focus_track} ({briefing.focus_phase})")
    click.echo(f"  {briefing.focus_rationale}")
    click.echo(f"{'=' * 60}\n")

    for i, task in enumerate(briefing.tasks, 1):
        p_color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "white"}.get(
            task.priority, "white"
        )
        click.echo(click.style(
            f"  {i}. [{task.priority.upper()}] {task.title} ({task.estimated_hours}h)",
            fg=p_color, bold=True,
        ))
        click.echo(f"     {task.description}")
        if task.resource_url:
            click.echo(click.style(f"     → {task.resource_name or task.resource_url}", fg="cyan"))
            click.echo(click.style(f"       {task.resource_url}", fg="bright_black"))
        if task.why:
            click.echo(click.style(f"     Why: {task.why}", fg="bright_black"))
        click.echo()

    click.echo(f"  Total: {briefing.total_estimated_hours}h planned\n")

    if briefing.portfolio_gaps:
        click.echo(click.style("  Portfolio Gaps:", fg="red", bold=True))
        for gap in briefing.portfolio_gaps:
            click.echo(click.style(f"    ⚠ {gap}", fg="red"))
        click.echo()

    if briefing.skill_observations:
        click.echo(click.style("  Observations:", fg="blue"))
        for obs in briefing.skill_observations:
            click.echo(f"    • {obs}")
        click.echo()

    if briefing.newsletter_topics:
        click.echo("  Newsletter topics to scan:")
        for topic in briefing.newsletter_topics:
            click.echo(f"    → {topic}")
