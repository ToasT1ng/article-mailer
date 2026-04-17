# TODO

PR #1 리뷰 및 Copilot 코멘트를 기반으로 정리한 개선 항목.

---

## 🔴 Critical

없음.

---

## 🟠 Major

### `src/pipeline.ts` — sendMail 에러 미처리
`sendMail()` 호출이 try/catch 없이 노출되어 있음. SMTP가 재시도 후에도 실패하면 예외가 throw되면서 `markSent()`와 `addLog()`가 모두 스킵됨. 다음 실행 시 같은 아티클이 중복 발송될 수 있고, 실패 이력도 남지 않음.

- `sendMail()` 를 try/catch로 감싸기
- 성공 시 `markSent()` + `addLog({ status: "success" })`
- 실패 시 `addLog({ status: "failed", errorMessage: ... })` 기록 (markSent 생략)
- 소스: `src/pipeline.ts:61-69` / Copilot 코멘트

---

### `src/mailer.ts` — 잘못된 Handlebars 타입
`loadTemplate()` 반환 타입에 `HandlebarsTemplateDelegate`를 사용하고 있으나 이 타입은 handlebars 패키지에서 export되지 않음. `tsc`에서 타입 오류 발생.

- `HandlebarsTemplateDelegate` → `Handlebars.TemplateDelegate` 로 수정
- 소스: `src/mailer.ts:11` / Copilot 코멘트

---

### `src/summarizer.ts` — Gemini 응답 JSON 파싱 불안정
`callGemini()`가 응답 텍스트를 즉시 `JSON.parse()`함. Gemini가 코드 펜스(` ```json ... ``` `)나 앞뒤 텍스트를 붙여 반환하면 파싱 실패로 파이프라인 전체가 중단됨.

- 응답 텍스트에서 첫 번째 JSON 배열/객체를 정규식으로 추출 후 파싱
- 파싱 실패 시 빈 배열 반환 또는 재시도 처리
- 소스: `src/summarizer.ts:110-118` / Copilot 코멘트

---

### `src/summarizer.ts` — screen() 결과 미검증
`screen()`이 Gemini 출력을 그대로 신뢰함. 중복 인덱스, 범위 초과 인덱스, `total`보다 많거나 적은 결과를 반환해도 아무 처리 없이 통과됨.

- 인덱스 범위 체크 (0 ≤ index < articles.length)
- 중복 인덱스 제거 (Set 사용)
- 결과를 `total`개로 clamp (부족 시 입력 배열 상위 N개로 fallback)
- 소스: `src/summarizer.ts:42-67` / Copilot 코멘트

---

### 테스트 없음
Python 버전에 있던 pytest 테스트 스위트가 제거되었고, TypeScript 테스트가 전혀 추가되지 않음. 핵심 로직(파이프라인, 요약기, 메일러)에 대한 단위 테스트 최소한 필요.

- `jest` 또는 `vitest` + `nock`/`msw`로 테스트 환경 구성
- 최소 범위: `summarizer.screen()`, `summarizer.selectAndSummarize()`, `pipeline.runPipeline()` (sendMail mocking)
- 소스: 내부 리뷰

---

## 🟡 Minor

### `src/pipeline.ts` — filterUnsent O(n²)
`unsentUrls.includes(a.url)` 로 필터링하는 부분이 O(n²). URL 목록이 커지면 느려짐.

- `filterUnsent()` 반환값을 `Set<string>`으로 변경하거나, 호출 측에서 `new Set(unsentUrls)`로 변환 후 `.has()` 사용
- 소스: `src/pipeline.ts:31` / Copilot 코멘트

---

### `src/pipeline.ts` — no_articles 시 로그 미기록
`sorted.length === 0` 분기에서 경고 로그만 남기고 `addLog()`를 호출하지 않음. `no_summaries` 경로와 달리 실행 이력이 누락됨.

- `addLog({ status: "failed", errorMessage: "수집된 아티클 없음" })` 추가
- 소스: `src/pipeline.ts:41-44` / Copilot 코멘트

---

### `src/mailer.ts` — 빈 수신자 목록 미처리
`RECIPIENT_EMAILS`가 `","` 나 공백일 경우 `getRecipients()`가 빈 배열을 반환하고, 빈 `to` 필드로 SMTP 발송을 시도해 실패함.

- `sendMail()` 초입에 `recipients.length === 0` 체크 추가
- 해당 시 경고 로그 후 조기 반환
- 소스: `src/mailer.ts:18-22` / Copilot 코멘트

---

### `src/summarizer.ts` — 프롬프트 컨텐츠 길이 미제한
`selectAndSummarize()` 프롬프트에 `rawContent`를 길이 제한 없이 삽입. `rawContent`는 최대 8000자까지 허용되어 있어 아티클 수가 많으면 모델 입력 한도 초과 위험.

- 프롬프트 삽입 전 컨텐츠를 3000~4000자로 truncate
- 소스: `src/summarizer.ts:70-81` / Copilot 코멘트

---

### `src/index.ts` — --count 입력값 미검증
`--count` 옵션이 zod 스키마의 min/max(1~20)와 무관하게 그대로 적용됨. 0이나 999 같은 값도 통과됨.

- 파싱 직후 범위 체크 추가 (1 ≤ count ≤ 20 또는 settings 스키마의 max와 동기화)
- 유효하지 않으면 명확한 오류 메시지 후 종료
- 소스: `src/index.ts:13-16` / Copilot 코멘트

---

### `package.json` — engines.node 버전 불일치
`cheerio@1.2.0`과 의존성 `undici@7.x`가 `node >=20.18.1`을 요구하지만, `package.json`의 `engines.node`는 `>=20.0.0`으로 더 느슨하게 설정되어 있음.

- `"node": ">=20.18.1"` 로 수정
- Docker base image도 동일 버전으로 맞출 것
- 소스: `package.json:20` / Copilot 코멘트

---

### `docker-compose.yml` — build 컨텍스트 제거
`build: .` 가 제거되고 퍼블리시된 이미지(`toasting/article-mailer:latest`)만 참조하도록 변경됨. 이미지를 먼저 push하지 않으면 로컬에서 `docker compose up`이 실패함.

- `build: .` 를 `image:` 와 함께 병기하거나, 개발/배포용 compose 파일을 분리
- 소스: `docker-compose.yml:1-6` / Copilot 코멘트

---

### `src/db/repository.ts` — PR 설명과 구현 불일치
PR 설명에 "SQLite-backed article repository"라고 적혀 있지만 실제 구현은 JSON 파일 기반.

- PR 설명 업데이트 (이미 README는 수정됨)
- 필요 시 `docs/design.md` 내 SQLite 언급도 JSON으로 정정
- 소스: `src/db/repository.ts:25-33` / Copilot 코멘트

---

## 📋 처리하지 않을 항목

| 항목 | 이유 |
|------|------|
| HackerNews 200개 병렬 fetch | 일간 크론 1회 실행 기준 실용적으로 문제없음 |
