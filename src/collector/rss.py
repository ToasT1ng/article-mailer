from datetime import datetime, timezone

import feedparser
import structlog

from src.collector.base import AbstractCollector, Article

log = structlog.get_logger()

# (이름, URL) 목록 — 우선순위 순
RSS_SOURCES: list[tuple[str, str]] = [
    ("ArXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("The Batch", "https://www.deeplearning.ai/the-batch/feed/"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
]


def _parse_published(entry: feedparser.FeedParserDict) -> datetime:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


class RSSCollector(AbstractCollector):
    """범용 RSS 수집기. sources 목록을 순회하며 아티클을 수집한다."""

    def __init__(self, sources: list[tuple[str, str]] | None = None) -> None:
        self._sources = sources if sources is not None else RSS_SOURCES

    async def fetch(self) -> list[Article]:
        articles: list[Article] = []
        for source_name, url in self._sources:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    link = getattr(entry, "link", None)
                    title = getattr(entry, "title", "")
                    if not link or not title:
                        continue
                    description = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    articles.append(
                        Article(
                            title=title,
                            url=link,
                            source=source_name,
                            published_at=_parse_published(entry),
                            fallback_description=description[:1000] if description else "",
                        )
                    )
                log.info("rss.fetched", source=source_name, count=len(feed.entries))
            except Exception:
                log.exception("rss.failed", source=source_name, url=url)

        return articles
