FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 (lxml 빌드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# 소스 코드 및 설정 복사
COPY pyproject.toml .
COPY src/ ./src/
COPY templates/ ./templates/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY tests/ ./tests/

# 의존성 설치
RUN pip install --no-cache-dir ".[dev]"

# data 디렉토리 생성
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////app/data/article_mailer.db

CMD ["python", "-m", "src.main"]
