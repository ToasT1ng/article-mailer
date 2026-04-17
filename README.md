# article-mailer

매일 최신 AI 아티클을 수집하고 요약하여 이메일로 발송하는 자동화 도구입니다.

## 동작 방식

등록된 소스에서 최신 AI 관련 아티클을 수집한 뒤 Gemini API를 통해 핵심 내용을 요약합니다. 요약된 결과는 HTML 이메일 형식으로 렌더링되어 지정된 수신자들에게 전송됩니다. 모든 과정은 비동기로 처리되며, SQLite를 사용하여 이미 발송된 아티클의 중복 발송을 방지합니다.

## 아티클 수집 소스

* Hacker News (AI 키워드 필터링 및 점수 기반)
* ArXiv cs.AI
* The Batch (DeepLearning.AI)
* MIT Technology Review (AI 섹션)
* VentureBeat (AI 섹션)

## 사전 준비 사항

* Node.js 20 이상
* Gmail 앱 비밀번호 (또는 SMTP 서버 계정)
* Google Gemini API 키

## 설치 방법

```bash
npm install
npm run build
```

## 설정 방법

1. `.env.example` 파일을 참고하여 `.env` 파일을 생성합니다.
   ```bash
   cp .env.example .env
   ```
2. `.env` 파일에 실제 크리덴셜을 입력합니다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `GEMINI_API_KEY` | (필수) | Google Gemini API 키 ([AI Studio](https://aistudio.google.com/apikey)에서 발급) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | 사용할 Gemini 모델명 |
| `SMTP_USER` | (필수) | 발송용 Gmail 계정 |
| `SMTP_PASSWORD` | (필수) | Gmail 앱 비밀번호 |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP 서버 주소 |
| `SMTP_PORT` | `587` | SMTP 포트 |
| `RECIPIENT_EMAILS` | (필수) | 수신자 이메일 주소 (쉼표로 구분하여 여러 명 지정 가능) |
| `SEND_HOUR` | `8` | 메일 발송 시각 (시, 0-23) |
| `SEND_MINUTE` | `0` | 메일 발송 시각 (분, 0-59) |
| `TIMEZONE` | `Asia/Seoul` | 스케줄 기준 타임존 |
| `ARTICLE_COUNT` | `5` | 하루에 발송할 아티클 개수 (최대 20) |
| `ARTICLE_LANGUAGE` | `ko` | 요약 언어 (`ko` 또는 `en`) |
| `DATA_PATH` | `./data/article_mailer.json` | 발송 이력 저장 경로 |

## 실행 방법

### 1. 스케줄러 모드
설정한 시각에 맞춰 매일 자동으로 실행됩니다.
```bash
node dist/index.js
# 또는 개발 모드
npm run dev
```

### 2. 즉시 실행 (수동)
스케줄과 상관없이 지금 바로 아티클을 수집하고 발송합니다.
```bash
node dist/index.js --run-now
```
특정 개수의 아티클만 수집하고 싶다면 `--count` 옵션을 사용합니다.
```bash
node dist/index.js --run-now --count 3
```

### 3. 드라이런 (발송 없이 수집만)
```bash
node dist/index.js --dry-run
```

### 4. Docker 실행
```bash
docker compose up -d
```

## 프로젝트 구조

```
src/
├── index.ts          # 진입점 및 스케줄러 설정
├── pipeline.ts       # 수집, 요약, 발송 전 과정을 조율하는 파이프라인
├── settings.ts       # 환경변수 설정 (zod)
├── summarizer.ts     # Gemini API를 이용한 아티클 요약
├── mailer.ts         # SMTP를 이용한 이메일 발송
├── logger.ts         # pino 구조화 로거
├── collector/        # 소스별 아티클 수집 로직
│   ├── base.ts
│   ├── hackerNews.ts
│   ├── rss.ts
│   └── arxiv.ts
├── db/               # 발송 이력 관리
│   └── repository.ts
├── templates/        # 이메일 본문 Handlebars 템플릿
└── utils/
    └── retry.ts      # 지수 백오프 재시도 유틸
```
