"""HTML email templates for daily briefings."""

from __future__ import annotations

from planner_agent.models import DailyBriefing, Phase

PHASE_LABELS = {
    Phase.LEARN: ("Learn", "#3b82f6", "Study & absorb"),
    Phase.PRACTICE: ("Practice", "#f59e0b", "Hands-on labs & exercises"),
    Phase.PRODUCE: ("Produce", "#10b981", "Ship publicly visible work"),
}

PRIORITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#3b82f6",
    "low": "#6b7280",
}


def render_briefing_html(briefing: DailyBriefing) -> str:
    phase_label, phase_color, phase_desc = PHASE_LABELS.get(
        briefing.focus_phase, ("Learn", "#3b82f6", "")
    )

    tasks_html = ""
    for i, task in enumerate(briefing.tasks, 1):
        p_color = PRIORITY_COLORS.get(task.priority, "#6b7280")
        url_html = ""
        if task.resource_url:
            url_html = (
                f'<a href="{task.resource_url}" '
                f'style="color:#3b82f6;text-decoration:none;font-size:13px;">'
                f'{task.resource_name or task.resource_url}</a><br>'
            )

        tasks_html += f"""
        <tr>
          <td style="padding:16px 20px;border-bottom:1px solid #e5e7eb;">
            <div style="display:flex;align-items:flex-start;gap:12px;">
              <div style="min-width:28px;height:28px;border-radius:50%;
                          background:{p_color}15;color:{p_color};
                          display:flex;align-items:center;justify-content:center;
                          font-weight:700;font-size:14px;">{i}</div>
              <div style="flex:1;">
                <div style="font-weight:600;font-size:15px;color:#111827;margin-bottom:4px;">
                  {task.title}
                </div>
                <div style="font-size:13px;color:#4b5563;margin-bottom:6px;">
                  {task.description}
                </div>
                {url_html}
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">
                  <span style="background:{p_color}15;color:{p_color};
                               padding:2px 8px;border-radius:10px;font-weight:500;">
                    {task.priority.upper()}
                  </span>
                  &nbsp;&middot;&nbsp; {task.estimated_hours}h
                  &nbsp;&middot;&nbsp; {task.track}
                  &nbsp;&middot;&nbsp; {task.phase}
                </div>
                <div style="font-size:12px;color:#9ca3af;margin-top:4px;font-style:italic;">
                  {task.why}
                </div>
              </div>
            </div>
          </td>
        </tr>"""

    gaps_html = ""
    if briefing.portfolio_gaps:
        items = "".join(
            f'<li style="color:#dc2626;font-size:13px;margin-bottom:4px;">{g}</li>'
            for g in briefing.portfolio_gaps
        )
        gaps_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
          <tr><td style="padding:12px 20px;background:#fef2f2;border-left:4px solid #ef4444;">
            <div style="font-weight:600;font-size:14px;color:#991b1b;margin-bottom:8px;">
              Portfolio Gaps</div>
            <ul style="margin:0;padding-left:20px;">{items}</ul>
          </td></tr>
        </table>"""

    observations_html = ""
    if briefing.skill_observations:
        items = "".join(
            f'<li style="font-size:13px;color:#4b5563;margin-bottom:4px;">{o}</li>'
            for o in briefing.skill_observations
        )
        observations_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
          <tr><td style="padding:12px 20px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            <div style="font-weight:600;font-size:14px;color:#1e40af;margin-bottom:8px;">
              Observations</div>
            <ul style="margin:0;padding-left:20px;">{items}</ul>
          </td></tr>
        </table>"""

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,
  BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:20px;">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:12px;overflow:hidden;
              box-shadow:0 1px 3px rgba(0,0,0,0.1);">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1e293b,#334155);
                 padding:24px 20px;text-align:center;">
    <div style="font-size:22px;font-weight:700;color:#ffffff;">
      Daily Briefing &middot; {briefing.date}</div>
    <div style="font-size:14px;color:#94a3b8;margin-top:4px;">
      Focus: {briefing.focus_track}
      &nbsp;&middot;&nbsp;
      <span style="background:{phase_color};color:#fff;padding:2px 10px;
                   border-radius:10px;font-size:12px;font-weight:600;">
        {phase_label.upper()}</span>
    </div>
  </td></tr>

  <!-- Rationale -->
  <tr><td style="padding:16px 20px;background:#f8fafc;border-bottom:1px solid #e5e7eb;">
    <div style="font-size:13px;color:#475569;">{briefing.focus_rationale}</div>
    <div style="font-size:13px;color:#64748b;margin-top:4px;">
      Total: {briefing.total_estimated_hours}h planned</div>
  </td></tr>

  <!-- Tasks -->
  {tasks_html}

</table>

{gaps_html}
{observations_html}

<!-- Reply CTA -->
<table width="600" cellpadding="0" cellspacing="0" style="margin-top:20px;">
  <tr><td style="padding:16px 20px;background:#f0fdf4;border-radius:8px;
                 border:1px solid #bbf7d0;text-align:center;">
    <div style="font-size:14px;color:#166534;font-weight:600;">
      Reply to this email with your progress</div>
    <div style="font-size:12px;color:#4ade80;margin-top:4px;">
      Example: "Done 1 and 2. Skipped 3. Spent 4 hours total."</div>
  </td></tr>
</table>

</td></tr></table>
</body>
</html>"""
