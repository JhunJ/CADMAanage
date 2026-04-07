# 여러 PC에서 작업할 때 (맞추기·실수 방지)

같은 GitHub 저장소([JhunJ/CADMAanage](https://github.com/JhunJ/CADMAanage))를 두 대 이상에서 쓸 때 기준입니다.

## 매번 (다른 PC에서 돌아온 뒤 / 작업 시작 전)

1. 프로젝트 루트에서:
   ```powershell
   .\scripts\sync_from_remote.ps1
   ```
2. 점검:
   ```powershell
   .\scripts\check_dev_env.ps1
   ```
3. 서버:
   ```powershell
   .\run_local.ps1
   ```
   DB 마이그레이션까지 한 번에 돌리려면:
   ```powershell
   .\scripts\sync_from_remote.ps1 -RunMigration
   ```

## 절대 하지 말 것

- **`.venv` 폴더를 USB·압축으로 다른 PC에 통째로 복사** — OS/경로가 달라 깨지기 쉽습니다. 각 PC에서 새로 만들거나 `.\scripts\recreate_venv.ps1` 후 `.\run_local.ps1`.
- **`.env`를 Git에 커밋** — 비밀번호·로컬 경로가 노출됩니다. `.env.example`만 저장소에 둡니다.
- **한 PC에서만 `push`하고 다른 PC에서는 `pull` 없이 계속 작업** — 코드가 갈라집니다. 작업 시작 전 `sync_from_remote.ps1` 또는 `git pull origin main`.

## DB와 업로드 파일

- PostgreSQL 데이터는 **PC마다 따로**입니다. 다른 PC와 DB 내용을 맞추려면 덤프/복원 등 별도 작업이 필요합니다.
- `data/uploads` 등 큰 파일은 보통 Git에 포함하지 않습니다. 도면이 필요하면 공유 폴더 등으로 따로 맞춥니다.

## `DATABASE_URL` 드라이버

이 프로젝트는 동기 SQLAlchemy용 **`postgresql+psycopg://`** (psycopg v3)을 씁니다. 예전에 `postgresql+psycopg2://`만 쓰던 PC는 `.env`를 고치세요. `check_dev_env.ps1`이 틀린 경우를 알려 줍니다.

## 브랜치

일상 작업은 **`main`에서 pull/push**로 맞추면 됩니다. 동시에 같은 파일을 많이 고치면 충돌이 날 수 있으니, 그때는 기능별 브랜치를 쓰거나 작업 단위를 나눕니다.

## Cursor(다른 PC)에 시킬 때

에이전트에게 “프로젝트 루트에서 `.\scripts\sync_from_remote.ps1`, `.\scripts\check_dev_env.ps1` 실행 후 문제 있으면 보고”라고 하면, 수동 명령 나열 없이 같은 절차를 밟게 할 수 있습니다.
