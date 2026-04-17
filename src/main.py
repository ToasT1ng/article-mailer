"""
article-mailer 진입점.

사용법:
  python -m src.main               # 스케줄러 시작 (매일 SEND_HOUR시 자동 발송)
  python -m src.main --run-now     # 즉시 수동 실행
  python -m src.main --run-now --count 3
"""
import argparse
import asyncio
import logging
import signal
import sys

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline import Pipeline
from src.settings import get_settings

# ─── 로깅 설정 ───────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=logging.WARNING)

log = structlog.get_logger()


def run_pipeline(count: int | None = None, dry_run: bool = False) -> None:
    """동기 래퍼 — APScheduler 및 CLI에서 공통 사용."""
    settings = get_settings()
    pipeline = Pipeline(settings)
    asyncio.run(pipeline.run(count=count, dry_run=dry_run))


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 데일리 아티클 메일러")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="즉시 실행 (스케줄러 없이)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="수집할 아티클 수 (기본값: settings.article_count)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="수집+크롤링만 실행. Gemini 요약·이메일 발송 스킵",
    )
    args = parser.parse_args()

    if args.run_now:
        log.info("main.run_now", count=args.count, dry_run=args.dry_run)
        run_pipeline(count=args.count, dry_run=args.dry_run)
        return

    # ─── 스케줄러 모드 ─────────────────────────────────────────────────────
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.timezone)
    trigger = CronTrigger(
        hour=settings.send_hour,
        minute=settings.send_minute,
        timezone=settings.timezone,
    )
    scheduler.add_job(run_pipeline, trigger=trigger, id="daily_mailer")
    log.info(
        "scheduler.start",
        hour=settings.send_hour,
        minute=settings.send_minute,
        timezone=settings.timezone,
    )

    # Ctrl+C / SIGTERM 처리
    def _shutdown(signum, frame):  # noqa: ANN001
        log.info("scheduler.shutdown")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
