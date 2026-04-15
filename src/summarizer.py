import asyncio
import json
import re
from dataclasses import dataclass
from typing import Literal

import anthropic
import structlog

from src.collector.base import Article
from src.settings import Settings

log = structlog.get_logger()

SYSTEM_PROMPT = """당신은 AI/ML 전문 뉴스 편집자입니다.
주어진 아티클을 한국어로 요약하고 아래 JSON 형식으로만 응답하세요.

{
  "one_liner": "한 줄 요약 (50자 이내)",
  "body": "핵심 내용을 3~5문장으로 요약",
  "importance": "상 | 중 | 하",
  "read_time_min": 예상_읽기_시간_정수
}

요약 원칙:
- 독자는 AI 업계 종사자. 기술 용어를 쉽게 설명하지 않아도 됨
- 중요도 기준: 상=업계 패러다임 변화, 중=주목할 기술/비즈니스, 하=참고 수준
- 본문이 없으면 제목과 설명만으로 추론하여 요약"""


@dataclass
class Summary:
    article: Article
    one_liner: str
    body: str
    importance: Literal["상", "중", "하"]
    read_time_min: int


class Summarizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def summarize_all(self, articles: list[Article]) -> list[Summary]:
        """아티클 목록을 병렬로 요약한다."""
        if not articles:
            return []

        tasks = [self._summarize_one(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summaries: list[Summary] = []
        for article, result in zip(articles, results):
            if isinstance(result, Exception):
                log.warning(
                    "summarizer.failed",
                    title=article.title,
                    error=str(result),
                )
            elif result is not None:
                summaries.append(result)

        log.info("summarizer.done", total=len(articles), success=len(summaries))
        return summaries

    async def _summarize_one(self, article: Article, retry: int = 2) -> Summary | None:
        """단일 아티클 요약. 최대 retry회 재시도."""
        content = self._build_user_content(article)

        for attempt in range(retry + 1):
            try:
                response = await self._client.messages.create(
                    model=self._settings.claude_model,
                    max_tokens=1024,
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            # Prompt Caching: 시스템 프롬프트는 고정이므로 캐싱 적용
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": content}],
                )
                text = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )
                summary = self._parse_response(text, article)
                log.debug(
                    "summarizer.success",
                    title=article.title,
                    cache_read=response.usage.cache_read_input_tokens,
                    cache_creation=response.usage.cache_creation_input_tokens,
                )
                return summary
            except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
                if attempt < retry:
                    wait = 2 ** attempt
                    log.warning(
                        "summarizer.retry",
                        title=article.title,
                        attempt=attempt + 1,
                        wait=wait,
                        error=str(e),
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        return None

    def _build_user_content(self, article: Article) -> str:
        lines = [
            f"제목: {article.title}",
            f"출처: {article.source}",
            f"URL: {article.url}",
            "",
            "본문:",
            article.content_for_summary() or "(본문 없음)",
        ]
        return "\n".join(lines)

    def _parse_response(self, text: str, article: Article) -> Summary:
        """Claude 응답 텍스트에서 JSON을 추출하여 Summary로 변환."""
        # 코드 블록 안에 JSON이 있을 경우 추출
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

        # 중괄호로 감싸인 부분만 추출 (여분의 텍스트 제거)
        brace_match = re.search(r"\{.*\}", json_str, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(0)

        data = json.loads(json_str)

        importance = data.get("importance", "중")
        if importance not in ("상", "중", "하"):
            importance = "중"

        return Summary(
            article=article,
            one_liner=str(data.get("one_liner", article.title))[:50],
            body=str(data.get("body", "")),
            importance=importance,
            read_time_min=int(data.get("read_time_min", 3)),
        )
