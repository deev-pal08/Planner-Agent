"""HTML email templates for daily briefings."""

from __future__ import annotations

from planner_agent.models import DailyBriefing, Phase

PHASE_LABELS = {
    Phase.LEARN: ("LEARN", "#6366f1", "#eef2ff"),
    Phase.PRACTICE: ("PRACTICE", "#d97706", "#fffbeb"),
    Phase.PRODUCE: ("PRODUCE", "#059669", "#ecfdf5"),
}

PRIORITY_STYLES = {
    "critical": ("#dc2626", "#fef2f2", "#991b1b"),
    "high": ("#ea580c", "#fff7ed", "#9a3412"),
    "medium": ("#2563eb", "#eff6ff", "#1e40af"),
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


def render_briefing_html(briefing: DailyBriefing) -> str:
    phase_label, phase_color, phase_bg = PHASE_LABELS.get(
        briefing.focus_phase, ("LEARN", "#6366f1", "#eef2ff")
    )

    tasks_html = _render_tasks(briefing)
    newsletter_reading_html = _render_newsletter_reading(briefing)
    gaps_html = _render_gaps(briefing)
    observations_html = _render_observations(briefing)
    newsletter_html = _render_newsletter(briefing)

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  -webkit-font-smoothing:antialiased;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;">
<tr><td align="center" style="padding:32px 16px;">

<!-- Main Container -->
<table width="600" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#ffffff;border-radius:16px;overflow:hidden;
              box-shadow:0 4px 6px -1px rgba(0,0,0,0.07),0 2px 4px -2px rgba(0,0,0,0.05);">

  <!-- Header -->
  <tr><td style="background-color:#0f172a;padding:0;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:32px 32px 16px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="font-size:13px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1.5px;">
              DAILY BRIEFING
            </td>
            <td align="right" style="font-size:13px;color:#64748b;">
              {briefing.total_estimated_hours}h planned
            </td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 32px 8px 32px;">
        <span style="font-size:28px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">
          {briefing.date}
        </span>
      </td></tr>
      <tr><td style="padding:0 32px 28px 32px;">
        <table cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding-right:12px;">
              <span style="display:inline-block;background-color:{phase_color};color:#ffffff;
                           font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;
                           letter-spacing:0.5px;">
                {phase_label}
              </span>
            </td>
            <td style="font-size:14px;color:#cbd5e1;">
              {briefing.focus_track.replace('_', ' ').title()}
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </td></tr>

  <!-- Rationale -->
  <tr><td style="padding:20px 32px;background-color:#f8fafc;border-bottom:1px solid #e2e8f0;">
    <p style="margin:0;font-size:14px;line-height:1.6;color:#475569;">
      {briefing.focus_rationale}
    </p>
  </td></tr>

  <!-- Tasks Header -->
  <tr><td style="padding:24px 32px 12px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.5px;">
          TODAY'S TASKS
        </td>
        <td align="right" style="font-size:12px;color:#94a3b8;">
          {len(briefing.tasks)} tasks
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- Tasks -->
  {tasks_html}

  <!-- Newsletter Reading -->
  {newsletter_reading_html}

  <!-- Spacer -->
  <tr><td style="padding:8px;"></td></tr>

</table>

{gaps_html}
{observations_html}
{newsletter_html}

<!-- Reply CTA -->
<table width="600" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
  <tr><td style="padding:20px 32px;background-color:#ffffff;border-radius:12px;
                 border:2px dashed #d1d5db;text-align:center;">
    <p style="margin:0 0 6px 0;font-size:15px;color:#1f2937;font-weight:600;">
      ✉️ Reply to update your progress
    </p>
    <p style="margin:0;font-size:13px;color:#9ca3af;line-height:1.5;">
      Just reply naturally: "Done 1 and 2. Skipped 3 — too tired. Spent 3 hours total."
    </p>
  </td></tr>
</table>

<!-- Footer -->
<table width="600" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
  <tr><td align="center" style="padding:12px;">
    <p style="margin:0;font-size:11px;color:#94a3b8;">
      Planner Agent &middot; Adaptive Daily Task Orchestrator
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
        color, bg, text_color = PRIORITY_STYLES.get(
            task.priority, ("#6b7280", "#f9fafb", "#374151")
        )
        icon = TASK_TYPE_ICONS.get(task.task_type, "⭐")

        resource_html = ""
        if task.resource_url:
            name = task.resource_name or task.resource_url
            if len(name) > 70:
                name = name[:67] + "..."
            resource_html = f"""
            <tr><td style="padding:8px 0 0 0;">
              <table cellpadding="0" cellspacing="0" border="0"
                     style="background-color:#f8fafc;border-radius:8px;width:100%;">
                <tr><td style="padding:10px 14px;">
                  <a href="{task.resource_url}"
                     style="color:#2563eb;font-size:13px;font-weight:500;text-decoration:none;">
                    \U0001f517 {name}
                  </a>
                </td></tr>
              </table>
            </td></tr>"""

        why_html = ""
        if task.why:
            why_html = f"""
            <tr><td style="padding:8px 0 0 0;">
              <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.5;font-style:italic;">
                \U0001f4a1 {task.why}
              </p>
            </td></tr>"""

        html += f"""
  <tr><td style="padding:4px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background-color:#ffffff;border:1px solid #e5e7eb;border-radius:12px;
                  border-left:4px solid {color};">
      <tr><td style="padding:20px;">

        <!-- Task Number + Priority -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="40" valign="top">
              <div style="width:32px;height:32px;border-radius:8px;background-color:{bg};
                          color:{text_color};font-size:15px;font-weight:800;line-height:32px;
                          text-align:center;">
                {i}
              </div>
            </td>
            <td style="padding-left:8px;" valign="top">
              <p style="margin:0 0 2px 0;font-size:15px;font-weight:700;color:#111827;line-height:1.4;">
                {task.title}
              </p>
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:6px;">
                    <span style="display:inline-block;background-color:{bg};color:{text_color};
                                 font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;
                                 text-transform:uppercase;letter-spacing:0.5px;">
                      {task.priority.upper()}
                    </span>
                  </td>
                  <td style="padding-right:6px;">
                    <span style="font-size:12px;color:#6b7280;">{icon} {task.task_type.replace('_', ' ').title()}</span>
                  </td>
                  <td style="padding-right:6px;">
                    <span style="font-size:12px;color:#6b7280;">⏱ {task.estimated_hours}h</span>
                  </td>
                  <td>
                    <span style="font-size:12px;color:#6b7280;">{task.track.replace('_', ' ').title()}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- Description -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;">
          <tr><td>
            <p style="margin:0;font-size:13px;color:#4b5563;line-height:1.65;">
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
        "CRITICAL": ("#dc2626", "#fef2f2"),
        "IMPORTANT": ("#ea580c", "#fff7ed"),
        "INTERESTING": ("#2563eb", "#eff6ff"),
        "REFERENCE": ("#6b7280", "#f9fafb"),
    }

    articles_html = ""
    for article in nr.articles:
        color, bg = priority_colors.get(article.priority, ("#6b7280", "#f9fafb"))
        why_html = ""
        if article.why:
            why_html = f"""
                  <p style="margin:6px 0 0 0;font-size:12px;color:#6b7280;line-height:1.5;font-style:italic;">
                    {article.why}
                  </p>"""

        articles_html += f"""
            <tr><td style="padding:5px 0;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background-color:#fafafa;border-radius:8px;border:1px solid #e5e7eb;">
                <tr><td style="padding:12px 14px;">
                  <span style="display:inline-block;background-color:{bg};color:{color};
                               font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;
                               text-transform:uppercase;letter-spacing:0.5px;">
                    {article.priority}
                  </span>
                  <p style="margin:8px 0 0 0;font-size:13px;line-height:1.4;">
                    <a href="{article.url}" style="color:#1e40af;font-weight:600;text-decoration:none;">
                      {article.title}
                    </a>
                  </p>{why_html}
                </td></tr>
              </table>
            </td></tr>"""

    return f"""
  <tr><td style="padding:12px 32px 4px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background-color:#ffffff;border:1px solid #c4b5fd;border-radius:12px;
                  border-left:4px solid #7c3aed;">
      <tr><td style="padding:20px;">

        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="40" valign="top">
              <div style="width:32px;height:32px;border-radius:8px;background-color:#f5f3ff;
                          color:#5b21b6;font-size:15px;font-weight:800;line-height:32px;
                          text-align:center;">
                {task_num}
              </div>
            </td>
            <td style="padding-left:8px;" valign="top">
              <p style="margin:0 0 2px 0;font-size:15px;font-weight:700;color:#111827;line-height:1.4;">
                {nr.title}
              </p>
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:6px;">
                    <span style="display:inline-block;background-color:#f5f3ff;color:#5b21b6;
                                 font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;
                                 text-transform:uppercase;letter-spacing:0.5px;">NEWSLETTER</span>
                  </td>
                  <td style="padding-right:6px;">
                    <span style="font-size:12px;color:#6b7280;">\U0001f4f0 {len(nr.articles)} articles</span>
                  </td>
                  <td>
                    <span style="font-size:12px;color:#6b7280;">⏱ {nr.estimated_hours}h</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;">
          <tr><td>
            <p style="margin:0 0 10px 0;font-size:13px;color:#4b5563;line-height:1.65;">
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
              <td width="20" valign="top" style="font-size:13px;color:#dc2626;">⚠</td>
              <td style="font-size:13px;color:#7f1d1d;line-height:1.5;">{gap}</td>
            </tr>
          </table>
        </td></tr>"""

    return f"""
<table width="600" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
  <tr><td style="background-color:#ffffff;border-radius:12px;overflow:hidden;
                 border:1px solid #fecaca;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:16px 24px 8px 24px;background-color:#fef2f2;border-bottom:1px solid #fecaca;">
        <p style="margin:0;font-size:11px;font-weight:700;color:#991b1b;text-transform:uppercase;letter-spacing:1.5px;">
          \U0001f6a8 Portfolio Gaps
        </p>
      </td></tr>
      <tr><td style="padding:12px 24px 16px 24px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
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
              <td width="20" valign="top" style="font-size:13px;color:#2563eb;">•</td>
              <td style="font-size:13px;color:#334155;line-height:1.5;">{obs}</td>
            </tr>
          </table>
        </td></tr>"""

    return f"""
<table width="600" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
  <tr><td style="background-color:#ffffff;border-radius:12px;overflow:hidden;
                 border:1px solid #bfdbfe;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:16px 24px 8px 24px;background-color:#eff6ff;border-bottom:1px solid #bfdbfe;">
        <p style="margin:0;font-size:11px;font-weight:700;color:#1e40af;text-transform:uppercase;letter-spacing:1.5px;">
          \U0001f4ca Observations
        </p>
      </td></tr>
      <tr><td style="padding:12px 24px 16px 24px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
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
              <td width="20" valign="top" style="font-size:13px;color:#dc2626;">⚠</td>
              <td style="font-size:13px;color:#7f1d1d;line-height:1.5;">{topic}</td>
            </tr>
          </table>
        </td></tr>"""

    return f"""
<table width="600" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
  <tr><td style="background-color:#ffffff;border-radius:12px;overflow:hidden;
                 border:1px solid #fecaca;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:16px 24px 8px 24px;background-color:#fef2f2;border-bottom:1px solid #fecaca;">
        <p style="margin:0;font-size:11px;font-weight:700;color:#991b1b;text-transform:uppercase;letter-spacing:1.5px;">
          \U0001f4ec Newsletter Agent — Action Required
        </p>
        <p style="margin:4px 0 0 0;font-size:12px;color:#b91c1c;">
          Run the newsletter agent with these search terms to fill content gaps
        </p>
      </td></tr>
      <tr><td style="padding:12px 24px 16px 24px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          {items}
        </table>
      </td></tr>
    </table>
  </td></tr>
</table>"""
