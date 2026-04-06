# CadManage Rhino 클라이언트 (로컬 전용)

캐드 매니저 **서버**는 별도로 배포하고, 이 폴더만(또는 여기서 만든 실행 파일만) 로컬 PC에 두면 Rhino에서 **DB(API) 통신만**으로 도면을 가져오고 저장할 수 있습니다. 서버 소스(`app/`)는 포함하지 않습니다.

## 포함 파일

- `cadmanage_rhino.py` — Rhino 8 Python 연동 스크립트 (가져오기/저장/커밋 설정)
- `launcher.ps1` — `cadmanage://` URL 처리 (웹 "라이노 열기" 클릭 시)
- `launcher_wrapper.bat` — 프로토콜 실행 래퍼
- `install_cadmanage_protocol.ps1` — 프로토콜 등록 + 스크립트를 `%LOCALAPPDATA%\CadManageRhino`에 복사
- `설치_및_라이노_실행.bat` — 최초 1회 설치 후 Rhino 실행
- `config.example.json` — 서버 주소 예시 (아래 참고)

## 설치 및 실행

1. **이 폴더 전체**를 사용자에게 전달(압축 배포 가능).
2. **최초 1회**: `설치_및_라이노_실행.bat` 더블클릭  
   - 프로토콜 등록 + 스크립트가 `%LOCALAPPDATA%\CadManageRhino\`에 복사됨  
   - Rhino 8이 실행되며 연동 스크립트가 한 번 실행됨
3. **웹에서 사용**: 캐드 매니저 웹에서 프로젝트·버전 선택 후 "라이노에서 열기" 클릭 → 브라우저에서 `cadmanage://` 허용 시 Rhino가 뜨고 해당 버전이 로드됨.
4. **Rhino에서 직접**: Rhino 메뉴에서 스크립트 실행(또는 `_-RunPythonScript`로 `%LOCALAPPDATA%\CadManageRhino\cadmanage_rhino.py` 실행) → CadManage 창에서 프로젝트/버전 선택 후 "DB에서 가져오기" 또는 "저장".

## 서버 주소(api_base) 설정

- **웹에서 "라이노 열기"로 열 때**: URL에 `api_base`가 포함되므로 별도 설정 없이 해당 서버로 연결됩니다.
- **Rhino에서만 사용할 때(가져오기/저장 창)**  
  - CadManage 창의 "서버 주소" 입력란에 직접 입력하거나,  
  - **config 파일**: `config.example.json`을 복사해 `config.json`으로 이름을 바꾼 뒤 `api_base`를 수정합니다.  
    - 설치 후 스크립트가 있는 위치: `%LOCALAPPDATA%\CadManageRhino\`  
    - 해당 폴더에 `config.json`을 두고 `{"api_base": "https://your-server.example.com"}` 형태로 설정하면, 스크립트가 기본 서버 주소로 읽을 수 있습니다(스크립트에서 config 로드 지원 시).
  - **환경 변수**: `CADMANAGE_API_BASE`를 설정해 기본 서버 주소로 사용할 수 있도록 할 수 있습니다(스크립트에서 지원 시).

현재 스크립트는 CadManage 창의 "서버 주소" 입력란 기본값으로 `http://127.0.0.1:8000`을 사용합니다. 다른 서버를 쓰려면 창에서 주소를 입력하면 됩니다.

## 배포 요약

- **서버**: 캐드 매니저 앱(`app/`)은 서버에 별도 배포.
- **로컬**: 이 폴더(`clients/rhino/`)만 압축해 Rhino 사용자에게 전달하거나, 여기서 빌드한 실행 파일만 전달하면 됩니다. 사용자는 서버 URL만 설정하고 DB(API) 통신만 하게 됩니다.
