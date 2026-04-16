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

* Python 3.12 이상
* Gmail 앱 비밀번호 (또는 SMTP 서버 계정)
* Google Gemini API 키

## 설정 방법

1. `.env.example` 파일을 참고하여 `.env` 파일을 생성합니다.
   ```bash
   cp .env.example .env
   ```
   또는 개발용 템플릿(수신자 사전 설정)을 사용할 수 있습니다.
   ```bash
   cp .env.dev .env
   ```
2. `.env` 파일에 실제 크리덴셜을 입력합니다.

* `GEMINI_API_KEY`: Google Gemini API 키 ([AI Studio](https://aistudio.google.com/apikey)에서 발급)
* `SMTP_USER`, `SMTP_PASSWORD`: 발송용 Gmail 계정과 앱 비밀번호
* `RECIPIENT_EMAILS`: 수신자 이메일 주소 (쉼표로 구분하여 여러 명 지정 가능)
* `SEND_HOUR`, `SEND_MINUTE`: 메일 발송을 원하는 시각
* `ARTICLE_COUNT`: 하루에 수집할 아티클 개수

## 실행 방법

### 1. 스케줄러 모드
설정한 시각에 맞춰 매일 자동으로 실행됩니다.
```bash
python -m src.main
```

### 2. 즉시 실행 (수동)
스케줄과 상관없이 지금 바로 아티클을 수집하고 발송합니다.
```bash
python -m src.main --run-now
```
특정 개수의 아티클만 수집하고 싶다면 `--count` 옵션을 사용합니다.
```bash
python -m src.main --run-now --count 3
```

### 3. Docker 실행
```bash
docker compose up -d
```

## 프로젝트 구조

* `src/main.py`: 프로그램 진입점 및 스케줄러 설정
* `src/pipeline.py`: 수집, 요약, 발송 전 과정을 조율하는 파이프라인
* `src/collector/`: 소스별 아티클 수집 로직 (Hacker News, RSS 등)
* `src/summarizer.py`: Gemini API를 이용한 아티클 요약
* `src/mailer.py`: SMTP를 이용한 이메일 발송
* `src/db/`: 발송 이력 관리를 위한 데이터베이스 모델 및 처리
* `templates/`: 이메일 본문 작성을 위한 Jinja2 HTML/TXT 템플릿
* `data/`: SQLite 데이터베이스 파일 저장 경로
