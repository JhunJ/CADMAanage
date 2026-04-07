# CAD Manage - Rhino 8 연동 스크립트

**로컬 배포용**: Rhino 사용자에게 **서버 소스 없이** 전달할 때는 **`clients/rhino/`** 폴더를 사용하세요. 해당 폴더만 압축해 배포하면 되며, `clients/rhino/README.md`에 설치·서버 주소 설정 방법이 정리되어 있습니다.

---

라이노 8에서 CAD Manage DB의 버전을 불러와 편집하고, 저장 시 DB에 새 버전으로 올리는 데 사용합니다.

## 흐름: 라이노 열기 → 가져오기/저장

**라이노 열기**는 방법이 하나입니다. **웹**에서 「라이노 열기」 버튼을 누르거나, 웹에서 받은 **「라이노 열기.bat」**을 더블클릭하면 됩니다. (최초 1회만 **`설치_및_라이노_실행.bat`**으로 프로토콜 설치.)

라이노가 열리면 **CadManage 창**(Eto 대화상자)이 뜹니다. 서버 주소 입력, 프로젝트 목록 불러오기, 프로젝트·버전 선택 후 **DB에서 가져오기**로 현재 문서에 객체 불러오기, **저장**으로 DB에 새 버전 저장이 가능합니다.

**최초 1회**  
`scripts\rhino\` 폴더에서 **`설치_및_라이노_실행.bat`** 을 더블클릭 → 프로토콜 설치 + 라이노 실행. 이후에는 웹 버튼이나 받은 **라이노 열기.bat**으로 같은 방식으로 라이노만 띄우면 됩니다.

**수동 실행**  
라이노를 먼저 연 뒤 RunScript로 `cadmanage_rhino.py` 실행해도 됩니다. CadManage 창(서버 주소, 프로젝트·버전 선택, DB에서 가져오기/저장)이 뜹니다.

**툴바 버튼으로 실행**  
원할 때 한 번에 CadManage 창을 열려면, 라이노 **도구 모음 사용자 지정**에서 버튼을 추가하세요.  
1. 메뉴 **도구** → **도구 모음** → **사용자 지정** (또는 툴바 우클릭 → 사용자 지정).  
2. **새로 만들기** 또는 기존 툴바에 **새 단추 추가**.  
3. 단추의 **명령**에 아래를 그대로 입력합니다 (경로에 공백이 있으면 괄호로 감쌈).  
   `-_RunPythonScript (%LOCALAPPDATA%\CadManageRhino\cadmanage_rhino.py)`  
4. 확인 후, 해당 버튼을 클릭하면 CadManage 창만 열립니다. (설치 후 스크립트 경로는 `%LOCALAPPDATA%\CadManageRhino\` 입니다.)

## 연동 정보 복사 (선택)

웹에서 프로젝트·버전 선택 후 **「연동 정보 복사」** → 라이노에서 RunScript로 스크립트 실행 → **[1] 가져오기** 선택 후 프롬프트에 JSON 붙여넣기. 편집 후 **[2] 저장**.

## 요구 사항

- **Rhino 8** (Code-Driven File I/O 사용)
- CAD Manage 서버가 접근 가능한 주소에 떠 있어야 함 (로컬: `http://127.0.0.1:8000` 등)
- 서버 설정에서 **DXF 업로드 허용** 필요 (`DEV_ALLOW_DXF_UPLOAD=true`, 기본값)

**로컬 vs 서버**: 개발 시에는 웹/API를 로컬(localhost)에서 띄우고 라이노도 같은 PC에서 실행하면 됩니다. 배포 시에는 웹은 서버에 두고, 사용자 PC에서 라이노만 실행합니다. 「라이노 열기」를 누르면 api_base만 전달되며, 라이노에서 서버 API로 프로젝트/버전을 선택해 데이터를 받습니다.

## 연동 정보(JSON) 형식

```json
{"api_base":"http://127.0.0.1:8000","project_id":1,"commit_id":14}
```

- `api_base`: CAD Manage API 루트 (웹 페이지 주소와 동일)
- `project_id`: 프로젝트 ID
- `commit_id`: 불러올 버전(커밋) ID

## 코드 수정 후

스크립트(`cadmanage_rhino.py`, `launcher.ps1` 등)를 수정한 뒤에는 **한 번 더** `설치_및_라이노_실행.bat` 또는 `install_cadmanage_protocol.ps1`을 실행하세요. Rhino가 실행하는 파일은 `%LOCALAPPDATA%\CadManageRhino\`에 복사된 것이므로, 최신 버전으로 덮어써야 합니다. 라이노가 뜨면 [가져오기]로 프로젝트/버전 선택 후 DB 엔티티(geom WKT)를 현재 문서에 curve/point/text 객체로 추가합니다. 연동 오류 시 `%TEMP%\cadmanage_rhino_debug.txt` 로그를 확인하면 원인 파악에 도움이 됩니다.

## 스크립트 설치(선택)

Rhino가 스크립트를 찾기 쉬우려면:

- Windows: `%APPDATA%\McNeel\Rhinoceros\8.0\Plug-ins\PythonPlugIns\` 아래에 이 폴더를 복사하거나, RunScript에서 이 프로젝트의 `scripts/rhino/cadmanage_rhino.py` 경로를 지정해 실행할 수 있습니다.
- RunScript 시 **파일 선택**으로 이 저장소의 `scripts/rhino/cadmanage_rhino.py`를 지정해도 됩니다.
