"""Summarizer 테스트."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.collector.base import Article
from src.summarizer import Summarizer, compute_category_counts


class TestComputeCategoryCounts:
    def test_five_articles(self):
        assert compute_category_counts(5) == (1, 4)

    def test_ten_articles(self):
        assert compute_category_counts(10) == (2, 8)

    def test_one_article(self):
        assert compute_category_counts(1) == (1, 0)

    def test_three_articles(self):
        assert compute_category_counts(3) == (1, 2)


class TestParseJsonArray:
    def test_clean_array(self, test_settings):
        summarizer = Summarizer(test_settings)
        raw = json.dumps([{"index": 0, "category": "impact"}, {"index": 1, "category": "trend"}])
        result = summarizer._parse_json_array(raw)
        assert len(result) == 2
        assert result[0]["index"] == 0

    def test_array_in_code_block(self, test_settings):
        summarizer = Summarizer(test_settings)
        raw = '```json\n[{"index": 0, "category": "trend"}]\n```'
        result = summarizer._parse_json_array(raw)
        assert len(result) == 1


class TestBuildSummaries:
    def test_builds_from_valid_data(self, test_settings, sample_article):
        summarizer = Summarizer(test_settings)
        articles = [sample_article]
        data = [
            {
                "index": 0,
                "category": "impact",
                "one_liner": "GPT-5 출시",
                "body": "본문 요약",
                "importance": "상",
                "read_time_min": 4,
            }
        ]
        summaries = summarizer._build_summaries(data, articles, n=1)
        assert len(summaries) == 1
        assert summaries[0].importance == "상"
        assert summaries[0].article.category == "impact"

    def test_skips_invalid_index(self, test_settings, sample_article):
        summarizer = Summarizer(test_settings)
        data = [{"index": 99, "category": "trend", "one_liner": "x", "body": "y"}]
        summaries = summarizer._build_summaries(data, [sample_article], n=1)
        assert len(summaries) == 0

    def test_limits_to_n(self, test_settings):
        from datetime import datetime, timezone

        summarizer = Summarizer(test_settings)
        articles = [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]
        data = [
            {"index": i, "category": "trend", "one_liner": "x", "body": "y"}
            for i in range(5)
        ]
        summaries = summarizer._build_summaries(data, articles, n=2)
        assert len(summaries) == 2


def _make_gemini_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.usage_metadata = MagicMock(total_token_count=100)
    return response


class TestScreeningPoolSize:
    def test_one_article(self, test_settings):
        s = Summarizer(test_settings)
        assert s._screening_pool_size(1) == 4

    def test_five_articles(self, test_settings):
        s = Summarizer(test_settings)
        assert s._screening_pool_size(5) == 20

    def test_capped_at_max(self, test_settings):
        s = Summarizer(test_settings)
        assert s._screening_pool_size(10) == 20


class TestScreen:
    @pytest.mark.asyncio
    async def test_screen_skips_when_small_pool(self, test_settings):
        from datetime import datetime, timezone

        articles = [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]
        summarizer = Summarizer(test_settings)
        result = await summarizer.screen(articles, n=5)
        assert result == articles

    @pytest.mark.asyncio
    async def test_screen_calls_gemini(self, test_settings):
        from datetime import datetime, timezone

        articles = [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at=datetime.now(timezone.utc),
                fallback_description=f"Desc {i}",
            )
            for i in range(25)
        ]

        response_data = [{"index": i, "category": "trend"} for i in range(20)]
        mock_response = _make_gemini_response(json.dumps(response_data))

        summarizer = Summarizer(test_settings)
        summarizer._client = MagicMock()
        summarizer._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        result = await summarizer.screen(articles, n=5)
        assert len(result) == 20


class TestSelectAndSummarize:
    @pytest.mark.asyncio
    async def test_returns_summaries(self, test_settings):
        from datetime import datetime, timezone

        articles = [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at=datetime.now(timezone.utc),
                fallback_description=f"Desc {i}",
            )
            for i in range(5)
        ]

        response_data = [
            {
                "index": 0,
                "category": "impact",
                "one_liner": "임팩트 요약",
                "body": "본문",
                "importance": "상",
                "read_time_min": 3,
            },
            {
                "index": 1,
                "category": "trend",
                "one_liner": "트렌드 요약",
                "body": "본문",
                "importance": "중",
                "read_time_min": 2,
            },
        ]
        mock_response = _make_gemini_response(json.dumps(response_data))

        summarizer = Summarizer(test_settings)
        summarizer._client = MagicMock()
        summarizer._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        summaries = await summarizer.select_and_summarize(articles, n=2)
        assert len(summaries) == 2
        assert summaries[0].article.category == "impact"
        assert summaries[1].article.category == "trend"

    @pytest.mark.asyncio
    async def test_empty_articles(self, test_settings):
        summarizer = Summarizer(test_settings)
        result = await summarizer.select_and_summarize([], n=5)
        assert result == []
