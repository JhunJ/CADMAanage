# AGENTS.md

## Cursor Cloud specific instructions

### Overview
CAD Manage MVP is a DWG/DXF file management and version control platform. The stack is Python 3.12 + FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL/PostGIS.

### Services

| Service | How to start | Port |
|---------|-------------|------|
| PostGIS (PostgreSQL 16 + PostGIS 3.4) | `docker compose up -d postgis` | 5432 |
| FastAPI dev server | `.venv/bin/uvicorn app.main:app --reload --port 8000` | 8000 |

### Environment variables
Copy `.env.example` to `.env`. The key variable is `DATABASE_URL` which defaults to `postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage`.

### Starting the development environment
1. Start PostGIS: `docker compose up -d postgis`
2. Run migrations: `DATABASE_URL="postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage" .venv/bin/python -m alembic upgrade head`
3. Start API: `DATABASE_URL="postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage" .venv/bin/uvicorn app.main:app --reload --port 8000`

### Running tests
```bash
DATABASE_URL="postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage" .venv/bin/python -m pytest tests/ -v
```

### Important notes
- Docker must be running (with `fuse-overlayfs` storage driver and `iptables-legacy`) for PostGIS.
- The `DATABASE_URL` env var must be exported before running alembic or uvicorn since `alembic.ini` has a placeholder URL and the real URL comes from `app/config.py` via env var / `.env` file.
- ODA File Converter is not available on Linux; DXF direct upload works when `DEV_ALLOW_DXF_UPLOAD=true` (default).
- A sample DXF can be generated via `scripts/make_sample_dxf.py`.
- The project uses Python 3.12 (system python), not 3.11. Both are compatible per `requirements.txt` (3.11+).
