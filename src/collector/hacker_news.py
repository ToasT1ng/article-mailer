import asyncio
import re
from datetime import datetime, timezone

import httpx
import structlog
from bs4 import BeautifulSoup

from src.collector.base import AbstractCollector, Article

log = structlog.get_logger()

HN_TOP_STORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

AI_KEYWORDS = re.compile(
    r"\b(AI|LLM|GPT|ML|model|neural|machine learning|deep learning|"
    r"language model|diffusion|transformer|OpenAI|Anthropic|Gemini|Claude|"
    r"AGI|inference|fine.?tun|embedding|RAG|vector)\b",
    re.IGNORECASE,
)

MIN_SCORE = 100
MAX_AGE_SECONDS = 86400  # 24시간


class HackerNewsCollector(AbstractCollector):
    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    async def fetch(self) -> list[Article]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(HN_TOP_STORIES)
                resp.raise_for_status()
                story_ids: list[int] = resp.json()[:200]
            except Exception:
                log.exception("hacker_news.top_stories.failed")
                return []

            tasks = [self._fetch_item(client, sid) for sid in story_ids]
            items = await asyncio.gather(*tasks, return_exceptions=True)

        articles: list[Article] = []
        now_ts = datetime.now(timezone.utc).timestamp()

        for item in items:
            if isinstance(item, Exception) or item is None:
                continue
            if not self._is_ai_article(item, now_ts):
                continue
            articles.append(self._to_article(item))

        log.info("hacker_news.fetched", count=len(articles))
        return articles

    async def _fetch_item(self, client: httpx.AsyncClient, item_id: int) -> dict | None:
        try:
            resp = await client.get(HN_ITEM.format(id=item_id))
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def _is_ai_article(self, item: dict, now_ts: float) -> bool:
        if item.get("type") != "story":
            return False
        if item.get("score", 0) < MIN_SCORE:
            return False
        title = item.get("title", "")
        if not AI_KEYWORDS.search(title):
            return False
        time_posted = item.get("time", 0)
        if now_ts - time_posted > MAX_AGE_SECONDS:
            return False
        url = item.get("url", "")
        if not url:  # Ask HN 등 외부 링크 없는 글 제외
            return False
        return True

    def _to_article(self, item: dict) -> Article:
        return Article(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source="Hacker News",
            published_at=datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc),
            fallback_description=item.get("title", ""),
        )


async def crawl_article_content(url: str, timeout: float = 10.0) -> str | None:
    """URL에서 본문 텍스트를 크롤링한다. 실패 시 None 반환."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; article-mailer/1.0)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            # script/style 제거
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return text[:8000] if text else None
    except Exception:
        log.debug("crawl.failed", url=url)
        return None
