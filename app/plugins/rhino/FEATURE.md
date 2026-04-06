# 기능: 라이노 연동 (Rhino)

워크스페이스에서 "라이노에서 열기"로 Rhino를 띄우고, Rhino에서 DB 버전을 가져오기/저장하는 연동 기능입니다.

## 에셋 기능 등록

- **id**: `rhino`
- **패널 id**: `featurePanel-rhino`
- **등록 위치**: `app/static/workspace.html` 내 `window.ASSET_FEATURES` 배열
- **활성화 시**: `cadmanage://` 프로토콜으로 현재 프로젝트/버전 정보를 전달해 Rhino 클라이언트 실행

## 클라이언트 위치

- **배포용(로컬 전용)**: `clients/rhino/` — 실행 파일 또는 이 폴더만 배포해 Rhino 사용자가 서버와 DB(API) 통신만 하도록 함
- **개발/레거시**: `scripts/rhino/` (향후 `clients/rhino/`로 통합 권장)

## 사용 API (서버 계약)

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/projects` | 프로젝트 목록 |
| GET | `/api/projects/{id}/commits` | 커밋 목록 |
| GET | `/api/commits/{id}` | 커밋 상세 |
| GET | `/api/commits/{id}/entities` | 엔티티 목록 (DB → Rhino 로드) |
| GET | `/api/commits/{id}/export/dxf` | DXF 내보내기 (선택) |
| POST | `/api/projects/{id}/uploads` | DXF 업로드(커밋 생성) |

## 업로드(커밋) Form 파라미터

`POST /api/projects/{project_id}/uploads` 시 다음 Form 필드를 보낼 수 있습니다.

- **필수**: `file` (업로드 파일)
- **선택**: `parent_commit_id`, `version_label`, `assignee_name`, `assignee_department`, `change_notes`, `class_pre`, `class_major`, `class_mid`, `class_minor`, `class_work_type`, `settings` (JSON 문자열)

Rhino 클라이언트는 저장 시 위 메타데이터를 폼에 넣어 전송합니다.

## 연동 흐름

1. 웹: "라이노 열기" 클릭 → `cadmanage://open?project_id=...&commit_id=...&api_base=...`
2. 로컬: 프로토콜 핸들러 → launcher → Rhino 실행 + 스크립트 로드
3. 스크립트: `launch.json`(또는 URL 파라미터)에서 project_id, commit_id, api_base 읽어 `/api/commits/{id}/entities` 호출 후 도면 로드
4. 저장: Rhino에서 DXF 내보내기 → `POST /api/projects/{id}/uploads` (커밋 설정 필드 포함)

## 새 기능 추가 시

이 폴더(`app/plugins/rhino/`)만 읽고 위 API·폴더 규칙을 따르면 기존 체계와 맞출 수 있습니다. 서버 측 전용 라우트가 필요하면 `router.py`를 추가하고 `_loader`가 자동 등록합니다.
