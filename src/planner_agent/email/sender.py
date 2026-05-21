"""Send daily briefing emails via Resend."""

from __future__ import annotations

import logging

import resend

from planner_agent.email.templates import render_briefing_html
from planner_agent.models import DailyBriefing

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, api_key: str, from_address: str, to_addresses: list[str]):
        resend.api_key = api_key
        self.from_address = from_address
        self.to_addresses = to_addresses

    def send_briefing(self, briefing: DailyBriefing) -> str:
        """Send the daily briefing email. Returns the Resend message ID."""
        html = render_briefing_html(briefing)
        subject = f"[Planner] {briefing.date} — Focus: {briefing.focus_track} ({briefing.focus_phase.upper()})"

        params: resend.Emails.SendParams = {
            "from": self.from_address,
            "to": self.to_addresses,
            "subject": subject,
            "html": html,
            "headers": {
                "X-Planner-Date": briefing.date,
                "X-Planner-Track": briefing.focus_track,
            },
        }

        response = resend.Emails.send(params)
        message_id = response.get("id", "") if isinstance(response, dict) else ""
        logger.info("Briefing email sent: %s (message_id=%s)", subject, message_id)
        return message_id
