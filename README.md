# CAD Manage MVP

DWG/DXF 업로드 → ODA 변환 → ezdxf 파싱 → PostgreSQL(PostGIS) 적재 → 버전 비교(ChangeSet) → 웹/API 조회 파이프라인 MVP입니다.

## 기술 스택

- **Python 3.11+**
- **FastAPI** - API 서버
- **SQLAlchemy 2.x + Alembic** - ORM 및 마이그레이션
- **PostgreSQL + PostGIS** - 공간 DB
- **BackgroundTasks** - 백그라운드 처리 (추후 Celery/Redis 확장 가능)
- **파일 저장** - 로컬 `./data/uploads` (추후 S3/MinIO 교체 가능)

## 요구사항

- Python 3.11+
- Docker, Docker Compose (권장)
- (선택) ODA File Converter CLI - DWG → DXF 변환용. 없으면 **DXF 직접 업로드** 또는 `DEV_ALLOW_DXF_UPLOAD=true`로 DXF 허용

## 설치 및 실행

### 1) Docker Compose로 한 번에 실행

```bash
# 프로젝트 루트에서
docker compose up -d

# PostGIS 준비 대기 후 마이그레이션
docker compose exec api alembic upgrade head

# API 확인
curl http://localhost:8000/health
```

- API: http://localhost:8000  
- 문서: http://localhost:8000/docs  
- Postgres: localhost:5432 (caduser / cadpass / cadmanage)

### 2) 로컬에서 API만 실행 (Postgres는 Docker)

**상세한 터미널 명령어·순서는 [LOCAL_RUN.md](LOCAL_RUN.md) 참고.**

요약:

```bash
# PostGIS만 띄우기
docker compose up -d postgis
# 마이그레이션 (로컬 Python)
export DATABASE_URL=postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage
alembic upgrade head

# 가상환경 및 의존성
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# API 실행
uvicorn app.main:app --reload --port 8000
```

### 3) 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage` |
| `UPLOAD_ROOT` | 업로드 파일 루트 | `./data/uploads` |
| `ODA_FC_PATH` | ODA File Converter 실행 파일 경로 | 없음 (없으면 DXF만 허용 가능) |
| `DEV_ALLOW_DXF_UPLOAD` | DXF 직접 업로드 허용 | `true` |

`.env.example`를 복사해 `.env`로 두고 필요한 값만 수정하면 됩니다.

### 4) 사내망(사설 IP)에서 인터넷에 공개할 때

Cloudflare DNS에 사설 IP(`172.x` 등)를 넣어도 **외부에서 원본까지 도달하지 않습니다.**  
**Cloudflare Tunnel(`cloudflared`)** 로 아웃바운드만 열고 `https://cadmanager.example.com` 형태로 노출하는 절차는 **[docs/CLOUDFLARE_PUBLIC_DEPLOY.md](docs/CLOUDFLARE_PUBLIC_DEPLOY.md)** 를 참고하세요.

## DB 마이그레이션

```bash
# 최신 마이그레이션 적용
alembic upgrade head

# 새 마이그레이션 생성 (스키마 변경 시)
alembic revision --autogenerate -m "설명"
```

## API 예시 (curl)

### 1) 사용자 생성

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"홍길동\",\"email\":\"hong@example.com\"}"
```

### 2) 프로젝트 생성

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"테스트 프로젝트\",\"code\":\"PRJ001\",\"created_by\":1}"
```

### 3) DXF 파일 업로드 (버전/커밋 생성)

```bash
# 첫 번째 버전
curl -X POST http://localhost:8000/api/projects/1/uploads \
  -F "file=@sample.dxf" \
  -F "created_by=1" \
  -F "version_label=v1"

# 두 번째 버전 (parent_commit_id로 이전 커밋 지정 → ChangeSet 생성)
curl -X POST http://localhost:8000/api/projects/1/uploads \
  -F "file=@sample_v2.dxf" \
  -F "created_by=1" \
  -F "version_label=v2" \
  -F "parent_commit_id=1"
```

### 4) 커밋 목록 / 단건 조회

```bash
curl http://localhost:8000/api/projects/1/commits
curl http://localhost:8000/api/commits/1
```

### 5) 엔티티 조회 (필터: layer, color, entity_type)

```bash
curl "http://localhost:8000/api/commits/1/entities"
curl "http://localhost:8000/api/commits/1/entities?layer=0&entity_type=LINE"
```

### 6) 블록 정의/배치 조회

```bash
curl http://localhost:8000/api/commits/1/blocks/defs
curl "http://localhost:8000/api/commits/1/blocks/inserts?name=BLOCK1"
```

### 7) ChangeSet 조회 (parent 대비)

```bash
curl http://localhost:8000/api/commits/2/changeset
```

### 8) DXF 내보내기 (옵션)

```bash
curl "http://localhost:8000/api/commits/1/export/dxf?layer=0" -o out.dxf
```

## 샘플 흐름 요약

1. **POST /api/users** → 사용자 생성  
2. **POST /api/projects** → 프로젝트 생성  
3. **POST /api/projects/{id}/uploads** → DXF(또는 DWG) 업로드 → 커밋 생성(status=PENDING), 백그라운드에서 파싱·적재·ChangeSet 후 status=READY  
4. **GET /api/projects/{id}/commits** → 커밋 목록  
5. **GET /api/commits/{id}/entities** → 엔티티 조회  
6. **GET /api/commits/{id}/changeset** → 이전 커밋 대비 변경분  

## 프로젝트 구조

```
app/
  main.py           # FastAPI 앱
  config.py         # 설정
  api/              # 라우터 (users, projects, uploads, commits, entities, blocks, changesets, export_dxf)
  db/               # 세션, Base
  models/           # SQLAlchemy 모델
  schemas/           # Pydantic 스키마
  services/         # storage, oda_converter, dxf_parser, fingerprint, changeset
  workers/          # commit_processor (백그라운드)
  utils/            # geom 등
alembic/            # 마이그레이션
```

## 테스트

```bash
pytest tests/ -v
```

- `tests/test_fingerprint.py` - fingerprint 유닛 테스트  
- `tests/test_dxf_parser.py` - DXF fixture 파싱 테스트  

## 주의사항

- **ODA File Converter**가 없으면 DWG 업로드 시 변환 단계를 건너뛸 수 없어 실패할 수 있습니다. 이 경우 DXF로 저장한 뒤 업로드하거나, `DEV_ALLOW_DXF_UPLOAD=true`로 DXF 업로드만 사용하세요.
- DWG 원본은 `UPLOAD_ROOT` 아래에 그대로 보관됩니다. DB는 운영/검색/비교/추출용 객체 레이어입니다.
