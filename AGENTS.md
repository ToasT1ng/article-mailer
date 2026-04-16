# AGENTS.md

이 프로젝트에서 코드를 작성할 때 따라야 하는 규칙과 컨텍스트.

## 프로젝트 개요

매일 AI 관련 아티클을 수집하고 Gemini API로 요약하여 이메일로 발송하는 Python 자동화 도구.
설계 문서는 `docs/design.md`에 있으며, 모든 구현은 이 문서를 따른다.

## 기술 스택

- Python 3.12+, asyncio 기반 비동기 처리
- `google-genai` SDK (Gemini API)
- `pydantic-settings` (환경변수 설정)
- `feedparser` + `httpx` (RSS/HTTP 수집)
- `beautifulsoup4` + `lxml` (본문 크롤링)
- `SQLAlchemy 2.0` + `alembic` (SQLite ORM, 마이그레이션)
- `APScheduler` (인프로세스 cron 스케줄러)
- `jinja2` (이메일 HTML/TXT 템플릿)
- `structlog` (구조화 로깅, JSON 출력)
- `ruff` (린터 + 포매터)
- `pytest` + `pytest-asyncio` + `pytest-httpx` (테스트)

## 코드 컨벤션

- ruff 설정: `line-length = 100`, `target-version = "py312"`, lint rules `["E", "F", "I", "UP"]`, `quote-style = "double"`
- 타입 힌트 필수. `str | None` 유니온 문법 사용 (Python 3.12+)
- `as any`, `type: ignore` 금지
- 주석과 docstring은 한국어
- 로거는 `structlog.get_logger()`를 모듈 최상단에 선언
- 로그 이벤트명은 `모듈명.동작` 형식 (예: `pipeline.start`, `mailer.sent`)

## 아키텍처 규칙

- 진입점: `src/main.py` (`python -m src.main`)
- 파이프라인 흐름: 수집(`collector/`) → 크롤링 → 요약(`summarizer.py`) → 발송(`mailer.py`) → DB 기록(`db/`)
- 모든 설정은 `src/settings.py`의 `Settings` 클래스를 통해 환경변수로 주입. 하드코딩 금지.
- 수집기는 `AbstractCollector`를 상속하고 `async def fetch() -> list[Article]`을 구현
- 외부 API 호출은 반드시 `asyncio.gather`로 병렬 처리
- Gemini API 호출 시 JSON 응답 모드 사용
- SMTP 발송과 Gemini API 호출은 재시도 로직 포함 (exponential backoff)
- DB 중복 체크: `ArticleRepository.filter_unsent()`로 이미 발송된 URL 제외

## 테스트 규칙

- `pytest-asyncio` mode: `auto`
- 외부 HTTP 요청은 `httpx_mock` (pytest-httpx) 또는 `unittest.mock.AsyncMock`으로 모킹
- 테스트 공통 fixture는 `tests/conftest.py`에 정의
- Gemini API 호출 테스트 시 `AsyncMock`으로 `summarizer._client`를 교체

## DB 마이그레이션

- 스키마 변경 시 `alembic/versions/`에 마이그레이션 파일 추가
- `ArticleRepository.__init__`에서 `Base.metadata.create_all()`을 호출하므로 개발 시에는 자동 생성됨
- 프로덕션 스키마 변경은 반드시 alembic migration으로 관리

## 배포

- Docker: `Dockerfile` + `docker-compose.yml`
- 모든 설정은 `.env` 파일로 주입 (`.env.example` 참조)
- SQLite DB는 `data/` 디렉토리에 저장되며 Docker volume으로 마운트
