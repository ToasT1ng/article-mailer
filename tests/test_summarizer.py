"""Summarizer 테스트."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.collector.base import Article
from src.summarizer import Summarizer


class TestSummarizerParseResponse:
    """_parse_response 단위 테스트."""

    def test_parses_clean_json(self, sample_article, test_settings):
        summarizer = Summarizer(test_settings)
        raw = json.dumps(
            {
                "one_liner": "GPT-5 출시로 AI 업계 지각변동",
                "body": "OpenAI가 GPT-5를 공개했다. 성능이 크게 향상됐다.",
                "importance": "상",
                "read_time_min": 4,
            }
        )
        summary = summarizer._parse_response(raw, sample_article)

        assert summary.one_liner == "GPT-5 출시로 AI 업계 지각변동"
        assert summary.importance == "상"
        assert summary.read_time_min == 4

    def test_parses_json_in_code_block(self, sample_article, test_settings):
        summarizer = Summarizer(test_settings)
        raw = '```json\n{"one_liner": "요약", "body": "본문", "importance": "중", "read_time_min": 3}\n```'
        summary = summarizer._parse_response(raw, sample_article)
        assert summary.importance == "중"

    def test_defaults_invalid_importance(self, sample_article, test_settings):
        summarizer = Summarizer(test_settings)
        raw = json.dumps(
            {
                "one_liner": "요약",
                "body": "본문",
                "importance": "unknown",
                "read_time_min": 3,
            }
        )
        summary = summarizer._parse_response(raw, sample_article)
        assert summary.importance == "중"

    def test_truncates_one_liner(self, sample_article, test_settings):
        summarizer = Summarizer(test_settings)
        raw = json.dumps(
            {
                "one_liner": "A" * 100,
                "body": "본문",
                "importance": "하",
                "read_time_min": 2,
            }
        )
        summary = summarizer._parse_response(raw, sample_article)
        assert len(summary.one_liner) <= 50


class TestSummarizerSummarizeAll:
    @pytest.mark.asyncio
    async def test_summarize_all_parallel(self, test_settings):
        """여러 아티클을 병렬 요약."""
        from datetime import datetime, timezone

        articles = [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at=datetime.now(timezone.utc),
                fallback_description=f"Description {i}",
            )
            for i in range(3)
        ]

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text=json.dumps(
                    {
                        "one_liner": "요약",
                        "body": "본문",
                        "importance": "중",
                        "read_time_min": 3,
                    }
                ),
            )
        ]
        mock_response.usage = MagicMock(
            cache_read_input_tokens=0, cache_creation_input_tokens=100
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        summarizer = Summarizer(test_settings)
        summarizer._client = mock_client

        summaries = await summarizer.summarize_all(articles)

        assert len(summaries) == 3
        assert mock_client.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_summarize_all_skips_failed(self, test_settings):
        """요약 실패한 아티클은 결과에서 제외."""
        import anthropic
        from datetime import datetime, timezone

        articles = [
            Article(
                title="Good Article",
                url="https://example.com/good",
                source="Test",
                published_at=datetime.now(timezone.utc),
                fallback_description="Good",
            ),
            Article(
                title="Bad Article",
                url="https://example.com/bad",
                source="Test",
                published_at=datetime.now(timezone.utc),
                fallback_description="Bad",
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text=json.dumps(
                    {
                        "one_liner": "요약",
                        "body": "본문",
                        "importance": "중",
                        "read_time_min": 3,
                    }
                ),
            )
        ]
        mock_response.usage = MagicMock(
            cache_read_input_tokens=0, cache_creation_input_tokens=100
        )

        async def side_effect(*args, **kwargs):
            messages = kwargs.get("messages", args[0] if args else [])
            user_content = messages[0]["content"] if messages else ""
            if "https://example.com/bad" in user_content:
                raise anthropic.APIStatusError(
                    "Server error",
                    response=MagicMock(status_code=500),
                    body={},
                )
            return mock_response

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=side_effect)

        summarizer = Summarizer(test_settings)
        summarizer._client = mock_client

        summaries = await summarizer.summarize_all(articles)
        assert len(summaries) == 1
        assert summaries[0].article.title == "Good Article"

    @pytest.mark.asyncio
    async def test_summarize_all_empty(self, test_settings):
        """빈 목록 입력 시 빈 목록 반환."""
        summarizer = Summarizer(test_settings)
        summaries = await summarizer.summarize_all([])
        assert summaries == []
