#!/bin/sh
set -e
# PostGIS 준비 대기
until alembic upgrade head 2>/dev/null; do
  echo "Waiting for DB..."
  sleep 2
done
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
