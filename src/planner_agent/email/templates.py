"""HTML email templates for daily briefings."""

from __future__ import annotations

from planner_agent.models import DailyBriefing, Phase

PHASE_LABELS = {
    Phase.LEARN: ("LEARN", "#6366f1", "#eef2ff"),
    Phase.PRACTICE: ("PRACTICE", "#f59e0b", "#fffbeb"),
    Phase.PRODUCE: ("PRODUCE", "#10b981", "#ecfdf5"),
}

PRIORITY_STYLES = {
    "critical": ("#ef4444", "#fef2f2", "#991b1b"),
    "high": ("#f97316", "#fff7ed", "#9a3412"),
    "medium": ("#3b82f6", "#eff6ff", "#1e40af"),
    "low": ("#6b7280", "#f9fafb", "#374151"),
}

TASK_TYPE_ICONS = {
    "read": "\U0001f4d6",
    "lab": "\U0001f9ea",
    "ctf": "\U0001f3af",
    "code_review": "\U0001f50d",
    "bug_bounty": "\U0001f41b",
    "write": "✏️",
    "build": "\U0001f6e0️",
    "research": "\U0001f52c",
    "course": "\U0001f393",
    "other": "⭐",
}


def render_briefing_html(
    briefing: DailyBriefing,
    directive: dict | None = None,
    opportunities: list[dict] | None = None,
) -> str:
    phase_label, phase_color, _phase_bg = PHASE_LABELS.get(
        briefing.focus_phase, ("LEARN", "#6366f1", "#eef2ff")
    )

    tasks_html = _render_tasks(briefing)
    newsletter_reading_html = _render_newsletter_reading(briefing)
    gaps_html = _render_gaps(briefing)
    observations_html = _render_observations(briefing)
    newsletter_html = _render_newsletter(briefing)
    directive_html = _render_directive_banner(directive)
    opportunities_html = _render_opportunities(
        opportunities or [], briefing.date
    )

    from datetime import datetime
    try:
        date_obj = datetime.fromisoformat(briefing.date)
        formatted_date = date_obj.strftime("%A, %B %-d")
        short_date = date_obj.strftime("%b %-d, %Y")
    except ValueError:
        formatted_date = briefing.date
        short_date = briefing.date

    focus_display = briefing.focus_track.replace("_", " ").title()

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#0f0f14;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',\
Roboto,'Helvetica Neue',Arial,sans-serif;
  -webkit-font-smoothing:antialiased;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#0f0f14;">
<tr><td align="center" style="padding:40px 16px;">

<!-- Main Container -->
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#1a1a24;border-radius:20px;overflow:hidden;
              border:1px solid rgba(255,255,255,0.06);">

  <!-- Header -->
  <tr><td style="padding:0;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:linear-gradient(135deg,#1e1b4b 0%,#312e81 50%,\
#3730a3 100%);">
      <tr><td style="padding:40px 40px 12px 40px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td>
              <p style="margin:0;font-size:11px;font-weight:700;\
color:rgba(255,255,255,0.4);text-transform:uppercase;\
letter-spacing:2.5px;">
                PLANNER AGENT
              </p>
            </td>
            <td align="right">
              <span style="display:inline-block;background-color:\
rgba(255,255,255,0.1);backdrop-filter:blur(8px);\
color:rgba(255,255,255,0.7);font-size:12px;\
font-weight:600;padding:6px 14px;border-radius:20px;\
border:1px solid rgba(255,255,255,0.1);">
                {briefing.total_estimated_hours}h planned
              </span>
            </td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="padding:16px 40px 6px 40px;">
        <p style="margin:0;font-size:32px;font-weight:800;\
color:#ffffff;letter-spacing:-1px;line-height:1.1;">
          {formatted_date}
        </p>
      </td></tr>
      <tr><td style="padding:4px 40px 0 40px;">
        <p style="margin:0;font-size:14px;color:rgba(255,255,255,0.4);\
font-weight:400;">
          {short_date}
        </p>
      </td></tr>
      <tr><td style="padding:20px 40px 36px 40px;">
        <table cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding-right:10px;">
              <span style="display:inline-block;background-color:\
{phase_color};color:#ffffff;font-size:11px;\
font-weight:700;padding:5px 14px;border-radius:6px;\
letter-spacing:1px;">
                {phase_label}
              </span>
            </td>
            <td>
              <span style="font-size:15px;color:rgba(255,255,255,0.85);\
font-weight:600;">
                {focus_display}
              </span>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </td></tr>

  <!-- Rationale -->
  <tr><td style="padding:28px 40px 24px 40px;\
border-bottom:1px solid rgba(255,255,255,0.06);">
    <p style="margin:0;font-size:14px;line-height:1.7;\
color:rgba(255,255,255,0.55);font-weight:400;">
      {briefing.focus_rationale}
    </p>
  </td></tr>

  <!-- Directive Banner -->
  {directive_html}

  <!-- Tasks Section -->
  <tr><td style="padding:28px 40px 16px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td>
          <p style="margin:0;font-size:11px;font-weight:700;\
color:rgba(255,255,255,0.3);text-transform:uppercase;\
letter-spacing:2px;">
            TODAY&rsquo;S TASKS
          </p>
        </td>
        <td align="right">
          <span style="font-size:12px;color:rgba(255,255,255,0.25);\
font-weight:500;">
            {len(briefing.tasks)} tasks
          </span>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- Task Cards -->
  {tasks_html}

  <!-- Newsletter Reading -->
  {newsletter_reading_html}

  <!-- Bottom Spacer -->
  <tr><td style="padding:12px;"></td></tr>

</table>

{gaps_html}
{observations_html}
{opportunities_html}
{newsletter_html}

<!-- Reply CTA -->
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td style="padding:24px 36px;background-color:#1a1a24;\
border-radius:16px;border:1px dashed rgba(255,255,255,0.12);\
text-align:center;">
    <p style="margin:0 0 6px 0;font-size:15px;\
color:rgba(255,255,255,0.8);font-weight:600;">
      ✉️ Reply to update your progress
    </p>
    <p style="margin:0;font-size:13px;color:rgba(255,255,255,0.3);\
line-height:1.5;">
      &ldquo;Done 1 and 2. Skipped 3 &mdash; too tired. \
Spent 3 hours total.&rdquo;
    </p>
  </td></tr>
</table>

<!-- Footer -->
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td align="center" style="padding:16px;">
    <p style="margin:0;font-size:11px;\
color:rgba(255,255,255,0.15);font-weight:400;\
letter-spacing:0.5px;">
      Planner Agent &middot; Adaptive Career Orchestrator
    </p>
  </td></tr>
</table>

</td></tr>
</table>

</body>
</html>"""


def _render_tasks(briefing: DailyBriefing) -> str:
    html = ""
    for i, task in enumerate(briefing.tasks, 1):
        color, _bg, _text_color = PRIORITY_STYLES.get(
            task.priority, ("#6b7280", "#f9fafb", "#374151")
        )
        icon = TASK_TYPE_ICONS.get(task.task_type, "⭐")

        resource_html = ""
        if task.resource_url:
            name = task.resource_name or task.resource_url
            if len(name) > 70:
                name = name[:67] + "..."
            resource_html = f"""
            <tr><td style="padding:12px 0 0 0;">
              <table cellpadding="0" cellspacing="0" border="0"
                     style="background-color:rgba(59,130,246,0.08);\
border-radius:10px;width:100%;border:1px solid \
rgba(59,130,246,0.15);">
                <tr><td style="padding:12px 16px;">
                  <a href="{task.resource_url}"
                     style="color:#60a5fa;font-size:13px;\
font-weight:500;text-decoration:none;">
                    \U0001f517 {name}
                  </a>
                </td></tr>
              </table>
            </td></tr>"""

        why_html = ""
        if task.why:
            why_html = f"""
            <tr><td style="padding:10px 0 0 0;">
              <p style="margin:0;font-size:12px;\
color:rgba(255,255,255,0.3);line-height:1.6;\
font-style:italic;padding-left:12px;\
border-left:2px solid rgba(255,255,255,0.08);">
                {task.why}
              </p>
            </td></tr>"""

        html += f"""
  <tr><td style="padding:6px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background-color:rgba(255,255,255,0.03);\
border:1px solid rgba(255,255,255,0.06);border-radius:14px;\
border-left:3px solid {color};">
      <tr><td style="padding:22px 24px;">

        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="44" valign="top">
              <div style="width:36px;height:36px;border-radius:10px;\
background-color:rgba(255,255,255,0.05);\
color:rgba(255,255,255,0.5);font-size:16px;\
font-weight:800;line-height:36px;text-align:center;\
border:1px solid rgba(255,255,255,0.08);">
                {i}
              </div>
            </td>
            <td style="padding-left:10px;" valign="top">
              <p style="margin:0 0 6px 0;font-size:15px;font-weight:700;\
color:rgba(255,255,255,0.9);line-height:1.4;">
                {task.title}
              </p>
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:8px;">
                    <span style="display:inline-block;\
background-color:{color};color:#ffffff;\
font-size:10px;font-weight:700;padding:3px 10px;\
border-radius:5px;text-transform:uppercase;\
letter-spacing:0.5px;">
                      {task.priority.upper()}
                    </span>
                  </td>
                  <td style="padding-right:8px;">
                    <span style="font-size:12px;\
color:rgba(255,255,255,0.35);">
                      {icon} {task.task_type.replace('_', ' ').title()}
                    </span>
                  </td>
                  <td style="padding-right:8px;">
                    <span style="font-size:12px;\
color:rgba(255,255,255,0.35);">
                      ⏱ {task.estimated_hours}h
                    </span>
                  </td>
                  <td>
                    <span style="font-size:12px;\
color:rgba(255,255,255,0.25);">
                      {task.track.replace('_', ' ').title()}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <table width="100%" cellpadding="0" cellspacing="0"
               border="0" style="margin-top:14px;">
          <tr><td>
            <p style="margin:0;font-size:13px;\
color:rgba(255,255,255,0.45);line-height:1.7;">
              {task.description}
            </p>
          </td></tr>
          {resource_html}
          {why_html}
        </table>

      </td></tr>
    </table>
  </td></tr>"""

    return html


def _render_newsletter_reading(briefing: DailyBriefing) -> str:
    nr = briefing.newsletter_reading
    if not nr or not nr.articles:
        return ""

    task_num = len(briefing.tasks) + 1

    priority_colors = {
        "CRITICAL": "#ef4444",
        "IMPORTANT": "#f97316",
        "INTERESTING": "#3b82f6",
        "REFERENCE": "#6b7280",
    }

    articles_html = ""
    for article in nr.articles:
        color = priority_colors.get(article.priority, "#6b7280")
        why_html = ""
        if article.why:
            why_html = (
                f'<p style="margin:6px 0 0 0;font-size:12px;'
                f"color:rgba(255,255,255,0.3);line-height:1.5;"
                f'font-style:italic;">'
                f"{article.why}</p>"
            )

        articles_html += f"""
            <tr><td style="padding:5px 0;">
              <table width="100%" cellpadding="0" cellspacing="0"
                     border="0"
                     style="background-color:rgba(255,255,255,0.02);\
border-radius:10px;border:1px solid rgba(255,255,255,0.06);">
                <tr><td style="padding:14px 16px;">
                  <table width="100%" cellpadding="0" cellspacing="0"
                         border="0">
                    <tr>
                      <td>
                        <span style="display:inline-block;\
background-color:{color};\
color:#ffffff;font-size:9px;font-weight:700;\
padding:3px 8px;border-radius:4px;\
text-transform:uppercase;\
letter-spacing:0.5px;">
                          {article.priority}
                        </span>
                      </td>
                    </tr>
                  </table>
                  <p style="margin:8px 0 0 0;font-size:13px;\
line-height:1.4;">
                    <a href="{article.url}"
                       style="color:#818cf8;font-weight:600;\
text-decoration:none;">
                      {article.title}
                    </a>
                  </p>{why_html}
                </td></tr>
              </table>
            </td></tr>"""

    return f"""
  <tr><td style="padding:12px 40px 6px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background-color:rgba(139,92,246,0.06);\
border:1px solid rgba(139,92,246,0.15);\
border-radius:14px;border-left:3px solid #8b5cf6;">
      <tr><td style="padding:22px 24px;">

        <table width="100%" cellpadding="0" cellspacing="0"
               border="0">
          <tr>
            <td width="44" valign="top">
              <div style="width:36px;height:36px;border-radius:10px;\
background-color:rgba(139,92,246,0.12);\
color:#a78bfa;font-size:16px;\
font-weight:800;line-height:36px;\
text-align:center;border:1px solid \
rgba(139,92,246,0.2);">
                {task_num}
              </div>
            </td>
            <td style="padding-left:10px;" valign="top">
              <p style="margin:0 0 6px 0;font-size:15px;\
font-weight:700;color:rgba(255,255,255,0.9);\
line-height:1.4;">
                {nr.title}
              </p>
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:8px;">
                    <span style="display:inline-block;\
background-color:#8b5cf6;color:#ffffff;\
font-size:10px;font-weight:700;\
padding:3px 10px;border-radius:5px;\
text-transform:uppercase;\
letter-spacing:0.5px;">
                      NEWSLETTER
                    </span>
                  </td>
                  <td style="padding-right:8px;">
                    <span style="font-size:12px;\
color:rgba(255,255,255,0.35);">
                      \U0001f4f0 {len(nr.articles)} articles
                    </span>
                  </td>
                  <td>
                    <span style="font-size:12px;\
color:rgba(255,255,255,0.35);">
                      ⏱ {nr.estimated_hours}h
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <table width="100%" cellpadding="0" cellspacing="0"
               border="0" style="margin-top:14px;">
          <tr><td>
            <p style="margin:0 0 12px 0;font-size:13px;\
color:rgba(255,255,255,0.45);line-height:1.7;">
              {nr.description}
            </p>
          </td></tr>
          {articles_html}
        </table>

      </td></tr>
    </table>
  </td></tr>"""


def _render_gaps(briefing: DailyBriefing) -> str:
    if not briefing.portfolio_gaps:
        return ""

    items = ""
    for gap in briefing.portfolio_gaps:
        items += f"""
        <tr><td style="padding:6px 0;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="24" valign="top"
                  style="font-size:14px;color:#ef4444;">
                ⚠
              </td>
              <td style="font-size:13px;\
color:rgba(255,255,255,0.55);line-height:1.6;">
                {gap}
              </td>
            </tr>
          </table>
        </td></tr>"""

    return f"""
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td style="background-color:#1a1a24;border-radius:16px;\
overflow:hidden;border:1px solid rgba(239,68,68,0.2);">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:18px 28px 10px 28px;\
background-color:rgba(239,68,68,0.06);\
border-bottom:1px solid rgba(239,68,68,0.12);">
        <p style="margin:0;font-size:11px;font-weight:700;\
color:#ef4444;text-transform:uppercase;\
letter-spacing:2px;">
          PORTFOLIO GAPS
        </p>
      </td></tr>
      <tr><td style="padding:16px 28px 20px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               border="0">
          {items}
        </table>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def _render_observations(briefing: DailyBriefing) -> str:
    if not briefing.skill_observations:
        return ""

    items = ""
    for obs in briefing.skill_observations:
        items += f"""
        <tr><td style="padding:6px 0;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="24" valign="top"
                  style="font-size:8px;color:#3b82f6;\
padding-top:4px;">
                ●
              </td>
              <td style="font-size:13px;\
color:rgba(255,255,255,0.5);line-height:1.6;">
                {obs}
              </td>
            </tr>
          </table>
        </td></tr>"""

    return f"""
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td style="background-color:#1a1a24;border-radius:16px;\
overflow:hidden;border:1px solid rgba(59,130,246,0.15);">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:18px 28px 10px 28px;\
background-color:rgba(59,130,246,0.05);\
border-bottom:1px solid rgba(59,130,246,0.1);">
        <p style="margin:0;font-size:11px;font-weight:700;\
color:#3b82f6;text-transform:uppercase;\
letter-spacing:2px;">
          OBSERVATIONS
        </p>
      </td></tr>
      <tr><td style="padding:16px 28px 20px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               border="0">
          {items}
        </table>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def _render_directive_banner(directive: dict | None) -> str:
    if not directive:
        return ""

    theme = directive.get("weekly_theme", "")
    focus = directive.get("strategic_focus", "")
    if not theme and not focus:
        return ""

    targets = directive.get("targets", [])
    alerts = directive.get("alerts", [])
    constraints = directive.get("constraints", [])

    targets_html = ""
    for t in targets[:4]:
        track = t.get("track_id", "").replace("_", " ").title()
        hours = t.get("hours_allocated", 0)
        rank = t.get("priority_rank", 0)
        phase = t.get("phase", "learn").upper()
        objectives = t.get("objectives", [])
        obj_text = objectives[0] if objectives else ""
        if len(obj_text) > 80:
            obj_text = obj_text[:77] + "..."
        targets_html += f"""
            <tr><td style="padding:4px 0;">
              <table width="100%" cellpadding="0" cellspacing="0"
                     border="0"
                     style="background-color:rgba(16,185,129,0.06);\
border-radius:8px;border:1px solid \
rgba(16,185,129,0.12);">
                <tr><td style="padding:10px 14px;">
                  <table width="100%" cellpadding="0"
                         cellspacing="0" border="0">
                    <tr>
                      <td style="font-size:13px;font-weight:600;\
color:#34d399;">
                        #{rank} {track}
                      </td>
                      <td align="right">
                        <span style="font-size:11px;\
color:#10b981;font-weight:600;">
                          {phase}
                        </span>
                        <span style="font-size:11px;\
color:rgba(255,255,255,0.3);padding-left:8px;">
                          {hours}h
                        </span>
                      </td>
                    </tr>
                  </table>
                  <p style="margin:4px 0 0 0;font-size:12px;\
color:rgba(255,255,255,0.4);line-height:1.4;">
                    {obj_text}
                  </p>
                </td></tr>
              </table>
            </td></tr>"""

    alerts_html = ""
    for a in alerts[:3]:
        severity = a.get("severity", "info").upper()
        msg = a.get("message", "")
        sev_color = {
            "CRITICAL": "#ef4444",
            "HIGH": "#f97316",
            "MEDIUM": "#3b82f6",
        }.get(severity, "#6b7280")
        alerts_html += f"""
            <tr><td style="padding:3px 0;">
              <span style="font-size:10px;font-weight:700;\
color:{sev_color};padding-right:6px;">
                {severity}
              </span>
              <span style="font-size:12px;\
color:rgba(255,255,255,0.5);">
                {msg}
              </span>
            </td></tr>"""

    constraints_html = ""
    for c in constraints[:3]:
        constraints_html += f"""
            <tr><td style="padding:3px 0;">
              <span style="font-size:12px;\
color:rgba(245,158,11,0.7);">
                ⚡ {c}
              </span>
            </td></tr>"""

    extra_sections = ""
    if alerts_html:
        extra_sections += f"""
          <tr><td style="padding:12px 0 0 0;">
            <p style="margin:0 0 6px 0;font-size:10px;\
font-weight:700;color:rgba(255,255,255,0.25);\
text-transform:uppercase;letter-spacing:1.5px;">
              Alerts
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   border="0">
              {alerts_html}
            </table>
          </td></tr>"""
    if constraints_html:
        extra_sections += f"""
          <tr><td style="padding:12px 0 0 0;">
            <p style="margin:0 0 6px 0;font-size:10px;\
font-weight:700;color:rgba(255,255,255,0.25);\
text-transform:uppercase;letter-spacing:1.5px;">
              Constraints
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   border="0">
              {constraints_html}
            </table>
          </td></tr>"""

    return f"""
  <tr><td style="padding:20px 40px 8px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background-color:rgba(16,185,129,0.04);\
border:1px solid rgba(16,185,129,0.15);\
border-radius:14px;">
      <tr><td style="padding:20px 24px 12px 24px;\
border-bottom:1px solid rgba(16,185,129,0.1);">
        <p style="margin:0;font-size:10px;font-weight:700;\
color:#10b981;text-transform:uppercase;\
letter-spacing:2px;">
          WEEKLY DIRECTIVE
        </p>
        <p style="margin:8px 0 0 0;font-size:18px;\
font-weight:700;color:rgba(255,255,255,0.85);\
line-height:1.3;">
          {theme}
        </p>
        <p style="margin:6px 0 10px 0;font-size:13px;\
color:rgba(255,255,255,0.4);line-height:1.6;">
          {focus}
        </p>
      </td></tr>
      <tr><td style="padding:16px 24px 20px 24px;">
        <p style="margin:0 0 8px 0;font-size:10px;\
font-weight:700;color:rgba(255,255,255,0.25);\
text-transform:uppercase;letter-spacing:1.5px;">
          Weekly Targets
        </p>
        <table width="100%" cellpadding="0" cellspacing="0"
               border="0">
          {targets_html}
        </table>
        {extra_sections}
      </td></tr>
    </table>
  </td></tr>"""


def _render_opportunities(
    opportunities: list[dict], today: str,
) -> str:
    if not opportunities:
        return ""

    from datetime import datetime as dt

    try:
        today_date = dt.fromisoformat(today).date()
    except ValueError:
        today_date = dt.now().date()

    # Filter to future deadlines/events and sort by urgency
    upcoming = []
    for o in opportunities:
        deadline = o.get("deadline")
        event_start = o.get("event_start")
        status = o.get("status", "discovered")
        if status in ("expired", "skipped", "completed"):
            continue
        ref_date = deadline or event_start
        if not ref_date:
            continue
        try:
            ref = dt.fromisoformat(ref_date).date()
            if ref < today_date:
                continue
            days_left = (ref - today_date).days
        except ValueError:
            days_left = 999
        upcoming.append({**o, "_days_left": days_left, "_ref_date": ref_date})

    upcoming.sort(key=lambda x: x["_days_left"])
    upcoming = upcoming[:8]

    if not upcoming:
        return ""

    items = ""
    for o in upcoming:
        days = o["_days_left"]
        title = o.get("title", "")
        url = o.get("url", "")
        opp_type = o.get("opportunity_type", "other")
        location = o.get("location", "")
        ref_date = o.get("_ref_date", "")

        # Urgency styling
        if days <= 7:
            urgency_color = "#ef4444"
            urgency_bg = "rgba(239,68,68,0.12)"
            urgency_text = f"{days}d left"
            urgency_border = "rgba(239,68,68,0.3)"
        elif days <= 14:
            urgency_color = "#f97316"
            urgency_bg = "rgba(249,115,22,0.1)"
            urgency_text = f"{days}d left"
            urgency_border = "rgba(249,115,22,0.25)"
        elif days <= 30:
            urgency_color = "#f59e0b"
            urgency_bg = "rgba(245,158,11,0.08)"
            urgency_text = f"{days}d left"
            urgency_border = "rgba(245,158,11,0.2)"
        else:
            urgency_color = "#10b981"
            urgency_bg = "rgba(16,185,129,0.06)"
            urgency_text = f"{days}d"
            urgency_border = "rgba(16,185,129,0.15)"

        type_labels = {
            "ctf": "CTF",
            "conference_cfp": "CFP",
            "bounty_program": "BOUNTY",
            "hackathon": "HACKATHON",
            "competition": "COMPETITION",
            "judging": "JUDGE/MENTOR",
            "certification": "CERT",
            "training": "TRAINING",
            "other": "EVENT",
        }
        type_label = type_labels.get(opp_type, "EVENT")

        title_html = (
            f'<a href="{url}" style="color:rgba(255,255,255,0.85);'
            f'font-weight:600;text-decoration:none;">{title}</a>'
            if url
            else f'<span style="color:rgba(255,255,255,0.85);'
            f'font-weight:600;">{title}</span>'
        )

        location_html = ""
        if location:
            location_html = (
                f'<span style="font-size:11px;'
                f'color:rgba(255,255,255,0.3);padding-left:8px;">'
                f"\U0001f4cd {location}</span>"
            )

        items += f"""
        <tr><td style="padding:5px 0;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 border="0"
                 style="background-color:{urgency_bg};\
border-radius:10px;border:1px solid {urgency_border};">
            <tr><td style="padding:14px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0"
                     border="0">
                <tr>
                  <td>
                    <span style="display:inline-block;\
background-color:rgba(255,255,255,0.08);\
color:rgba(255,255,255,0.5);font-size:9px;\
font-weight:700;padding:3px 8px;\
border-radius:4px;text-transform:uppercase;\
letter-spacing:0.5px;">
                      {type_label}
                    </span>{location_html}
                  </td>
                  <td align="right">
                    <span style="display:inline-block;\
background-color:{urgency_color};color:#ffffff;\
font-size:10px;font-weight:700;\
padding:3px 10px;border-radius:5px;">
                      {urgency_text}
                    </span>
                  </td>
                </tr>
              </table>
              <p style="margin:8px 0 2px 0;font-size:13px;\
line-height:1.4;">
                {title_html}
              </p>
              <p style="margin:0;font-size:11px;\
color:rgba(255,255,255,0.3);">
                {ref_date}
              </p>
            </td></tr>
          </table>
        </td></tr>"""

    return f"""
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td style="background-color:#1a1a24;border-radius:16px;\
overflow:hidden;border:1px solid rgba(245,158,11,0.15);">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:18px 28px 10px 28px;\
background-color:rgba(245,158,11,0.05);\
border-bottom:1px solid rgba(245,158,11,0.1);">
        <p style="margin:0;font-size:11px;font-weight:700;\
color:#f59e0b;text-transform:uppercase;\
letter-spacing:2px;">
          UPCOMING OPPORTUNITIES
        </p>
      </td></tr>
      <tr><td style="padding:16px 28px 20px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               border="0">
          {items}
        </table>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def _render_newsletter(briefing: DailyBriefing) -> str:
    if not briefing.newsletter_topics:
        return ""

    items = ""
    for topic in briefing.newsletter_topics:
        items += f"""
        <tr><td style="padding:4px 0;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="24" valign="top"
                  style="font-size:14px;color:#ef4444;">
                ⚠
              </td>
              <td style="font-size:13px;\
color:rgba(255,255,255,0.55);line-height:1.6;">
                {topic}
              </td>
            </tr>
          </table>
        </td></tr>"""

    return f"""
<table width="640" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td style="background-color:#1a1a24;border-radius:16px;\
overflow:hidden;border:1px solid rgba(239,68,68,0.2);">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:18px 28px 10px 28px;\
background-color:rgba(239,68,68,0.06);\
border-bottom:1px solid rgba(239,68,68,0.12);">
        <p style="margin:0;font-size:11px;font-weight:700;\
color:#ef4444;text-transform:uppercase;\
letter-spacing:2px;">
          NEWSLETTER AGENT &mdash; ACTION REQUIRED
        </p>
        <p style="margin:4px 0 0 0;font-size:12px;\
color:rgba(255,255,255,0.4);">
          Run the newsletter agent with these search terms \
to fill content gaps
        </p>
      </td></tr>
      <tr><td style="padding:16px 28px 20px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               border="0">
          {items}
        </table>
      </td></tr>
    </table>
  </td></tr>
</table>"""
