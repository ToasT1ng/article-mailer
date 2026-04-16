# Article Mailer 설계 문서

## 1. 개요

매일 지정된 시각에 AI 관련 아티클 N개를 자동으로 수집·요약하여 이메일로 발송하는 자동화 프로그램.
수집할 아티클 수, 발송 시각, 수신자 목록은 모두 설정으로 제어한다.

---

## 2. 목표 및 요구사항

### 기능 요구사항

| # | 요구사항 | 우선순위 |
|---|---|---|
| F-1 | 매일 지정된 시각에 자동 실행 | Must |
| F-2 | AI 관련 최신 아티클을 N개 수집 (N은 설정값) | Must |
| F-3 | 각 아티클 본문을 Gemini API로 요약 | Must |
| F-4 | 요약 결과를 HTML 이메일로 발송 | Must |
| F-5 | 이미 발송된 아티클 중복 제외 | Must |
| F-6 | 본문 크롤링 실패 시 graceful fallback | Must |
| F-7 | 여러 수신자에게 동시 발송 | Should |
| F-8 | 수동 실행 지원 (즉시 발송 CLI 명령) | Should |

### 비기능 요구사항

- 단일 서버(또는 로컬 머신)에서 Docker로 실행 가능
- 하루 1회 실행 기준 Gemini API 비용 최소화
- 환경변수만으로 모든 설정 변경 가능 (코드 수정 불필요)

---

## 3. 기술 스택 결정

### 언어 및 런타임

**Python 3.12**
- 이유: `asyncio` 네이티브 지원, RSS/HTTP/이메일 생태계 성숙도, Gemini SDK 공식 지원

### 의존성 목록

| 라이브러리 | 버전 | 용도 | 선택 이유 |
|---|---|---|---|
| `google-genai` | latest | Gemini API 클라이언트 | 공식 SDK, 무료 티어 지원 |
| `pydantic-settings` | ^2 | 설정 관리 (.env 파싱) | 타입 안전한 환경변수 바인딩, 검증 내장 |
| `feedparser` | ^6 | RSS/Atom 피드 파싱 | 사실상 표준, 인코딩/날짜 처리 자동 |
| `httpx` | ^0.27 | 비동기 HTTP 클라이언트 | async/await 네이티브, timeout/retry 설정 용이 |
| `beautifulsoup4` | ^4 | HTML 본문 추출 | 파싱 안정성 높음 |
| `lxml` | ^5 | BS4 파서 백엔드 | feedparser/BS4 공통 사용, 속도 빠름 |
| `jinja2` | ^3 | 이메일 HTML 템플릿 | 로직과 뷰 분리 |
| `APScheduler` | ^3 | 인프로세스 스케줄러 | cron 표현식 지원, 프로세스 재시작 없이 스케줄 변경 가능 |
| `SQLAlchemy` | ^2 | ORM (SQLite) | 중복 발송 방지용 발송 이력 관리 |
| `alembic` | ^1 | DB 마이그레이션 | 스키마 변경 이력 관리 |
| `structlog` | ^24 | 구조화 로깅 | JSON 로그 출력, 프로덕션 로그 파싱 용이 |
| `pytest` | ^8 | 테스트 | - |
| `pytest-asyncio` | ^0 | 비동기 테스트 | - |
| `pytest-httpx` | ^0 | httpx mock | 외부 HTTP 요청 mocking |
| `ruff` | ^0 | 린터 + 포매터 | flake8+black 대체, 빠름 |

### 스케줄러 선택: APScheduler vs 시스템 Cron

| 항목 | APScheduler | 시스템 Cron |
|---|---|---|
| 설정 변경 | 코드/환경변수로 핫리로드 가능 | crontab 직접 수정 필요 |
| 실행 이력 | 인메모리 or DB 저장 | 별도 로그 필요 |
| 컨테이너 친화성 | 단일 프로세스로 완결 | 별도 cron 데몬 필요 |
| 복잡도 | 코드로 관리 | 운영 환경 의존 |

**결론: APScheduler 채택** — Docker 단일 컨테이너에서 스케줄까지 자급자족 가능.

### 이메일 발송: SMTP vs AWS SES

| 항목 | Gmail SMTP | AWS SES |
|---|---|---|
| 초기 설정 | Gmail App Password만 발급하면 됨 | AWS 계정 + 도메인 인증 필요 |
| 발송 한도 | 500건/일 (무료) | 거의 무제한 (유료) |
| 개발 편의성 | 높음 | 낮음 |
| 프로덕션 적합성 | 수신자 수 적으면 충분 | 대규모 발송에 적합 |

**결론: Gmail SMTP 기본 채택**, 환경변수로 SMTP 호스트를 교체하면 SES로 전환 가능하게 설계.

### Gemini API 사용 전략

- 모델: `gemini-2.5-flash` (무료 티어: 1,500 req/일)
- 호출 방식: 아티클별 개별 호출 (병렬 `asyncio.gather`)
- JSON 응답 모드 사용 (`response_mime_type="application/json"`)
- 예상 비용: 무료 티어 내 충분 (하루 5~10건 기준)

---

## 4. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        article-mailer                        │
│                                                              │
│  ┌───────────┐   trigger   ┌──────────────────────────────┐  │
│  │ Scheduler │────────────▶│        Pipeline              │  │
│  │(APScheduler)            │                              │  │
│  └───────────┘             │  ┌──────────┐               │  │
│                            │  │Collector │ feedparser     │  │
│  ┌───────────┐             │  │          │ + httpx        │  │
│  │  CLI      │────────────▶│  └────┬─────┘               │  │
│  │(수동 실행) │  trigger    │       │ articles[]          │  │
│  └───────────┘             │  ┌────▼─────┐               │  │
│                            │  │Summarizer│ Gemini API    │  │
│                            │  │          │ (async batch)  │  │
│                            │  └────┬─────┘               │  │
│                            │       │ summaries[]         │  │
│                            │  ┌────▼─────┐               │  │
│                            │  │  Mailer  │ SMTP + Jinja2  │  │
│                            │  └──────────┘               │  │
│                            └──────────────────────────────┘  │
│                                          │                   │
│  ┌──────────────┐              ┌──────────▼──────────┐       │
│  │   Settings   │              │    SQLite DB        │       │
│  │(pydantic-    │              │  (sent_articles)    │       │
│  │  settings)   │              └─────────────────────┘       │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. 데이터 흐름 상세

```
[1] Scheduler / CLI
      │
      ▼
[2] Collector.collect(n: int) → List[Article]
      ├── 등록된 소스(RSS/API) 병렬 fetch
      ├── 전체 후보 목록 최신순 정렬
      ├── DB에서 이미 발송된 URL 제외
      └── 상위 n개 반환

      Article {
        title: str
        url: str
        source: str
        published_at: datetime
        raw_content: str | None   # 크롤링 성공 시
        fallback_description: str # 크롤링 실패 시 RSS description 사용
      }

[3] Summarizer.summarize_all(articles) → List[Summary]  [asyncio.gather]
      ├── 각 Article에 대해 Gemini API 호출 (병렬)
      ├── JSON 응답 모드로 구조화된 출력
      └── 응답 파싱 → Summary

      Summary {
        article: Article
        one_liner: str      # 한 줄 요약 (50자 이내)
        body: str           # 3~5문장 요약
        importance: Literal["상", "중", "하"]
        read_time_min: int  # 추정 읽기 시간
      }

[4] Mailer.send(summaries: List[Summary])
      ├── Jinja2로 HTML 렌더링
      ├── MIME multipart (text/plain fallback 포함)
      ├── SMTP 발송
      └── DB에 발송된 URL 기록 (중복 방지)
```

---

## 6. 아티클 수집 소스

우선순위 순으로 여러 소스를 등록하고, 부족하면 다음 소스로 보충.

| 우선순위 | 소스 | 방식 | 카테고리 |
|---|---|---|---|
| 1 | Hacker News (Top Stories) | REST API | AI/ML 트렌딩, 커뮤니티 검증 |
| 2 | ArXiv cs.AI | RSS | 최신 AI 논문 |
| 3 | The Batch (deeplearning.ai) | RSS | AI 뉴스레터 |
| 4 | MIT Technology Review – AI | RSS | AI 업계 분석 |
| 5 | VentureBeat AI | RSS | AI 스타트업/비즈니스 |

**Hacker News 필터링 기준**
- 점수(score) ≥ 100
- 제목에 `AI`, `LLM`, `GPT`, `ML`, `model`, `neural` 등 키워드 포함
- 24시간 이내 게시

---

## 7. 설정 (pydantic-settings)

모든 동작은 환경변수로 제어한다. 코드 수정 없이 `.env` 파일만 바꾸면 된다.

```python
class Settings(BaseSettings):
    # 스케줄
    send_hour: int = 8          # 발송 시각 (0~23)
    send_minute: int = 0        # 발송 분 (0~59)
    timezone: str = "Asia/Seoul"

    # 아티클
    article_count: int = 5      # 수집할 아티클 수 (1~20)
    article_language: str = "ko"  # 요약 언어

    # Gemini API
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str

    # 수신자 (콤마 구분)
    recipient_emails: list[str]

    # DB
    database_url: str = "sqlite:///./data/article_mailer.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

**.env.example**

```env
# 스케줄 설정
SEND_HOUR=8
SEND_MINUTE=0
TIMEZONE=Asia/Seoul

# 아티클 설정
ARTICLE_COUNT=5          # 원하는 숫자로 변경 (1~20)
ARTICLE_LANGUAGE=ko

# Gemini API
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# SMTP (Gmail 기준)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=gmail-app-password

# 수신자 (콤마로 여러 명 지정 가능)
RECIPIENT_EMAILS=a@example.com,b@example.com
```

---

## 8. DB 스키마

```sql
-- 발송 이력 (중복 방지)
CREATE TABLE sent_articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL,
    sent_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 발송 로그 (성공/실패 추적)
CREATE TABLE send_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at          DATETIME NOT NULL,
    article_count   INTEGER NOT NULL,
    recipient_count INTEGER NOT NULL,
    status          TEXT NOT NULL,   -- 'success' | 'partial' | 'failed'
    error_message   TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. Gemini API 프롬프트 설계

```python
SYSTEM_PROMPT = """
당신은 AI/ML 전문 뉴스 편집자입니다.
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
- 본문이 없으면 제목과 설명만으로 추론하여 요약
""" # JSON 응답 모드로 전달
```

---

## 10. 이메일 템플릿 구조

```
제목: [AI 데일리] 2026-04-14 | 오늘의 AI 아티클 {N}선

본문 (HTML):
┌─────────────────────────────────────────┐
│  AI 데일리 브리핑                        │
│  2026년 04월 14일 (월)                   │
├─────────────────────────────────────────┤
│                                         │
│  1. [중요도: 상] 아티클 제목             │
│     출처: Hacker News | 읽기: 5분        │
│     한 줄 요약                           │
│     ─────────────────────────────────   │
│     본문 요약 (3~5문장)                  │
│                                         │
│     [원문 읽기 →]                        │
│                                         │
│  2. ...                                 │
│                                         │
├─────────────────────────────────────────┤
│  이 메일은 자동 발송됩니다.              │
└─────────────────────────────────────────┘
```

---

## 11. 에러 처리 전략

| 상황 | 처리 |
|---|---|
| 특정 소스 RSS fetch 실패 | 해당 소스 스킵, 다음 소스로 보충 |
| 아티클 본문 크롤링 실패 | RSS `description` 필드로 fallback |
| Gemini API 타임아웃 | 최대 2회 재시도, 실패 시 해당 아티클 제외 |
| 수집 아티클이 N개 미만 | 가용한 아티클만으로 발송 (최소 1개 이상이면 발송) |
| SMTP 발송 실패 | 최대 3회 재시도 후 실패 로그 기록 |
| 모든 아티클 수집 실패 | 발송 취소, `send_logs`에 `failed` 기록 |

---

## 12. 디렉토리 구조

```
article-mailer/
├── docs/
│   └── design.md
├── src/
│   ├── __init__.py
│   ├── main.py             # 진입점 (Scheduler 시작 + CLI)
│   ├── settings.py         # pydantic-settings 설정 클래스
│   ├── pipeline.py         # 전체 파이프라인 조율
│   ├── collector/
│   │   ├── __init__.py
│   │   ├── base.py         # AbstractCollector
│   │   ├── hacker_news.py
│   │   ├── arxiv.py
│   │   └── rss.py          # 범용 RSS 수집기
│   ├── summarizer.py       # Gemini API 요약 (async)
│   ├── mailer.py           # SMTP 발송
│   └── db/
│       ├── __init__.py
│       ├── models.py       # SQLAlchemy 모델
│       └── repository.py   # sent_articles CRUD
├── templates/
│   ├── email.html          # Jinja2 HTML 템플릿
│   └── email.txt           # plaintext fallback
├── tests/
│   ├── conftest.py
│   ├── test_collector.py
│   ├── test_summarizer.py
│   ├── test_mailer.py
│   └── test_pipeline.py
├── data/                   # .gitignore — SQLite DB 저장
├── alembic/                # DB 마이그레이션
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml          # 의존성 + ruff 설정
└── README.md
```

---

## 13. 실행 방법

```bash
# 스케줄러 시작 (매일 SEND_HOUR시에 자동 발송)
python -m src.main

# 즉시 수동 실행 (테스트용)
python -m src.main --run-now

# 아티클 수 지정해서 즉시 실행
python -m src.main --run-now --count 3

# Docker
docker compose up -d
```

---

## 14. 개발 단계

| 단계 | 작업 | 완료 기준 |
|---|---|---|
| 1 | 프로젝트 초기화 (pyproject.toml, settings, DB) | `python -m src.main` 실행됨 |
| 2 | Collector 구현 (Hacker News + RSS) | 아티클 목록 정상 수집 |
| 3 | Summarizer 구현 (Gemini API, async) | 요약 JSON 정상 파싱 |
| 4 | Mailer 구현 (SMTP + Jinja2 템플릿) | 실제 메일 수신 확인 |
| 5 | Pipeline + Scheduler 연결 | 자동 발송 확인 |
| 6 | 에러 처리 + 중복 방지 DB | 재실행 시 중복 없음 확인 |
| 7 | 테스트 작성 | pytest 통과 |
| 8 | Docker 패키징 | `docker compose up -d` 동작 |
