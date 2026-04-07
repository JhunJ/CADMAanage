# CAD Manage API - Python 3.11
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app

# 기본 포트
EXPOSE 8000

# DB 준비 후 마이그레이션 적용 후 uvicorn 실행 (진입 스크립트 대신 인라인)
CMD ["/bin/sh", "-c", "until alembic upgrade head 2>/dev/null; do echo Waiting for DB...; sleep 2; done; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
