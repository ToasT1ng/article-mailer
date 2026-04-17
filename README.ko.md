# article-mailer

[![npm version](https://img.shields.io/npm/v/article-mailer.svg)](https://www.npmjs.com/package/article-mailer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🇺🇸 [English documentation](./README.md)

매일 최신 AI 아티클을 수집하고 요약하여 이메일로 발송하는 자동화 도구입니다.

## 동작 방식

등록된 소스에서 최신 AI 관련 아티클을 수집한 뒤 Gemini API를 통해 핵심 내용을 요약합니다. 요약된 결과는 HTML 이메일 형식으로 렌더링되어 지정된 수신자들에게 전송됩니다. 모든 과정은 비동기로 처리되며, 이미 발송된 아티클의 중복 발송을 방지합니다.

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

### npm (권장)

```bash
npm install -g article-mailer
```

### npx (설치 없이 바로 실행)

```bash
npx article-mailer --run-now
```

### 소스코드에서 직접 빌드

```bash
git clone https://github.com/ToasT1ng/article-mailer.git
cd article-mailer
npm install
npm run build
```

## 설정 방법

실행할 디렉토리에 `.env` 파일을 생성합니다.

```bash
# 스케줄러를 상주시킬 디렉토리 (예시)
mkdir ~/article-mailer && cd ~/article-mailer
```

아래 내용을 `.env` 파일로 저장하고 값을 채웁니다.

```dotenv
# Gemini API
GEMINI_API_KEY=            # 필수. https://aistudio.google.com/apikey 에서 발급
GEMINI_MODEL=gemini-2.5-flash

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=                 # 필수. 발송용 Gmail 계정
SMTP_PASSWORD=             # 필수. Gmail 앱 비밀번호

# 수신자 (쉼표로 여러 명 지정 가능)
RECIPIENT_EMAILS=          # 필수. 예: a@gmail.com,b@gmail.com

# 스케줄 설정
SEND_HOUR=8
SEND_MINUTE=0
TIMEZONE=Asia/Seoul

# 아티클 설정
ARTICLE_COUNT=5            # 하루 발송 개수 (최대 20)
# 요약 출력 언어. 언어의 영어 전체 이름을 사용하세요.
# 예시: English, Korean, Japanese, Spanish, French
# 참고: importance 값은 언어 설정에 관계없이 항상 영어로 고정됩니다 (high, medium, low).
ARTICLE_LANGUAGE=English

# 데이터 저장 경로
DATA_PATH=./data/article_mailer.json

# 추가 RSS 피드 설정 파일 경로 (선택 사항, 없으면 무시)
FEEDS_PATH=./feeds.json
```

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
| `ARTICLE_LANGUAGE` | `English` | 요약 출력 언어. 언어의 영어 전체 이름을 사용하세요 (예: `English`, `Korean`, `Japanese`, `Spanish`). `importance` 값은 언어 설정과 무관하게 항상 영어로 고정됩니다. |
| `DATA_PATH` | `./data/article_mailer.json` | 발송 이력 저장 경로 |
| `FEEDS_PATH` | `./feeds.json` | 추가 RSS 피드 설정 파일 경로 (선택 사항) |

## 커스텀 RSS 피드 추가

명령을 실행하는 디렉토리에 `feeds.json` 파일을 생성하면 기본 소스에 **추가**됩니다. 기본 피드는 항상 포함됩니다.

```json
[
  { "url": "https://d2.naver.com/feed.xml", "source": "Naver D2" },
  { "url": "https://tech.kakao.com/feed/", "source": "Kakao Tech" },
  { "url": "https://engineering.linecorp.com/ko/feed", "source": "LINE Engineering" },
  { "url": "https://www.aitimes.com/rss/allArticle.xml", "source": "AI Times Korea" }
]
```

`feeds.json`이 없으면 무시됩니다. `.env`의 `FEEDS_PATH`로 파일 경로를 변경할 수 있습니다.

## 실행 방법

### 1. 스케줄러 모드
설정한 시각에 맞춰 매일 자동으로 실행됩니다.
```bash
article-mailer
# 소스코드 빌드 시
node dist/index.js
```

### 2. 즉시 실행 (수동)
스케줄과 상관없이 지금 바로 아티클을 수집하고 발송합니다.
```bash
article-mailer --run-now
# 특정 개수만 수집
article-mailer --run-now --count 3
```

### 3. 드라이런 (발송 없이 수집만)
```bash
article-mailer --dry-run
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

## License

MIT © [ToasT1ng](https://github.com/ToasT1ng)
