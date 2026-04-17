from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime
    raw_content: str | None = None
    fallback_description: str = ""
    category: Literal["impact", "trend"] | None = None

    def content_for_summary(self) -> str:
        """요약에 사용할 텍스트를 반환한다. 본문 크롤링 성공 시 본문, 아니면 RSS description."""
        if self.raw_content:
            # 토큰 절약을 위해 최대 4000자로 자름
            return self.raw_content[:4000]
        return self.fallback_description


class AbstractCollector(ABC):
    """모든 수집기의 기반 클래스."""

    @abstractmethod
    async def fetch(self) -> list[Article]:
        """소스에서 아티클 목록을 가져온다."""
        ...
