"""IMAP email receiver — polls inbox for replies to planner briefings."""

from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

from planner_agent.config import IMAPConfig

logger = logging.getLogger(__name__)

SUBJECT_PATTERN = re.compile(r"\[Planner\]")


class EmailReceiver:
    def __init__(self, config: IMAPConfig):
        self.config = config

    def fetch_replies(self, since_date: str | None = None) -> list[dict]:
        """
        Connect to IMAP, find replies to planner briefing emails.

        Args:
            since_date: Only fetch emails since this date (YYYY-MM-DD).
                        If None, fetches from last 2 days.

        Returns:
            List of dicts with keys: subject, body, date, message_id, in_reply_to
        """
        if not self.config.email or not self.config.password:
            logger.warning("IMAP credentials not configured")
            return []

        try:
            conn = imaplib.IMAP4_SSL(self.config.server, self.config.port)
            conn.login(self.config.email, self.config.password)
            conn.select(self.config.mailbox)
        except Exception:
            logger.error("IMAP connection failed", exc_info=True)
            return []

        try:
            search_criteria = _build_search(since_date)
            _, message_nums = conn.search(None, *search_criteria)

            if not message_nums or not message_nums[0]:
                logger.info("No matching emails found")
                return []

            replies = []
            for num in message_nums[0].split():
                _, msg_data = conn.fetch(num, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue

                raw = msg_data[0]
                if isinstance(raw, tuple):
                    raw_email = raw[1]
                else:
                    continue

                msg = email.message_from_bytes(raw_email)
                subject = _decode_subject(msg.get("Subject", ""))

                if not SUBJECT_PATTERN.search(subject):
                    continue

                body = _extract_body(msg)
                if not body:
                    continue

                date_str = msg.get("Date", "")
                try:
                    msg_date = parsedate_to_datetime(date_str).isoformat()
                except Exception:
                    msg_date = ""

                replies.append({
                    "subject": subject,
                    "body": body,
                    "date": msg_date,
                    "message_id": msg.get("Message-ID", ""),
                    "in_reply_to": msg.get("In-Reply-To", ""),
                })

            logger.info("Found %d planner reply emails", len(replies))
            return replies

        finally:
            try:
                conn.close()
                conn.logout()
            except Exception:
                pass


def _build_search(since_date: str | None) -> list[str]:
    """Build IMAP search criteria."""
    criteria = ['SUBJECT "[Planner]"']
    if since_date:
        from datetime import datetime
        dt = datetime.fromisoformat(since_date)
        imap_date = dt.strftime("%d-%b-%Y")
        criteria.append(f'SINCE {imap_date}')
    else:
        criteria.append('SINCE "1-Jan-2020"')
    return criteria


def _decode_subject(subject: str) -> str:
    """Decode email subject header."""
    decoded_parts = decode_header(subject)
    parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return " ".join(parts)


def _extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from email, stripping quoted content."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    # Strip quoted reply content (lines starting with >)
    lines = body.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if stripped.startswith("On ") and stripped.endswith("wrote:"):
            break
        if stripped == "-- ":
            break
        clean_lines.append(line)

    return "\n".join(clean_lines).strip()
