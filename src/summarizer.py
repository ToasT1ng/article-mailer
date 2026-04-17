import asyncio
import json
import math
import re
from dataclasses import dataclass
from typing import Literal

import structlog
from google import genai
from google.genai import types

from src.collector.base import Article
from src.settings import Settings

log = structlog.get_logger()

SCREENING_PROMPT = """당신은 AI/ML 전문 뉴스 편집장입니다.
아래 아티클 후보 목록에서 **정확히 {total}개**를 선별하세요.

카테고리별 선별 기준:
- **impact** ({impact_count}개): AI를 활용하여 세상을 실제로 변화시키고 있는 사례.
  의료·교육·환경·제조·금융 등 산업에서 AI가 만들어내는 실질적 변화.
- **trend** ({trend_count}개): AI 기술 동향. 새로 나온 모델, 상용화 소식,
  오픈소스·로컬 모델 발전, 벤치마크, API 출시, 업계 인수합병 등.

아래 JSON 배열로만 응답하세요. 각 항목은 원본 index(0-based)와 category를 포함:
[
  {{"index": 0, "category": "impact"}},
  {{"index": 5, "category": "trend"}},
  ...
]

중요: 반드시 impact {impact_count}개 + trend {trend_count}개 = 총 {total}개를 선별하세요."""

SUMMARY_PROMPT = """당신은 AI/ML 전문 뉴스 편집자입니다.
아래 {total}개 아티클을 읽고, 최종 **{final_count}개**를 선택하여 요약하세요.

선택 기준:
- **impact** ({impact_count}개): AI로 세상을 바꾸고 있는 가장 임팩트 있는 사례
- **trend** ({trend_count}개): 가장 주목할 만한 AI 기술 동향

아래 JSON 배열로만 응답하세요:
[
  {{
    "index": 0,
    "category": "impact",
    "one_liner": "한 줄 요약 (50자 이내)",
    "body": "핵심 내용을 3~5문장으로 요약",
    "importance": "상 | 중 | 하",
    "read_time_min": 3
  }},
  ...
]

요약 원칙:
- 독자는 AI 업계 종사자. 기술 용어를 쉽게 설명하지 않아도 됨
- 중요도 기준: 상=업계 패러다임 변화, 중=주목할 기술/비즈니스, 하=참고 수준
- 반드시 impact {impact_count}개 + trend {trend_count}개 = 총 {final_count}개를 응답하세요."""


def compute_category_counts(n: int) -> tuple[int, int]:
    """최종 아티클 수에서 impact/trend 개수를 계산한다. impact=ceil(20%), trend=나머지."""
    impact = max(1, math.ceil(n * 0.2))
    trend = n - impact
    return impact, trend


@dataclass
class Summary:
    article: Article
    one_liner: str
    body: str
    importance: Literal["상", "중", "하"]
    read_time_min: int


class Summarizer:
    """Gemini 기반 2단계 요약기: 선별(screening) → 최종 선택+요약(select_and_summarize)."""

    MAX_SCREENING_POOL = 20
    SCREENING_MULTIPLIER = 4

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _screening_pool_size(self, n: int) -> int:
        return min(n * self.SCREENING_MULTIPLIER, self.MAX_SCREENING_POOL)

    async def screen(self, articles: list[Article], n: int) -> list[Article]:
        """1단계: 아티클 후보 목록에서 스크리닝 풀 크기만큼 Gemini로 선별한다."""
        pool_size = self._screening_pool_size(n)

        if len(articles) <= pool_size:
            log.info("summarizer.screen.skip", reason="후보가 풀 사이즈 이하", pool_size=pool_size)
            return articles

        impact_count, trend_count = compute_category_counts(n)
        pool_impact = max(1, math.ceil(pool_size * 0.2))
        pool_trend = pool_size - pool_impact

        candidate_list = "\n".join(
            f"[{i}] {a.title} | {a.source} | {a.fallback_description[:100]}"
            for i, a in enumerate(articles)
        )

        prompt = SCREENING_PROMPT.format(
            total=pool_size,
            impact_count=pool_impact,
            trend_count=pool_trend,
        )
        content = f"{candidate_list}\n\n총 후보 수: {len(articles)}개"

        selected_indices = await self._call_gemini_for_indices(prompt, content)

        if not selected_indices:
            log.warning("summarizer.screen.fallback", reason="Gemini 선별 실패, 상위 N개 사용")
            return articles[:pool_size]

        valid = [i for i in selected_indices if 0 <= i < len(articles)]
        result = [articles[i] for i in valid]

        log.info("summarizer.screen.done", selected=len(result))
        return result[:pool_size]

    async def select_and_summarize(
        self, articles: list[Article], n: int
    ) -> list[Summary]:
        """2단계: 크롤링된 아티클에서 최종 N개를 선택하고 요약한다."""
        if not articles:
            return []

        impact_count, trend_count = compute_category_counts(n)

        article_texts = "\n---\n".join(
            f"[{i}] 제목: {a.title}\n출처: {a.source}\nURL: {a.url}\n"
            f"본문:\n{a.content_for_summary() or '(본문 없음)'}"
            for i, a in enumerate(articles)
        )

        prompt = SUMMARY_PROMPT.format(
            total=len(articles),
            final_count=n,
            impact_count=impact_count,
            trend_count=trend_count,
        )

        summaries = await self._call_gemini_for_summaries(
            prompt, article_texts, articles, n
        )

        log.info(
            "summarizer.select_and_summarize.done",
            requested=n,
            returned=len(summaries),
        )
        return summaries

    async def _call_gemini_for_indices(
        self, system_prompt: str, content: str, retry: int = 2
    ) -> list[int]:
        """Gemini를 호출하여 인덱스 리스트를 반환한다."""
        for attempt in range(retry + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        max_output_tokens=2048,
                    ),
                )
                text = response.text or ""
                data = self._parse_json_array(text)
                indices = [item["index"] for item in data if "index" in item]
                log.debug("summarizer.screen.response", count=len(indices))
                return indices
            except Exception as e:
                if attempt < retry:
                    wait = 2**attempt
                    log.warning(
                        "summarizer.screen.retry",
                        attempt=attempt + 1,
                        wait=wait,
                        error=str(e),
                    )
                    await asyncio.sleep(wait)
                else:
                    log.error("summarizer.screen.failed", error=str(e))
                    return []

        return []

    async def _call_gemini_for_summaries(
        self,
        system_prompt: str,
        content: str,
        articles: list[Article],
        n: int,
        retry: int = 2,
    ) -> list[Summary]:
        """Gemini를 호출하여 최종 선택+요약 결과를 반환한다."""
        for attempt in range(retry + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        max_output_tokens=4096,
                    ),
                )
                text = response.text or ""
                data = self._parse_json_array(text)
                return self._build_summaries(data, articles, n)
            except Exception as e:
                if attempt < retry:
                    wait = 2**attempt
                    log.warning(
                        "summarizer.summary.retry",
                        attempt=attempt + 1,
                        wait=wait,
                        error=str(e),
                    )
                    await asyncio.sleep(wait)
                else:
                    log.error("summarizer.summary.failed", error=str(e))
                    return []

        return []

    def _parse_json_array(self, text: str) -> list[dict]:
        """Gemini 응답에서 JSON 배열을 추출한다."""
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

        bracket_match = re.search(r"\[.*\]", json_str, re.DOTALL)
        if bracket_match:
            json_str = bracket_match.group(0)

        return json.loads(json_str)

    def _build_summaries(
        self, data: list[dict], articles: list[Article], n: int
    ) -> list[Summary]:
        """파싱된 JSON 데이터를 Summary 리스트로 변환한다."""
        summaries: list[Summary] = []
        for item in data:
            idx = item.get("index")
            if idx is None or idx < 0 or idx >= len(articles):
                continue

            article = articles[idx]
            category = item.get("category", "trend")
            if category not in ("impact", "trend"):
                category = "trend"
            article.category = category

            importance = item.get("importance", "중")
            if importance not in ("상", "중", "하"):
                importance = "중"

            summaries.append(
                Summary(
                    article=article,
                    one_liner=str(item.get("one_liner", article.title))[:50],
                    body=str(item.get("body", "")),
                    importance=importance,
                    read_time_min=int(item.get("read_time_min", 3)),
                )
            )

            if len(summaries) >= n:
                break

        return summaries
