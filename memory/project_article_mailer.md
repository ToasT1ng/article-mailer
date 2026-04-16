---
name: article-mailer project context
description: article-mailer 프로젝트 설계 및 구현 현황
type: project
---

매일 AI 관련 아티클을 수집·요약하여 이메일로 발송하는 Python 자동화 프로그램.

**Why:** AI 업계 종사자를 대상으로 매일 자동 발송되는 뉴스레터 시스템.

**How to apply:** 이 프로젝트에 대한 작업 시 설계 문서는 `docs/design.md`를 참조. 구현은 설계 문서의 기술 스택을 그대로 따름.

## 구현 완료 현황

- `src/settings.py` — pydantic-settings 기반 환경변수 설정
- `src/db/models.py`, `src/db/repository.py` — SQLAlchemy ORM + 발송이력 관리
- `src/collector/base.py` — Article 데이터클래스, AbstractCollector ABC
- `src/collector/hacker_news.py` — HN Top Stories API + AI 키워드 필터링
- `src/collector/rss.py` — 범용 RSS 수집기 (ArXiv, The Batch, MIT TR, VentureBeat)
- `src/collector/arxiv.py` — ArXiv 특화 수집기
- `src/summarizer.py` — Gemini API asyncio.gather 병렬 요약, JSON 응답 모드 사용
- `src/mailer.py` — SMTP + Jinja2 HTML/txt 이중 발송
- `src/pipeline.py` — 전체 파이프라인 조율 (수집→중복제거→크롤링→요약→발송→기록)
- `src/main.py` — APScheduler + CLI (--run-now, --count)
- `templates/email.html`, `templates/email.txt` — Jinja2 이메일 템플릿
- `alembic/` — DB 마이그레이션 (001_initial)
- `tests/` — pytest 테스트 (collector, summarizer, mailer, pipeline)
- `Dockerfile`, `docker-compose.yml` — Docker 패키징

## Gemini API 사용 방식

- 모델: `gemini-2.5-flash` (설정값, 기본값)
- JSON 응답 모드: `response_mime_type="application/json"` 사용
- 병렬 호출: `asyncio.gather`로 N개 아티클 동시 요약
