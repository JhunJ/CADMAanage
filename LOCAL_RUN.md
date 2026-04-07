# 로컬 실행 가이드 (Windows, 도커 없이)

가능한 한 **두 단계**로 끝나도록 자동화해 두었습니다.

---

## 0. 다른 PC에서 이 폴더를 통째로 옮긴 경우

- **`.venv`를 같이 복사했다면 삭제**하세요. 다른 PC에서 만든 가상환경은 이 PC에서 깨지기 쉽습니다. 삭제 후 프로젝트 루트에서 `.\scripts\recreate_venv.ps1` 또는 바로 `.\run_local.ps1`(venv 없으면 자동 생성).
- **`.env`**는 상대 경로(`./data/uploads`)라 보통 그대로 두면 됩니다. DB 비밀번호·호스트가 이 PC와 다르면 `DATABASE_URL`만 수정하세요.
- **PostgreSQL을 이 PC에 처음 맞출 때**는 **`setup_db.bat`**(더블클릭) 또는 `.\scripts\init_db.ps1`로 `caduser` / `cadmanage` / PostGIS를 맞춥니다. 스크립트가 **`caduser` 비밀번호를 항상 `cadpass`로 동기화**하므로, 예전에 다른 비밀번호로 만들었어도 한 번 다시 실행하면 `.env`와 맞습니다.
- **Docker로 DB만 쓸 때**는 [Docker Desktop](https://www.docker.com/products/docker-desktop/)을 **실행한 뒤** `docker compose up -d postgis` 하세요. 데스크톱이 꺼져 있으면 `open //./pipe/dockerDesktopLinuxEngine` 오류가 납니다.
- **Git으로 여러 PC를 쓸 때**는 작업 시작 전 `.\scripts\sync_from_remote.ps1` 와 `.\scripts\check_dev_env.ps1` 를 권장합니다. 요약은 [docs/MULTI_PC_WORKFLOW.md](docs/MULTI_PC_WORKFLOW.md).

---

## 1. 사전 준비 (최초 1회)

- **Python 3.11 이상**  
  ```powershell
  python --version
  ```
- **PostgreSQL + PostGIS**  
  - [PostgreSQL 다운로드](https://www.postgresql.org/download/windows/) 에서 설치 (예: 16)
  - 설치 후 **Stack Builder** 또는 [PostGIS for Windows](https://postgis.net/windows_downloads/) 로 PostGIS 확장 설치

---

## 2. DB 생성 (최초 1회)

PostgreSQL 설치가 끝났다면, **프로젝트 폴더**에서:

```powershell
cd "<CADManage 프로젝트 폴더 경로>"
.\scripts\init_db.ps1
```

또는 프로젝트 루트에서 **`setup_db.bat`** 더블클릭(동일 작업).

- `psql`을 찾을 수 없다고 나오면: PostgreSQL 설치 경로의 `bin` 폴더를 PATH에 추가 (예: `C:\Program Files\PostgreSQL\16\bin`)
- 비밀번호를 묻면: PostgreSQL 설치 시 정한 **postgres** 사용자 비밀번호 입력

이 스크립트가 **caduser** / **cadmanage** DB / **PostGIS 확장**을 만들어 줍니다.

---

## 3. 앱 실행 (매번)

같은 프로젝트 폴더에서:

```powershell
.\run_local.ps1
```

이 한 번이면:

- 가상환경이 없으면 생성
- `.env`가 없으면 `.env.example` 복사
- 패키지 설치
- DB 마이그레이션 (`alembic upgrade head`)
- API 서버 기동 (`http://localhost:8000`)

브라우저에서 **http://localhost:8000/docs** 로 API 문서를 볼 수 있습니다.

---

## 4. "스크립트를 실행할 수 없습니다" / 실행 정책 오류

PowerShell에서 `.\run_local.ps1` 또는 `.\scripts\init_db.ps1` 실행이 차단되면, **같은 PowerShell 창**에서 아래를 **한 번만** 실행:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

- "변경할지" 묻면 **Y** 입력 후 Enter.
- 관리자 권한 없이, 현재 사용자에게만 적용됩니다.

이후 다시 `.\scripts\init_db.ps1` 또는 `.\run_local.ps1` 실행.

---

## 5. DB 비밀번호/포트를 바꿨을 때

프로젝트 루트의 **`.env`** 파일을 열어서 수정합니다.

```ini
DATABASE_URL=postgresql+psycopg://caduser:원하는비밀번호@127.0.0.1:5432/cadmanage
```

`run_local.ps1`은 `.env`를 읽어서 사용합니다.

---

## 5-2. DWG 변환 (ODA File Converter, 선택)

DWG 파일을 업로드하면 서버에서 DXF로 자동 변환합니다. 변환이 되려면 **ODA File Converter**가 필요합니다.

- **설치**: [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) 에서 다운로드 후 설치 (비상업용 무료).
- **기본 경로**: `C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe` 또는 버전 폴더(예: `C:\Program Files\ODA\ODAFileConverter 26.12.0\ODAFileConverter.exe`)에 두면 **별도 설정 없이** 자동으로 찾습니다.
- **다른 경로에 설치한 경우**: `.env` 에 다음처럼 설정합니다.
  ```ini
  ODA_FC_PATH=C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe
  ```
  (경로에 공백이 있어도 됩니다. 따옴표는 넣지 않아도 됩니다.)

ODA가 없어도 **DXF 파일**은 그대로 업로드·파싱·뷰어까지 사용할 수 있습니다.

---

## 6. API 테스트 (새 터미널)

서버가 떠 있는 상태에서 **다른 터미널**을 열고:

```powershell
cd "<CADManage 프로젝트 폴더 경로>"
.\.venv\Scripts\Activate.ps1
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
Invoke-RestMethod -Uri "http://localhost:8000/api/users" -Method Post -ContentType "application/json" -Body '{"name":"테스트","email":"test@example.com"}'
Invoke-RestMethod -Uri "http://localhost:8000/api/projects" -Method Post -ContentType "application/json" -Body '{"name":"테스트프로젝트","code":"PRJ1","created_by":1}'
```

**샘플 DXF로 업로드 테스트:**

```powershell
python scripts/make_sample_dxf.py
$f = @{ file = Get-Item ".\sample.dxf"; created_by = 1; version_label = "v1" }
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/1/uploads" -Method Post -Form $f
```

---

## 요약 (복사용)

```powershell
# 최초 1회: PostgreSQL+PostGIS 설치 후 (프로젝트 루트로 이동)
cd "<CADManage 프로젝트 폴더 경로>"
.\scripts\init_db.ps1

# 매번 실행
.\run_local.ps1
```

---

## 문제 해결

| 현상 | 조치 |
|------|------|
| `마이그레이션 실패` | PostgreSQL 서비스 실행 여부 확인. `.env`의 `DATABASE_URL`가 실제 DB/비밀번호와 같은지 확인. |
| `psql을 찾을 수 없습니다` | PostgreSQL `bin` 폴더를 PATH에 추가. |
| `PostGIS 확장 실패` | PostGIS가 해당 PostgreSQL 버전에 설치되어 있는지 확인. |
| `run_local.ps1 실행 안 됨` | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` 실행 후 재시도. |
| `DWG 업로드 후 변환 실패` | ODA File Converter 설치 여부 확인. `.env`에 `ODA_FC_PATH`가 있으면 설치 경로와 일치하는지 확인. (경로에 따옴표 제거) |

---

## (참고) Docker로 실행할 때

PostgreSQL을 Docker로 쓰려면:

```powershell
docker compose up -d postgis
# .env 의 DATABASE_URL 는 그대로 두고
.\run_local.ps1
```

자세한 내용은 [README.md](README.md) 참고.
