import asyncio
from datetime import datetime, timezone

import structlog

from src.collector.base import Article
from src.collector.hacker_news import HackerNewsCollector, crawl_article_content
from src.collector.rss import RSSCollector
from src.db.repository import ArticleRepository
from src.mailer import Mailer
from src.settings import Settings
from src.summarizer import Summarizer

log = structlog.get_logger()


class Pipeline:
    """전체 파이프라인 (수집 → 중복제거 → 크롤링 → 요약 → 발송 → 기록)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = ArticleRepository(settings.database_url)
        self._summarizer = Summarizer(settings)
        self._mailer = Mailer(settings)

    async def run(self, count: int | None = None) -> None:
        n = count or self._settings.article_count
        run_at = datetime.now(timezone.utc)
        log.info("pipeline.start", count=n)

        # 1. 수집
        articles = await self._collect(n)
        if not articles:
            log.error("pipeline.no_articles")
            self._repo.record_log(
                run_at=run_at,
                article_count=0,
                recipient_count=len(self._settings.recipient_emails),
                status="failed",
                error_message="수집된 아티클 없음",
            )
            return

        # 2. 본문 크롤링 (병렬)
        articles = await self._crawl_contents(articles)

        # 3. Gemini API 요약
        summaries = await self._summarizer.summarize_all(articles)
        if not summaries:
            log.error("pipeline.no_summaries")
            self._repo.record_log(
                run_at=run_at,
                article_count=len(articles),
                recipient_count=len(self._settings.recipient_emails),
                status="failed",
                error_message="요약 생성 실패",
            )
            return

        # 4. 이메일 발송
        status = "success"
        error_msg: str | None = None
        try:
            self._mailer.send(summaries, send_date=run_at)
        except Exception as exc:
            status = "partial"
            error_msg = str(exc)
            log.exception("pipeline.send_failed")

        # 5. 발송 이력 기록
        for s in summaries:
            self._repo.mark_sent(
                url=s.article.url,
                title=s.article.title,
                source=s.article.source,
            )

        self._repo.record_log(
            run_at=run_at,
            article_count=len(summaries),
            recipient_count=len(self._settings.recipient_emails),
            status=status,
            error_message=error_msg,
        )
        log.info("pipeline.done", status=status, articles=len(summaries))

    async def _collect(self, n: int) -> list[Article]:
        """여러 소스에서 아티클을 수집하고 n개를 반환한다."""
        hn_collector = HackerNewsCollector()
        rss_collector = RSSCollector()

        hn_articles, rss_articles = await asyncio.gather(
            hn_collector.fetch(),
            rss_collector.fetch(),
            return_exceptions=True,
        )

        if isinstance(hn_articles, Exception):
            log.warning("pipeline.hn_failed", error=str(hn_articles))
            hn_articles = []
        if isinstance(rss_articles, Exception):
            log.warning("pipeline.rss_failed", error=str(rss_articles))
            rss_articles = []

        # 최신순 정렬
        all_articles: list[Article] = sorted(
            hn_articles + rss_articles,  # type: ignore[operator]
            key=lambda a: a.published_at,
            reverse=True,
        )

        # 중복 URL 제거 (같은 URL이 여러 소스에서 올 수 있음)
        seen: set[str] = set()
        unique: list[Article] = []
        for a in all_articles:
            if a.url not in seen:
                seen.add(a.url)
                unique.append(a)

        # DB에서 이미 발송된 URL 제외
        unsent_urls = self._repo.filter_unsent([a.url for a in unique])
        unsent_set = set(unsent_urls)
        candidates = [a for a in unique if a.url in unsent_set]

        log.info(
            "pipeline.collected",
            total=len(all_articles),
            unique=len(unique),
            unsent=len(candidates),
        )

        return candidates[:n]

    async def _crawl_contents(self, articles: list[Article]) -> list[Article]:
        """아티클 본문을 병렬 크롤링. 실패해도 fallback_description 유지."""
        tasks = [crawl_article_content(a.url) for a in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for article, result in zip(articles, results):
            if isinstance(result, str) and result:
                article.raw_content = result

        crawled = sum(1 for r in results if isinstance(r, str) and r)
        log.info("pipeline.crawled", total=len(articles), success=crawled)
        return articles
