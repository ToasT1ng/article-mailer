"""Pipeline 통합 테스트."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.collector.base import Article
from src.pipeline import Pipeline
from src.summarizer import Summary


def make_article(i: int) -> Article:
    return Article(
        title=f"AI Article {i}",
        url=f"https://example.com/article/{i}",
        source="Test Source",
        published_at=datetime(2026, 4, 14, 8, 0, 0, tzinfo=timezone.utc),
        fallback_description=f"Description {i}",
    )


def make_summary(article: Article) -> Summary:
    return Summary(
        article=article,
        one_liner=f"{article.title} 요약",
        body="본문 요약 내용.",
        importance="중",
        read_time_min=3,
    )


class TestPipeline:
    @pytest.mark.asyncio
    async def test_run_full_pipeline(self, test_settings):
        """전체 파이프라인 정상 실행 확인."""
        articles = [make_article(i) for i in range(3)]
        summaries = [make_summary(a) for a in articles]

        with (
            patch.object(Pipeline, "_collect", new=AsyncMock(return_value=articles)),
            patch.object(Pipeline, "_crawl_contents", new=AsyncMock(return_value=articles)),
            patch("src.pipeline.Summarizer") as mock_sum_cls,
            patch("src.pipeline.Mailer") as mock_mailer_cls,
            patch("src.pipeline.ArticleRepository") as mock_repo_cls,
        ):
            mock_summarizer = AsyncMock()
            mock_summarizer.summarize_all = AsyncMock(return_value=summaries)
            mock_sum_cls.return_value = mock_summarizer

            mock_mailer = MagicMock()
            mock_mailer_cls.return_value = mock_mailer

            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            pipeline = Pipeline(test_settings)
            await pipeline.run(count=3)

        mock_summarizer.summarize_all.assert_called_once_with(articles)
        mock_mailer.send.assert_called_once()
        assert mock_repo.mark_sent.call_count == 3
        mock_repo.record_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_no_articles_records_failed(self, test_settings):
        """아티클 없을 때 failed 로그 기록."""
        with (
            patch.object(Pipeline, "_collect", new=AsyncMock(return_value=[])),
            patch("src.pipeline.Mailer"),
            patch("src.pipeline.Summarizer"),
            patch("src.pipeline.ArticleRepository") as mock_repo_cls,
        ):
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            pipeline = Pipeline(test_settings)
            await pipeline.run()

        mock_repo.record_log.assert_called_once()
        call_kwargs = mock_repo.record_log.call_args[1]
        assert call_kwargs["status"] == "failed"

    @pytest.mark.asyncio
    async def test_run_deduplicates_via_db(self, test_settings):
        """DB에 이미 발송된 URL은 수집에서 제외되는지 확인."""
        all_articles = [make_article(i) for i in range(5)]
        sent_urls = {all_articles[0].url, all_articles[1].url}

        with (
            patch("src.pipeline.HackerNewsCollector") as mock_hn,
            patch("src.pipeline.RSSCollector") as mock_rss,
            patch("src.pipeline.crawl_article_content", new=AsyncMock(return_value=None)),
            patch("src.pipeline.Summarizer"),
            patch("src.pipeline.Mailer"),
            patch("src.pipeline.ArticleRepository") as mock_repo_cls,
        ):
            mock_hn.return_value.fetch = AsyncMock(return_value=all_articles[:3])
            mock_rss.return_value.fetch = AsyncMock(return_value=all_articles[3:])

            mock_repo = MagicMock()
            mock_repo.filter_unsent = MagicMock(
                side_effect=lambda urls: [u for u in urls if u not in sent_urls]
            )
            mock_repo_cls.return_value = mock_repo

            pipeline = Pipeline(test_settings)
            collected = await pipeline._collect(n=10)

        assert len(collected) == 3  # 5개 중 2개 제외
        for a in collected:
            assert a.url not in sent_urls
