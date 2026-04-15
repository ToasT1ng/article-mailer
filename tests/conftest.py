from datetime import datetime, timezone

import pytest

from src.collector.base import Article
from src.settings import Settings
from src.summarizer import Summary


@pytest.fixture
def sample_article() -> Article:
    return Article(
        title="GPT-5 Released with Unprecedented Capabilities",
        url="https://example.com/gpt5",
        source="Hacker News",
        published_at=datetime(2026, 4, 14, 8, 0, 0, tzinfo=timezone.utc),
        fallback_description="OpenAI releases GPT-5 with major improvements.",
    )


@pytest.fixture
def sample_article_with_content() -> Article:
    return Article(
        title="Claude 4 Sets New Benchmarks in AI Research",
        url="https://example.com/claude4",
        source="ArXiv cs.AI",
        published_at=datetime(2026, 4, 14, 9, 0, 0, tzinfo=timezone.utc),
        raw_content="This paper presents Claude 4, which achieves state-of-the-art results across multiple benchmarks. " * 50,
        fallback_description="Anthropic's Claude 4 paper.",
    )


@pytest.fixture
def sample_summary(sample_article: Article) -> Summary:
    return Summary(
        article=sample_article,
        one_liner="GPT-5, 전례 없는 성능으로 출시",
        body="OpenAI가 GPT-5를 공개했다. 이전 모델 대비 크게 향상된 성능을 보이며 여러 벤치마크에서 최고 성적을 기록했다.",
        importance="상",
        read_time_min=5,
    )


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        anthropic_api_key="test-key",
        smtp_user="test@gmail.com",
        smtp_password="test-password",
        recipient_emails=["recipient@example.com"],
        database_url="sqlite:///:memory:",
    )
