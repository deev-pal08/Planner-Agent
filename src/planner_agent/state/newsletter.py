"""Read-only interface to the Newsletter Agent's SQLite database."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    "CRITICAL - ACT NOW": 0,
    "IMPORTANT - READ THIS WEEK": 1,
    "INTERESTING - QUEUE FOR WEEKEND": 2,
    "REFERENCE - SAVE FOR LATER": 3,
}

PRIORITY_SHORT = {
    "CRITICAL - ACT NOW": "CRITICAL",
    "IMPORTANT - READ THIS WEEK": "IMPORTANT",
    "INTERESTING - QUEUE FOR WEEKEND": "INTERESTING",
    "REFERENCE - SAVE FOR LATER": "REFERENCE",
}

DEFAULT_LIMITS = {
    "CRITICAL": 15,
    "IMPORTANT": 20,
    "INTERESTING": 15,
    "REFERENCE": 10,
}


class NewsletterReader:
    """Read-only access to the Newsletter Agent's article database."""

    def __init__(self, project_dir: str):
        expanded = os.path.expanduser(project_dir)
        self.db_path = Path(expanded) / "data" / "newsletter.db"
        self._conn: sqlite3.Connection | None = None

        if self.is_available():
            try:
                self._conn = sqlite3.connect(
                    f"file:{self.db_path}?mode=ro", uri=True,
                )
                self._conn.row_factory = sqlite3.Row
            except (sqlite3.OperationalError, PermissionError):
                logger.warning("Cannot open newsletter DB at %s", self.db_path)
                self._conn = None

    def is_available(self) -> bool:
        try:
            return self.db_path.exists()
        except PermissionError:
            return False

    def get_db_age_days(self) -> float | None:
        if not self._conn:
            return None
        try:
            mtime = os.path.getmtime(self.db_path)
        except (OSError, PermissionError):
            return None
        age_seconds = datetime.now(UTC).timestamp() - mtime
        return age_seconds / 86400

    def get_article_count(self) -> int:
        if not self._conn:
            return 0
        articles = self._load_all_articles()
        return len(articles)

    def get_articles_by_priority(
        self,
        exclude_urls: set[str],
        limit_per_priority: dict[str, int] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        if not self._conn:
            return {}

        limits = limit_per_priority or DEFAULT_LIMITS
        all_articles = self._load_all_articles()

        unread: dict[str, list[dict[str, Any]]] = {
            "CRITICAL": [],
            "IMPORTANT": [],
            "INTERESTING": [],
            "REFERENCE": [],
        }

        for article in all_articles:
            url = article.get("url", "")
            if not url or url in exclude_urls:
                continue

            raw_priority = article.get("priority", "REFERENCE - SAVE FOR LATER")
            short = PRIORITY_SHORT.get(raw_priority, "REFERENCE")

            if short not in unread:
                continue

            unread[short].append({
                "title": article.get("title", ""),
                "url": url,
                "source_name": article.get("source_name", ""),
                "priority": short,
                "tags": article.get("tags", []),
                "ai_summary": (article.get("ai_summary", "") or "")[:150],
                "published_at": article.get("published_at", ""),
                "score": article.get("score"),
            })

        for tier, cap in limits.items():
            if tier in unread:
                unread[tier] = unread[tier][:cap]

        return unread

    def _load_all_articles(self) -> list[dict[str, Any]]:
        if not self._conn:
            return []

        rows = self._conn.execute(
            "SELECT articles_json FROM digests WHERE articles_json IS NOT NULL",
        ).fetchall()

        seen_urls: set[str] = set()
        articles: list[dict[str, Any]] = []

        for row in rows:
            try:
                batch = json.loads(row["articles_json"])
                if not isinstance(batch, list):
                    continue
                for article in batch:
                    url = article.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        articles.append(article)
            except (json.JSONDecodeError, TypeError):
                continue

        articles.sort(
            key=lambda a: PRIORITY_ORDER.get(
                a.get("priority", "REFERENCE - SAVE FOR LATER"), 3,
            ),
        )

        return articles

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
