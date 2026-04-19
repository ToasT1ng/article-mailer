# CLAUDE.md

Claude Code가 이 프로젝트에서 작업할 때 참고하는 핵심 가이드. 상세 규칙은 `AGENTS.md` 참조.

## 프로젝트

매일 AI 뉴스를 수집·요약하여 이메일로 발송하는 TypeScript/Node.js CLI 도구.

## 주요 커맨드

```bash
npm run build          # tsc 빌드
npm test               # vitest 전체 실행
npx tsx src/index.ts --dry-run   # 빌드 없이 dry run (수집만, 발송·Gemini 호출 없음)
node dist/index.js --dry-run     # 빌드 후 dry run
node dist/index.js --run-now     # 즉시 실행 (Gemini 호출 + 메일 발송)
```

## 테스트 원칙

- 기능 검증은 반드시 `--dry-run` 모드로 먼저 진행한다.
- 실제 Gemini API 호출이 수반되는 검증은 **사용자에게 먼저 확인**한다 (API 비용 발생).

## 파이프라인 흐름

```
수집 (HN / RSS / ArXiv)
  → 중복 제거 + 미발송 필터
  → score 가중 정렬
  → Gemini screen()         ← title + fallbackDescription으로 후보 선별
  → crawlContents()         ← Readability → cheerio fallback, 동시 4개 제한
  → Gemini selectAndSummarize()
  → 이메일 발송 + DB 기록
```

## 브랜치 / 커밋

- `main`, `develop`에 직접 커밋 금지. 작업 브랜치에서 진행.
- 브랜치명: `git-branch-convention` 스킬 사용.
- 커밋: `git-commit-convention` 스킬 사용 (gitmoji 형식).
- PR: `develop` → `develop`, 버전 릴리스만 `develop` → `main`.

## 환경변수

`.env.example` 참조. 필수값: `GEMINI_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, `RECIPIENT_EMAILS`.
