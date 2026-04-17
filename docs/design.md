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
| F-8 | 수동 실행 지원 (`--run-now` CLI 플래그) | Should |
| F-9 | `npx article-mailer` 로 설치 없이 실행 가능 | Must |

### 비기능 요구사항

- 단일 서버(또는 로컬 머신)에서 Docker로 실행 가능
- `npx article-mailer` 또는 `npm install -g article-mailer` 로도 실행 가능
- 하루 1회 실행 기준 Gemini API 비용 최소화
- 환경변수(.env)만으로 모든 설정 변경 가능 (코드 수정 불필요)
- 네이티브 모듈 없음 — `npx` 환경에서 빌드 도구 불필요

---

## 3. 기술 스택

### 언어 및 런타임

**TypeScript + Node.js 20+**
- npm 생태계를 통한 `npx` 배포 가능
- `fetch` API 내장 (Node 18+), 별도 HTTP 클라이언트 불필요
- 비동기 처리: `Promise.allSettled`, `async/await`

### 의존성 목록

| 라이브러리 | 버전 | 용도 |
|---|---|---|
| `@google/generative-ai` | ^0.21 | Gemini API 클라이언트 |
| `zod` | ^3.23 | 환경변수 스키마 검증 |
| `dotenv` | ^16.4 | .env 파일 로드 |
| `rss-parser` | ^3.13 | RSS/Atom 피드 파싱 |
| `cheerio` | ^1.0 | HTML 본문 추출 |
| `nodemailer` | ^6.9 | SMTP 이메일 발송 |
| `node-cron` | ^3.0 | 인프로세스 cron 스케줄러 |
| `handlebars` | ^4.7 | 이메일 HTML/TXT 템플릿 |
| `pino` | ^9.1 | 구조화 로깅 (JSON) |
| `pino-pretty` | ^11.0 | 로컬 개발용 pretty 출력 |

### 개발 의존성

| 라이브러리 | 용도 |
|---|---|
| `typescript` | 컴파일러 |
| `tsx` | 개발 중 직접 실행 (`ts-node` 대체) |
| `@types/node` | Node.js 타입 |
| `@types/nodemailer` | nodemailer 타입 |

### 네이티브 모듈 없음

SQLite 대신 **JSON 파일**로 발송 이력 관리.
하루 5~10건 규모에서 성능 이슈 없으며, `npx` 환경에서 별도 빌드 도구 불필요.

### npm 배포 구조

```
bin/article-mailer.js     ← shebang 래퍼 (npm bin 진입점)
dist/                     ← tsc 컴파일 결과
src/templates/            ← Handlebars 템플릿 (빌드 시 dist/templates/ 복사)
```

`package.json`의 `bin` 필드가 `bin/article-mailer.js`를 가리키며,
npm이 설치 시 자동으로 실행 권한(chmod +x)을 부여한다.

---

## 4. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        article-mailer                        │
│                                                              │
│  ┌───────────┐   trigger   ┌──────────────────────────────┐  │
│  │ Scheduler │────────────▶│        Pipeline              │  │
│  │(node-cron)│             │                              │  │
│  └───────────┘             │  ┌──────────┐               │  │
│                            │  │Collector │ rss-parser     │  │
│  ┌───────────┐             │  │          │ + fetch        │  │
│  │  CLI      │────────────▶│  └────┬─────┘               │  │
│  │(--run-now)│  trigger    │       │ articles[]          │  │
│  └───────────┘             │  ┌────▼─────┐               │  │
│                            │  │Summarizer│ Gemini API    │  │
│                            │  │          │ (async batch)  │  │
│                            │  └────┬─────┘               │  │
│                            │       │ summaries[]         │  │
│                            │  ┌────▼─────┐               │  │
│                            │  │  Mailer  │ nodemailer    │  │
│                            │  │          │ + Handlebars  │  │
│                            │  └──────────┘               │  │
│                            └──────────────────────────────┘  │
│                                          │                   │
│  ┌──────────────┐              ┌──────────▼──────────┐       │
│  │   Settings   │              │    JSON 파일        │       │
│  │  (zod +      │              │  (sent_articles)    │       │
│  │   dotenv)    │              └─────────────────────┘       │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. 데이터 흐름 상세

```
[1] Scheduler(node-cron) / CLI(--run-now)
      │
      ▼
[2] Collector.fetch() → Article[]
      ├── HackerNewsCollector: REST API + AI 키워드 필터
      ├── RSSCollector: rss-parser로 복수 피드 수집
      ├── 전체 후보 최신순 정렬 + URL 중복 제거
      └── JSON 파일에서 이미 발송된 URL 제외

      Article {
        title: string
        url: string
        source: string
        publishedAt: Date
        rawContent?: string        // 크롤링 성공 시
        fallbackDescription: string // 크롤링 실패 시 RSS description
        category?: 'impact' | 'trend'
      }

[3] Summarizer.screen(articles, n) → Article[]   // Gemini 1회차: 후보 선별
[4] crawlContents(screened) → Article[]           // cheerio로 본문 크롤링 (병렬)
[5] Summarizer.selectAndSummarize(crawled, n) → Summary[]  // Gemini 2회차: 요약

      Summary {
        article: Article
        oneLiner: string           // 한 줄 요약 (50자 이내)
        body: string               // 3~5문장 요약
        importance: '상' | '중' | '하'
        readTimeMin: number
      }

[6] Mailer.send(summaries)
      ├── Handlebars로 HTML/TXT 렌더링
      ├── nodemailer로 SMTP 발송
      └── JSON 파일에 발송 URL 기록
```

---

## 6. 아티클 수집 소스

| 우선순위 | 소스 | 방식 | 카테고리 |
|---|---|---|---|
| 1 | Hacker News (Top Stories) | REST API | AI/ML 트렌딩 |
| 2 | ArXiv cs.AI | RSS | 최신 AI 논문 |
| 3 | The Batch (deeplearning.ai) | RSS | AI 뉴스레터 |
| 4 | MIT Technology Review – AI | RSS | AI 업계 분석 |
| 5 | VentureBeat AI | RSS | AI 스타트업/비즈니스 |

**Hacker News 필터링 기준**
- score ≥ 100
- 제목에 AI/LLM/GPT/ML/neural 등 키워드 포함
- 24시간 이내 게시

---

## 7. 설정 (zod + dotenv)

모든 동작은 환경변수로 제어한다.

```typescript
const settingsSchema = z.object({
  SEND_HOUR:         z.coerce.number().int().min(0).max(23).default(8),
  SEND_MINUTE:       z.coerce.number().int().min(0).max(59).default(0),
  TIMEZONE:          z.string().default('Asia/Seoul'),
  ARTICLE_COUNT:     z.coerce.number().int().min(1).max(20).default(5),
  ARTICLE_LANGUAGE:  z.string().default('ko'),
  GEMINI_API_KEY:    z.string().min(1),
  GEMINI_MODEL:      z.string().default('gemini-2.5-flash'),
  SMTP_HOST:         z.string().default('smtp.gmail.com'),
  SMTP_PORT:         z.coerce.number().int().default(587),
  SMTP_USER:         z.string().min(1),
  SMTP_PASSWORD:     z.string().min(1),
  RECIPIENT_EMAILS:  z.string().min(1),   // 콤마 구분
  DATA_PATH:         z.string().default('./data/article_mailer.json'),
});
```

**.env.example**

```env
SEND_HOUR=8
SEND_MINUTE=0
TIMEZONE=Asia/Seoul

ARTICLE_COUNT=5
ARTICLE_LANGUAGE=ko

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=gmail-app-password

RECIPIENT_EMAILS=a@example.com,b@example.com

DATA_PATH=./data/article_mailer.json
```

---

## 8. 스토리지 (JSON 파일)

SQLite 대신 JSON 파일 사용. 하루 수십 건 규모에서 성능 문제 없음.

```typescript
interface StoreData {
  sentArticles: Array<{
    url: string;
    title: string;
    source: string;
    sentAt: string;   // ISO 8601
  }>;
  sendLogs: Array<{
    runAt: string;
    articleCount: number;
    recipientCount: number;
    status: 'success' | 'partial' | 'failed';
    errorMessage?: string;
    createdAt: string;
  }>;
}
```

---

## 9. Gemini API 프롬프트 설계

### 1단계: 후보 선별 (screening)

```
당신은 AI/ML 전문 뉴스 편집장입니다.
아래 아티클 후보 목록에서 정확히 {total}개를 선별하세요.

카테고리별 선별 기준:
- impact ({impact_count}개): AI가 세상을 실질적으로 변화시키는 사례
- trend ({trend_count}개): AI 기술 동향, 모델 출시, 업계 소식

JSON 배열로만 응답: [{"index": 0, "category": "impact"}, ...]
```

### 2단계: 최종 선택 + 요약

```
당신은 AI/ML 전문 뉴스 편집자입니다.
아래 {total}개 아티클에서 최종 {final_count}개를 선택하여 요약하세요.

JSON 배열로만 응답:
[{
  "index": 0,
  "category": "impact",
  "one_liner": "한 줄 요약 (50자 이내)",
  "body": "3~5문장 요약",
  "importance": "상 | 중 | 하",
  "read_time_min": 3
}]
```

- 응답 모드: `responseMimeType: "application/json"`
- 재시도: 최대 2회 (exponential backoff)

---

## 10. 이메일 템플릿 (Handlebars)

```
제목: [AI 데일리] {{formattedDate}} | 오늘의 AI 아티클 {{count}}선

본문 (HTML — src/templates/email.html):
  {{#each items}}
    중요도 배지, 출처, 읽기 시간
    제목
    한 줄 요약
    본문 요약
    [원문 읽기 →] 링크
  {{/each}}
```

---

## 11. 에러 처리 전략

| 상황 | 처리 |
|---|---|
| RSS fetch 실패 | 해당 소스 스킵, 다음 소스로 보충 |
| 본문 크롤링 실패 | `fallbackDescription`으로 대체 |
| Gemini API 실패 | 최대 2회 재시도 후 해당 아티클 제외 |
| 아티클 N개 미만 | 가용한 아티클만으로 발송 |
| SMTP 발송 실패 | 최대 3회 재시도 후 로그 기록 |

---

## 12. 디렉토리 구조

```
article-mailer/
├── bin/
│   └── article-mailer.js   # npm bin 진입점 (shebang 래퍼)
├── src/
│   ├── index.ts             # CLI + 스케줄러 진입점
│   ├── settings.ts          # zod 설정 스키마
│   ├── pipeline.ts          # 전체 파이프라인 조율
│   ├── summarizer.ts        # Gemini API 2단계 요약
│   ├── mailer.ts            # SMTP 발송 + Handlebars 렌더링
│   ├── logger.ts            # pino 로거
│   ├── collector/
│   │   ├── base.ts          # Article 타입, AbstractCollector
│   │   ├── hackerNews.ts    # HackerNewsCollector + crawlArticleContent
│   │   ├── rss.ts           # RSSCollector
│   │   └── arxiv.ts         # ArXivCollector
│   ├── db/
│   │   └── repository.ts    # JSON 파일 기반 발송 이력 관리
│   └── templates/
│       ├── email.html       # Handlebars HTML 템플릿
│       └── email.txt        # Handlebars TXT 템플릿
├── data/                    # .gitignore — JSON 스토리지
├── dist/                    # .gitignore — tsc 컴파일 결과
├── docs/
│   └── design.md
├── package.json
├── tsconfig.json
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── AGENTS.md
```

---

## 13. 사용자 경험 (UX 흐름)

두 가지 실행 경로를 지원한다. `.env` 파일 형식은 동일하다.

---

### 경로 A — Docker만 있는 경우 (스케줄 자동 실행)

**대상**: 서버에 Docker만 설치된 사용자. 한 번 설정하면 매일 자동 발송.

```bash
# 1. 파일 2개 받기
curl -O https://raw.githubusercontent.com/.../docker-compose.yml
curl -O https://raw.githubusercontent.com/.../.env.example

# 2. 환경변수 설정
mv .env.example .env
# .env 편집: API 키, 이메일 정보, 수신자, 발송 시각

# 3. 실행 (백그라운드 데몬)
docker compose up -d

# 로그 확인
docker compose logs -f
```

**docker-compose.yml** (사용자가 받는 파일 — 소스 불필요):
```yaml
services:
  article-mailer:
    image: toasting/article-mailer:latest   # Docker Hub 퍼블리시 이미지
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data                    # 발송 이력 영속화
```

- `restart: unless-stopped` → 서버 재시작 시 자동 복구
- `.env`의 `SEND_HOUR` / `SEND_MINUTE` / `TIMEZONE` 으로 발송 시각 제어
- 컨테이너 내부에서 `node-cron`이 스케줄 실행

---

### 경로 B — Node.js만 있는 경우 (수동 또는 외부 cron)

**대상**: 로컬 머신이나 서버에 Node.js 설치된 사용자.

```bash
# 1. .env 파일 준비 (현재 디렉토리)
curl -O https://raw.githubusercontent.com/.../.env.example
mv .env.example .env
# .env 편집

# 2. 즉시 실행 (테스트)
npx article-mailer --run-now

# 3. 아티클 수 지정
npx article-mailer --run-now --count 3

# 4. 드라이런 (요약·발송 없이 수집만)
npx article-mailer --dry-run

# 5. 스케줄러 모드 (프로세스 유지)
npx article-mailer
```

**자동화가 필요한 경우** — 시스템 cron에 등록:
```bash
# crontab -e
0 8 * * * cd /home/user/mailer && npx article-mailer --run-now >> /var/log/article-mailer.log 2>&1
```

또는 글로벌 설치 후:
```bash
npm install -g article-mailer
article-mailer --run-now
```

---

### .env 필수 항목 요약

| 항목 | 설명 | 예시 |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio에서 발급 | `AIza...` |
| `SMTP_USER` | 발신 Gmail 주소 | `you@gmail.com` |
| `SMTP_PASSWORD` | Gmail 앱 비밀번호 | `xxxx xxxx xxxx xxxx` |
| `RECIPIENT_EMAILS` | 수신자 (콤마 구분) | `a@example.com,b@example.com` |
| `SEND_HOUR` | 발송 시각 (0~23) | `8` |
| `SEND_MINUTE` | 발송 분 (0~59) | `0` |
| `TIMEZONE` | 타임존 | `Asia/Seoul` |

나머지는 기본값이 있어 생략 가능.

---

### CLI 플래그 전체

| 플래그 | 설명 |
|---|---|
| _(없음)_ | 스케줄러 모드 — 프로세스 유지, 지정 시각에 자동 실행 |
| `--run-now` | 즉시 1회 실행 후 종료 |
| `--count N` | 수집 아티클 수 override (기본: `ARTICLE_COUNT`) |
| `--dry-run` | 수집·크롤링까지만 실행, Gemini 요약·발송 스킵 |

---

## 14. 실행 방법 (개발)

```bash
npm install
npm run dev               # tsx로 직접 실행 (스케줄러 모드)
npm run dev -- --run-now  # 즉시 실행
npm run build             # tsc 컴파일
npm start                 # 컴파일된 dist/ 실행
```

---

## 15. 배포

### npm 배포

```bash
npm run build    # tsc + templates 복사
npm publish      # npm registry 배포
```

`package.json` 핵심 필드:
```json
{
  "bin": { "article-mailer": "./bin/article-mailer.js" },
  "files": ["dist", "bin"],
  "scripts": {
    "build": "tsc && cp -r src/templates dist/templates",
    "prepublishOnly": "npm run build"
  }
}
```

### Docker Hub 배포

```bash
docker build -t toasting/article-mailer:latest .
docker push toasting/article-mailer:latest
```

사용자는 `docker-compose.yml` + `.env` 두 파일만 있으면 소스 없이 실행 가능.
