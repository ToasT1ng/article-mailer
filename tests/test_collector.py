"""Collector 테스트."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.collector.base import Article
from src.collector.hacker_news import HackerNewsCollector, crawl_article_content
from src.collector.rss import RSSCollector


class TestHackerNewsCollector:
    @pytest.mark.asyncio
    async def test_fetch_filters_ai_articles(self, httpx_mock):
        """점수 높고 AI 키워드 있는 24시간 이내 글만 수집."""
        import time

        now_ts = int(time.time())
        story_ids = [1, 2, 3]

        items = {
            1: {
                "id": 1,
                "type": "story",
                "title": "New LLM model beats GPT-4",
                "url": "https://example.com/llm",
                "score": 200,
                "time": now_ts - 3600,  # 1시간 전
            },
            2: {
                "id": 2,
                "type": "story",
                "title": "Ask HN: Best coffee shops in SF",
                "url": "https://example.com/coffee",
                "score": 50,  # 점수 낮음 → 필터
                "time": now_ts - 3600,
            },
            3: {
                "id": 3,
                "type": "story",
                "title": "Neural network paper published",
                "url": "https://example.com/neural",
                "score": 150,
                "time": now_ts - 3600,
            },
        }

        httpx_mock.add_response(
            url="https://hacker-news.firebaseio.com/v0/topstories.json",
            json=story_ids,
        )
        for item_id, item in items.items():
            httpx_mock.add_response(
                url=f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                json=item,
            )

        collector = HackerNewsCollector()
        articles = await collector.fetch()

        assert len(articles) == 2
        urls = {a.url for a in articles}
        assert "https://example.com/llm" in urls
        assert "https://example.com/neural" in urls
        assert "https://example.com/coffee" not in urls

    @pytest.mark.asyncio
    async def test_fetch_skips_old_articles(self, httpx_mock):
        """24시간 이전 글은 제외."""
        import time

        old_ts = int(time.time()) - 90000  # 25시간 전
        story_ids = [99]
        httpx_mock.add_response(
            url="https://hacker-news.firebaseio.com/v0/topstories.json",
            json=story_ids,
        )
        httpx_mock.add_response(
            url="https://hacker-news.firebaseio.com/v0/item/99.json",
            json={
                "id": 99,
                "type": "story",
                "title": "AI breakthrough announced",
                "url": "https://example.com/old",
                "score": 300,
                "time": old_ts,
            },
        )

        collector = HackerNewsCollector()
        articles = await collector.fetch()
        assert articles == []

    @pytest.mark.asyncio
    async def test_fetch_handles_api_failure(self, httpx_mock):
        """API 실패 시 빈 목록 반환."""
        httpx_mock.add_exception(
            Exception("Connection refused"),
            url="https://hacker-news.firebaseio.com/v0/topstories.json",
        )
        collector = HackerNewsCollector()
        articles = await collector.fetch()
        assert articles == []


class TestArticleContentForSummary:
    def test_uses_raw_content_when_available(self):
        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at=datetime.now(timezone.utc),
            raw_content="Full article content here.",
            fallback_description="Short description.",
        )
        assert article.content_for_summary() == "Full article content here."

    def test_falls_back_to_description(self):
        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at=datetime.now(timezone.utc),
            raw_content=None,
            fallback_description="Short description.",
        )
        assert article.content_for_summary() == "Short description."

    def test_truncates_long_content(self):
        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at=datetime.now(timezone.utc),
            raw_content="A" * 5000,
        )
        assert len(article.content_for_summary()) == 4000


class TestRSSCollector:
    @pytest.mark.asyncio
    async def test_fetch_returns_articles(self):
        """RSS 파싱 결과가 Article 목록으로 변환되는지 확인."""
        mock_entry = MagicMock()
        mock_entry.link = "https://arxiv.org/abs/2501.00001"
        mock_entry.title = "Advances in Large Language Models"
        mock_entry.summary = "We present advances in LLMs."
        mock_entry.published_parsed = (2026, 4, 14, 8, 0, 0, 0, 0, 0)

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("feedparser.parse", return_value=mock_feed):
            collector = RSSCollector(
                sources=[("ArXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI")]
            )
            articles = await collector.fetch()

        assert len(articles) == 1
        assert articles[0].title == "Advances in Large Language Models"
        assert articles[0].source == "ArXiv cs.AI"

    @pytest.mark.asyncio
    async def test_fetch_skips_failed_source(self):
        """특정 소스 실패 시 해당 소스만 스킵."""
        with patch("feedparser.parse", side_effect=Exception("Network error")):
            collector = RSSCollector(
                sources=[("Bad Source", "https://bad.example.com/rss")]
            )
            articles = await collector.fetch()

        assert articles == []
