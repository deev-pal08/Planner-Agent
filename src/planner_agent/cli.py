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
@click.option("--date", "-d", default=None, help="Briefing date (YYYY-MM-DD)")
@click.option("--no-email", is_flag=True, help="Print to terminal, don't send email")
@click.option("--force", is_flag=True, help="Regenerate if briefing exists for today")
@click.pass_context
def daily(ctx: click.Context, date: str | None, no_email: bool, force: bool) -> None:
    """Full daily cycle: generate briefing, send email."""
    config = ctx.obj["config"]

    from planner_agent.agent.base import BriefingParseError
    from planner_agent.agent.orchestrator import Orchestrator
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)

    from datetime import UTC, datetime

    today = date or datetime.now(UTC).strftime("%Y-%m-%d")

    if not force and state.briefing_exists_for_date(today):
        click.echo(f"Briefing already generated for {today}. Use --force to regenerate.")
        return

    if force and state.briefing_exists_for_date(today):
        deleted = state.delete_pending_tasks_for_date(today)
        if deleted:
            click.echo(f"Cleared {deleted} pending tasks from previous briefing.")

    click.echo("Running daily cycle...")
    try:
        orchestrator = Orchestrator(config, state)
        briefing = orchestrator.run_daily(target_date=date, force=force)
    except (BriefingParseError, Exception) as e:
        click.echo(click.style(f"\nBriefing generation failed: {e}", fg="red"))
        if not no_email and config.email.enabled and config.email.to_addresses:
            try:
                from planner_agent.email.sender import EmailSender

                sender = EmailSender(
                    api_key=config.email.api_key,
                    from_address=config.email.from_address,
                    to_addresses=config.email.to_addresses,
                )
                stats = state.get_completion_stats()
                last = state.get_last_briefing()
                last_date = last["date"][:10] if last else "never"
                total = stats.get("total", 0)
                done = stats.get("done", 0)
                rate = (done / total * 100) if total > 0 else 0
                skills = state.get_all_skills()
                tracks = ", ".join(s["name"] for s in skills) if skills else "none"

                body = (
                    f"Briefing generation failed for {today}.\n\n"
                    f"Error: {e}\n\n"
                    f"Last briefing: {last_date}\n"
                    f"Recent: {done}/{total} tasks ({rate:.0f}%)\n"
                    f"Active tracks: {tracks}\n\n"
                    f"Check logs for details. Run `planner daily` to retry."
                )
                sender.send_plain(
                    subject=f"[Planner] Briefing Failed — {today}",
                    body=body,
                )
                click.echo("Failure notification email sent.")
            except Exception as email_err:
                click.echo(click.style(
                    f"Failed to send notification: {email_err}", fg="red",
                ))
        sys.exit(1)

    _print_briefing(briefing)

    if not no_email and config.email.enabled and config.email.to_addresses:
        try:
            from planner_agent.email.sender import EmailSender

            sender = EmailSender(
                api_key=config.email.api_key,
                from_address=config.email.from_address,
                to_addresses=config.email.to_addresses,
            )
            message_id = sender.send_briefing(briefing, directive=orchestrator.last_directive)

            last_briefing = state.get_last_briefing()
            if last_briefing:
                state.update_briefing_email(last_briefing["id"], message_id)

            click.echo(
                f"\nBriefing email sent to "
                f"{', '.join(config.email.to_addresses)}"
            )
        except Exception as e:
            click.echo(click.style(f"\nEmail send failed: {e}", fg="red"))
    elif no_email:
        click.echo("\n(--no-email: email not sent)")


@cli.command()
@click.option("--date", "-d", default=None, help="Generate for a specific date")
@click.option("--force", is_flag=True, help="Regenerate if briefing exists")
@click.pass_context
def briefing(ctx: click.Context, date: str | None, force: bool) -> None:
    """Generate and display daily briefing (no email)."""
    config = ctx.obj["config"]

    from planner_agent.agent.base import BriefingParseError
    from planner_agent.agent.orchestrator import Orchestrator
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)

    from datetime import UTC, datetime

    today = date or datetime.now(UTC).strftime("%Y-%m-%d")

    if not force and state.briefing_exists_for_date(today):
        click.echo(f"Briefing already generated for {today}. Use --force to regenerate.")
        return

    if force and state.briefing_exists_for_date(today):
        deleted = state.delete_pending_tasks_for_date(today)
        if deleted:
            click.echo(f"Cleared {deleted} pending tasks from previous briefing.")

    click.echo("Running daily cycle...")
    try:
        orchestrator = Orchestrator(config, state)
        b = orchestrator.run_daily(target_date=date, force=force)
    except BriefingParseError as e:
        click.echo(click.style(f"\nBriefing generation failed: {e}", fg="red"))
        sys.exit(1)
    _print_briefing(b)


@cli.command(name="process-replies")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt (for automation)")
@click.pass_context
def process_replies(ctx: click.Context, yes: bool) -> None:
    """Poll inbox for email replies and update task statuses."""
    config = ctx.obj["config"]

    from planner_agent.agent.loop import PlannerAgent
    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    agent = PlannerAgent(config, state)

    count = _process_replies_impl(config, state, agent, auto_confirm=yes)
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

    task = state.get_task_by_id(task_id)
    if not task:
        click.echo(click.style(f"Error: Task #{task_id} not found.", fg="red"))
        sys.exit(1)

    state.update_task_status(
        task_id=task_id, status="done", actual_hours=hours, learnings=notes,
    )
    state.log_feedback(
        task_id=task_id, status="done", actual_hours=hours,
        learnings=notes, source="cli",
    )

    track = task.get("track", "")
    if track:
        state.update_skill_hours(track, hours or task.get("estimated_hours", 0))

    click.echo(f"Task #{task_id} marked as done: {task['title']}")
    if hours:
        click.echo(f"  Hours: {hours}")
    if notes:
        click.echo(f"  Notes: {notes}")

    if notes:
        from planner_agent.agent.analyst import AnalystBrain

        analyst = AnalystBrain(config, state)
        click.echo("Updating intelligence profile...")
        analyst.update_from_single_task(
            task=task, status="done", hours=hours, notes=notes,
        )


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

    if reason:
        from planner_agent.agent.analyst import AnalystBrain

        task = state.get_task_by_id(task_id)
        if task:
            analyst = AnalystBrain(config, state)
            click.echo("Updating intelligence profile...")
            analyst.update_from_single_task(
                task=task, status="skipped", notes=reason,
            )


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current state — goals, milestones, skills, directive, profile."""
    config = ctx.obj["config"]

    from datetime import UTC, datetime

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    click.echo("\nPlanner Agent Status")
    click.echo("=" * 60)

    # --- Active Directive ---
    directive_row = state.get_active_directive()
    if directive_row:
        d = directive_row.get("directive", {})
        click.echo(click.style(
            f"\n  This Week: {d.get('weekly_theme', 'N/A')}",
            fg="cyan", bold=True,
        ))
        click.echo(f"  {d.get('strategic_focus', '')}")
        click.echo(
            f"  Period: {directive_row.get('week_start', '?')} — "
            f"{directive_row.get('week_end', '?')} | "
            f"Hours: {d.get('total_hours_available', 0):.0f}h"
        )
        targets = d.get("targets", [])
        if targets:
            for t in sorted(targets, key=lambda x: x.get("priority_rank", 99)):
                click.echo(
                    f"    #{t['priority_rank']} {t['track_id']}: "
                    f"{t['hours_allocated']}h ({t['phase']})"
                )
        alerts = d.get("alerts", [])
        for a in alerts:
            color = "red" if a.get("severity") == "critical" else "yellow"
            click.echo(click.style(
                f"    [{a['severity'].upper()}] {a['message']}", fg=color,
            ))

    # --- Goals ---
    goals = state.get_active_goals()
    if goals:
        click.echo(click.style("\n  Goals:", fg="green", bold=True))
        for g in goals:
            deadline = g.get("deadline", "no deadline")
            if deadline and deadline != "no deadline":
                dt = datetime.fromisoformat(deadline)
                days_left = (dt - datetime.fromisoformat(today)).days
                countdown = f"{days_left}d left"
            else:
                countdown = "no deadline"
            click.echo(
                f"    [{g.get('priority', '?').upper()}] "
                f"{g['title']} ({countdown})"
            )
            milestones = state.get_milestones_by_goal(g["id"])
            if milestones:
                done_ms = sum(
                    1 for m in milestones if m["status"] == "completed"
                )
                click.echo(
                    f"      Milestones: {done_ms}/{len(milestones)} done"
                )
                for m in milestones[:3]:
                    status_icon = {
                        "completed": "done",
                        "in_progress": "WIP",
                        "at_risk": "RISK",
                        "blocked": "BLOCKED",
                    }.get(m["status"], "pending")
                    click.echo(
                        f"        [{status_icon}] {m['title']} "
                        f"(by {m['target_date']})"
                    )
                if len(milestones) > 3:
                    click.echo(
                        f"        ... +{len(milestones) - 3} more"
                    )

    # --- Last briefing ---
    last = state.get_last_briefing()
    if last:
        click.echo(f"\n  Last briefing: {last['date'][:10]} ({last['focus_track']})")
    else:
        click.echo("\n  Last briefing: never (run `planner daily` first)")

    # --- Completion stats ---
    stats = state.get_completion_stats()
    total = stats.get("total", 0) or 0
    done = stats.get("done", 0) or 0
    hours = stats.get("hours_done", 0) or 0
    rate = (done / total * 100) if total > 0 else 0
    click.echo(
        f"  Progress: {done}/{total} tasks ({rate:.0f}%), "
        f"{hours:.1f}h logged"
    )

    # --- Skill tracks ---
    skills = state.get_all_skills()
    if skills:
        click.echo(click.style("\n  Skill Tracks:", bold=True))
        for s in skills:
            h = s.get("hours_invested", 0) or 0
            items = s.get("items_completed", 0) or 0
            comp = s.get("competence_level", "novice")
            phase_icon = {
                "learn": "L", "practice": "P", "produce": "X",
            }.get(s["current_phase"], "?")
            click.echo(
                f"    [{phase_icon}] {s['name']:<28} "
                f"{h:>5.1f}h  {items:>3} items  "
                f"({comp})"
            )

    # --- Intelligence profile summary ---
    profile_json = state.get_meta("user_intelligence_profile")
    if profile_json:
        from planner_agent.models import UserIntelligenceProfile
        profile = UserIntelligenceProfile.model_validate_json(profile_json)
        if profile.confidence_indicators:
            click.echo(click.style("\n  Strengths:", fg="green"))
            for c in profile.confidence_indicators[:3]:
                click.echo(f"    + {c}")
        if profile.concern_indicators:
            click.echo(click.style("  Concerns:", fg="red"))
            for c in profile.concern_indicators[:3]:
                click.echo(f"    - {c}")

    # --- Portfolio ---
    counts = state.get_achievement_counts()
    if counts:
        click.echo("\n  Portfolio:")
        for atype, count in sorted(counts.items()):
            click.echo(f"    {atype}: {count}")
    else:
        click.echo(
            "\n  Portfolio: empty (use `planner log-achievement` to add)"
        )

    # --- API cost tracking ---
    brain_names = ["strategist", "tactician", "critic", "analyst", "scout"]
    cost_lines = []
    total_input = 0
    total_output = 0
    total_calls = 0
    for bn in brain_names:
        raw = state.get_meta(f"tokens_{bn}")
        if raw:
            import json as _json
            try:
                data = _json.loads(raw)
                inp = data.get("input", 0)
                out = data.get("output", 0)
                calls = data.get("calls", 0)
                total_input += inp
                total_output += out
                total_calls += calls
                cost_lines.append(
                    f"    {bn:<12} {calls:>3} calls  "
                    f"{inp:>7,} in / {out:>7,} out"
                )
            except (ValueError, TypeError):
                pass
    if cost_lines:
        click.echo(click.style("\n  API Usage (cumulative):", bold=True))
        for line in cost_lines:
            click.echo(line)
        click.echo(
            f"    {'TOTAL':<12} {total_calls:>3} calls  "
            f"{total_input:>7,} in / {total_output:>7,} out"
        )

    click.echo()


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
        click.echo("\n  Recent achievements:")
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
    click.echo(
        "  1. Log existing achievements: "
        "planner log-achievement --type hall_of_fame --title 'Atlassian HoF #1'"
    )
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
@click.option("--limit", "-l", type=int, default=15, help="Number of tasks to show")
@click.pass_context
def history(ctx: click.Context, limit: int) -> None:
    """Show recent task history."""
    config = ctx.obj["config"]

    from planner_agent.state.store import StateStore

    state = StateStore(config.state_dir)
    tasks = state.get_recent_completed(limit=limit)

    if not tasks:
        click.echo("No completed tasks found.")
        return

    click.echo(f"\nCompleted tasks (last {limit}):")
    click.echo("-" * 60)

    for t in tasks:
        hours = t.get("actual_hours") or t.get("estimated_hours", 0)
        click.echo(f"  [{t['track']}] {t['title']} ({hours}h)")
        if t.get("learnings"):
            click.echo(click.style(f"    Learned: {t['learnings']}", fg="cyan"))


# --- Internal helpers ---

def _process_replies_impl(config, state, agent, *, auto_confirm: bool = False) -> int:
    """Process email replies and update task statuses."""
    last_briefing = state.get_last_briefing()
    if not last_briefing:
        click.echo("No briefing found — generate one first with `planner daily`.")
        return 0

    from planner_agent.email.receiver import EmailReceiver

    receiver = EmailReceiver(config.imap)
    replies = receiver.fetch_replies(
        since_date=state.last_briefing_date,
        from_address=config.email.from_address,
    )

    if not replies:
        return 0

    combined_body = "\n\n---\n\n".join(r["body"] for r in replies)

    briefing_tasks = json.loads(last_briefing.get("tasks_json", "[]"))
    feedback = agent.parse_feedback(combined_body, briefing_tasks)

    # Issue 1: Show parsed feedback and ask for confirmation
    click.echo("\nParsed feedback from email reply:")
    click.echo("-" * 50)
    for entry in feedback.task_updates:
        idx = entry.task_id - 1
        title = briefing_tasks[idx]["title"] if 0 <= idx < len(briefing_tasks) else "?"
        hours_str = f"{entry.actual_hours}h" if entry.actual_hours else "—"
        notes_str = entry.notes or entry.learnings or ""
        click.echo(
            f"  Task {entry.task_id}: {title}\n"
            f"    Status: {entry.status}  |  Hours: {hours_str}"
        )
        if notes_str:
            click.echo(f"    Notes: {notes_str}")
    if feedback.general_notes:
        click.echo(f"\n  General notes: {feedback.general_notes}")
    if feedback.total_hours_reported:
        click.echo(f"  Total hours reported: {feedback.total_hours_reported}h")
    click.echo("-" * 50)

    if not auto_confirm and not click.confirm("Apply these updates to the database?"):
        click.echo("Aborted. Use `planner complete <id>` to update tasks manually.")
        return 0

    updated = agent.apply_feedback(feedback, briefing_tasks)

    if updated > 0:
        click.echo("Updating intelligence profile...")
        from planner_agent.agent.analyst import AnalystBrain

        analyst = AnalystBrain(config, state)
        analyst.update_profile(feedback=feedback, briefing_tasks=briefing_tasks)

    return updated


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

    # Newsletter reading block (always last, separate from tasks)
    if briefing.newsletter_reading and briefing.newsletter_reading.articles:
        nr = briefing.newsletter_reading
        task_num = len(briefing.tasks) + 1
        click.echo(click.style(
            f"  {task_num}. [NEWSLETTER] {nr.title} ({nr.estimated_hours}h)",
            fg="magenta", bold=True,
        ))
        click.echo(f"     {nr.description}")
        for article in nr.articles:
            priority_color = {
                "CRITICAL": "red", "IMPORTANT": "yellow",
                "INTERESTING": "blue", "REFERENCE": "white",
            }.get(article.priority, "white")
            click.echo(click.style(
                f"     • [{article.priority}] {article.title}",
                fg=priority_color,
            ))
            click.echo(click.style(f"       {article.url}", fg="bright_black"))
            if article.why:
                click.echo(click.style(f"       Why: {article.why}", fg="bright_black"))
        click.echo()

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
