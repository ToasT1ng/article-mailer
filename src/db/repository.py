from datetime import datetime

import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.db.models import Base, SendLog, SentArticle

log = structlog.get_logger()


class ArticleRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)
        Base.metadata.create_all(self._engine)

    def is_sent(self, url: str) -> bool:
        with Session(self._engine) as session:
            result = session.execute(
                select(SentArticle.id).where(SentArticle.url == url).limit(1)
            ).first()
            return result is not None

    def filter_unsent(self, urls: list[str]) -> list[str]:
        if not urls:
            return []
        with Session(self._engine) as session:
            sent = set(
                row[0]
                for row in session.execute(
                    select(SentArticle.url).where(SentArticle.url.in_(urls))
                ).all()
            )
        return [u for u in urls if u not in sent]

    def mark_sent(self, url: str, title: str, source: str) -> None:
        with Session(self._engine) as session:
            existing = session.execute(
                select(SentArticle).where(SentArticle.url == url)
            ).scalar_one_or_none()
            if existing is None:
                session.add(SentArticle(url=url, title=title, source=source))
                session.commit()

    def record_log(
        self,
        run_at: datetime,
        article_count: int,
        recipient_count: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        with Session(self._engine) as session:
            session.add(
                SendLog(
                    run_at=run_at,
                    article_count=article_count,
                    recipient_count=recipient_count,
                    status=status,
                    error_message=error_message,
                )
            )
            session.commit()
