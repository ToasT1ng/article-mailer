# AGENTS.md

이 프로젝트에서 코드를 작성할 때 따라야 하는 규칙과 컨텍스트.

## 프로젝트 개요

매일 AI 관련 아티클을 수집하고 Gemini API로 요약하여 이메일로 발송하는 **TypeScript/Node.js** 자동화 도구.

## 기술 스택

- **Node.js 20+**, TypeScript 5.4+, ESM 모듈
- `@google/generative-ai` (Gemini API SDK)
- `zod` (환경변수 스키마 검증)
- `rss-parser` (RSS 수집), `cheerio` (HTML 크롤링)
- `node-cron` (인프로세스 cron 스케줄러)
- `handlebars` (이메일 HTML/TXT 템플릿)
- `nodemailer` (SMTP 발송)
- `pino` + `pino-pretty` (구조화 로깅)
- `vitest` (테스트)
- JSON 파일 기반 데이터 저장 (`data/article_mailer.json`)

## 코드 컨벤션

- TypeScript strict 모드, 타입 힌트 필수
- `as any`, `@ts-ignore`, `type: ignore` 금지
- 주석과 로그 이벤트명은 한국어 허용
- 로거는 `logger.child({ module: "모듈명" })`으로 파일 최상단에 선언
- 로그 이벤트명은 `모듈명.동작` 형식 (예: `pipeline.start`, `mailer.sent`)
- import 시 `.js` 확장자 명시 (ESM 규칙)

## 아키텍처 규칙

- 진입점: `src/index.ts` → 빌드 후 `node dist/index.js`
- 파이프라인 흐름: 수집(`collector/`) → 크롤링 → 스크리닝 → 요약(`summarizer.ts`) → 발송(`mailer.ts`) → 이력 기록(`db/`)
- 모든 설정은 `src/settings.ts`의 `loadSettings()` (zod 기반)를 통해 환경변수로 주입. 하드코딩 금지.
- 수집기는 `AbstractCollector`를 상속하고 `async fetch(): Promise<Article[]>`를 구현
- 외부 수집은 `Promise.allSettled`로 병렬 처리, 개별 실패가 전체를 막지 않도록 함
- Gemini API 호출은 JSON 응답 모드 사용 (`responseMimeType: "application/json"`)
- SMTP 발송과 Gemini API 호출은 `withRetry()` (지수 백오프)로 감쌈
- 중복 발송 방지: `ArticleRepository.filterUnsent()`로 이미 발송된 URL 제외

## 아티클 카테고리

Gemini가 분류하는 3가지 카테고리:

- `trend_industry`: OpenAI·Anthropic·Google·Meta 등 주요 기업의 LLM 제품·서비스 동향 (전체의 약 60%)
- `impact`: AI가 의료·법률·교육 등 실제 산업에 적용되는 사례 (전체의 약 20%)
- `trend_llm`: LLM 아키텍처·학습 기법·벤치마크 등 모델 기술 연구 (전체의 약 20%)

## 요약 파이프라인 (2단계)

1. **`screen()`**: 수집된 후보군에서 카테고리 비율에 맞게 상위 N개 선별
2. **`selectAndSummarize()`**: 선별된 아티클을 크롤링 후 최종 요약 (`oneLiner`, `body`, `importance`, `readTimeMin`)

## 데이터 저장

- SQLite/ORM 없음. JSON 파일 단일 스토어 (`DATA_PATH`, 기본 `./data/article_mailer.json`)
- `ArticleRepository` 클래스가 로드/저장 담당
- Docker 볼륨으로 `data/` 디렉토리 마운트

## 테스트 규칙

- `vitest` 사용, 설정은 `vitest.config.mts`
- 외부 HTTP 요청은 `vi.fn()` 또는 `vi.spyOn()`으로 모킹
- Gemini API 호출 테스트 시 `vi.spyOn(summarizer['client'], ...)`으로 교체
- 테스트 공통 fixture는 `tests/conftest` 대신 각 테스트 파일 내 `beforeEach`/`vi.mock` 활용

## 브랜치 전략

- 모든 작업은 `develop` 브랜치를 기반으로 한다. `develop`에서 신규 브랜치를 생성하여 작업하고, 작업 완료 후 `develop`으로 머지한다.
- `main` 브랜치는 버전 업(npm 배포)이 수반되는 경우에만 `develop`에서 머지한다. 단순 README 업데이트 등 배포와 무관한 변경은 `main`에 직접 머지하지 않는다.
- 신규 브랜치 생성 시 로컬에 브랜치 관련 스킬(예: `git-branch-convention`)이 있으면 해당 스킬을 사용하여 브랜치명을 결정한다. 스킬을 찾지 못했다면 `git log --oneline origin/develop` 등으로 기존 브랜치 생성 내역을 확인하고 동일한 형식(prefix·케이스·구조)을 따른다.
- 브랜치 생성 후 작업을 시작하며, 완료 후 사용자에게 브랜치명을 알린다.

## 커밋 정책

- **`main` 브랜치에 직접 커밋하는 것은 절대 금지한다.** 사용자가 명시적으로 "main에 커밋해줘", "main에 직접 해줘"라고 요청한 경우에만 예외로 허용한다. 그 외 모든 커밋은 반드시 `develop` 또는 작업 브랜치에서 이루어진다.
- 커밋 메시지 작성 시 로컬에 커밋 관련 스킬(예: `git-commit-convention`)이 있으면 반드시 해당 스킬을 로드하여 따른다. 스킬이 없으면 기존 커밋 로그(`git log --oneline`)를 확인하고 동일한 형식(gitmoji·prefix·언어)을 따른다.

## npm 배포 정책

- `npm publish`는 사용자가 명시적으로 요청한 경우에만 직접 실행한다. 그 외의 경우(버전 bump만 요청, 코드 변경 완료 후 자동 배포 등)는 CI/CD 파이프라인을 통해 배포되도록 하며, 에이전트가 자의적으로 `npm publish`를 실행하지 않는다.

## 배포

- Docker: `Dockerfile` + `docker-compose.yml`
- 모든 설정은 `.env` 파일로 주입 (`.env.example` 참조)
- 빌드: `npm run build` (tsc + 템플릿 복사)
- 실행: `node dist/index.js` (스케줄러) | `node dist/index.js --run-now` (즉시) | `node dist/index.js --dry-run` (드라이런)
