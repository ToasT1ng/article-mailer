# article-mailer

[![npm version](https://img.shields.io/npm/v/article-mailer.svg)](https://www.npmjs.com/package/article-mailer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🇰🇷 [한국어 문서 보기](./README.ko.md)

A CLI tool that automatically collects the latest AI articles daily, summarizes them using the Gemini API, and delivers them to your inbox.

## How It Works

Fetches articles from registered sources, summarizes key content via the Gemini API, renders the result as an HTML email, and sends it to configured recipients. All sources are fetched in parallel, and previously sent articles are filtered out to prevent duplicate delivery.

## Article Sources

* Hacker News (AI keyword filter + score-based ranking)
* ArXiv cs.AI
* The Batch (DeepLearning.AI)
* MIT Technology Review (AI section)
* VentureBeat (AI section)

## Prerequisites

* Node.js 20+
* Gmail App Password (or any SMTP account)
* Google Gemini API key

## Installation

### npm (recommended)

```bash
npm install -g article-mailer
```

### npx (no installation required)

```bash
npx article-mailer --run-now
```

### Build from source

```bash
git clone https://github.com/ToasT1ng/article-mailer.git
cd article-mailer
npm install
npm run build
```

## Configuration

Create a `.env` file in the directory where you'll run the command.

```bash
# Example: create a dedicated directory for the scheduler
mkdir ~/article-mailer && cd ~/article-mailer
```

Copy the template below into `.env` and fill in the values.

```dotenv
# Gemini API
GEMINI_API_KEY=            # Required. Get yours at https://aistudio.google.com/apikey
GEMINI_MODEL=gemini-2.5-flash

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=                 # Required. Gmail account for sending
SMTP_PASSWORD=             # Required. Gmail App Password

# Recipients (comma-separated for multiple)
RECIPIENT_EMAILS=          # Required. e.g. a@gmail.com,b@gmail.com

# Schedule
SEND_HOUR=8
SEND_MINUTE=0
TIMEZONE=Asia/Seoul

# Article settings
ARTICLE_COUNT=5            # Articles per day (max 20)
ARTICLE_LANGUAGE=English   # Use the full English name of the language (e.g. English, Korean, Japanese)

# Data path
DATA_PATH=./data/article_mailer.json

# Custom RSS feeds file path (optional, ignored if not present)
FEEDS_PATH=./feeds.json
```

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | required | Google Gemini API key ([AI Studio](https://aistudio.google.com/apikey)) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `SMTP_USER` | required | Sender Gmail account |
| `SMTP_PASSWORD` | required | Gmail App Password |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server host |
| `SMTP_PORT` | `587` | SMTP server port |
| `RECIPIENT_EMAILS` | required | Recipient emails (comma-separated) |
| `SEND_HOUR` | `8` | Scheduled send hour (0–23) |
| `SEND_MINUTE` | `0` | Scheduled send minute (0–59) |
| `TIMEZONE` | `Asia/Seoul` | Scheduler timezone |
| `ARTICLE_COUNT` | `5` | Articles per delivery (max 20) |
| `ARTICLE_LANGUAGE` | `English` | Output language for summaries. Use the full English name of the language (e.g. `English`, `Korean`, `Japanese`, `Spanish`). Note: `importance` values are always in English (`high`, `medium`, `low`). |
| `DATA_PATH` | `./data/article_mailer.json` | Path for sent history storage |
| `FEEDS_PATH` | `./feeds.json` | Path to custom RSS feeds file (optional) |

## Adding Custom RSS Feeds

Create a `feeds.json` file in the same directory where you run the command. These feeds are **appended** to the built-in sources — the defaults are always included.

```json
[
  { "url": "https://d2.naver.com/feed.xml", "source": "Naver D2" },
  { "url": "https://tech.kakao.com/feed/", "source": "Kakao Tech" },
  { "url": "https://engineering.linecorp.com/ko/feed", "source": "LINE Engineering" },
  { "url": "https://www.aitimes.com/rss/allArticle.xml", "source": "AI Times Korea" }
]
```

If `feeds.json` does not exist, it is silently ignored. You can use a different path by setting `FEEDS_PATH` in your `.env`.

## Usage

### 1. Scheduler mode
Runs automatically every day at the configured time.
```bash
article-mailer
# If built from source
node dist/index.js
```

### 2. Run immediately
Collect and send articles right now, regardless of schedule.
```bash
article-mailer --run-now
# Limit the number of articles
article-mailer --run-now --count 3
```

### 3. Dry run (collect only, no email sent)
```bash
article-mailer --dry-run
```

### 4. Docker
```bash
docker compose up -d
```

## Project Structure

```
src/
├── index.ts          # Entry point and scheduler
├── pipeline.ts       # Orchestrates collect → summarize → send
├── settings.ts       # Environment variable schema (zod)
├── summarizer.ts     # Gemini API summarization
├── mailer.ts         # SMTP email delivery
├── logger.ts         # Structured logger (pino)
├── collector/        # Per-source article collectors
│   ├── base.ts
│   ├── hackerNews.ts
│   ├── rss.ts
│   └── arxiv.ts
├── db/               # Sent history management
│   └── repository.ts
├── templates/        # Handlebars email templates
└── utils/
    └── retry.ts      # Exponential backoff retry utility
```

## License

MIT © [ToasT1ng](https://github.com/ToasT1ng)
