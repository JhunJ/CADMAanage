# 플러그인 폴더

이 폴더에 **기능별 폴더만 넣으면** 됩니다. 새 기능은 외부에서 개발 후 이곳 한 곳에 넣으면 작동합니다.

## 규칙

- 각 기능: `app/plugins/<기능명>/` 폴더 하나
- 폴더 안에:
  - **FEATURE.md** (필수): 기능 설명, 사용 API, 웹 연동 방법. AI가 이 폴더만 읽어 연동·수정 가능
  - **router.py** (선택): API 라우트가 있으면 `router = APIRouter(...)` 정의 → 로더가 자동 등록
- `_` 로 시작하는 폴더는 스킵

## 예시

```
app/plugins/
  version_compare/   FEATURE.md (문서만)
  rhino/             FEATURE.md (문서만)
  example/           FEATURE.md + router.py
  내기능/            FEATURE.md + router.py  ← 새로 넣으면 자동 로드
```

## 새 기능 추가

1. `app/plugins/내기능/` 폴더 생성
2. `FEATURE.md` 작성 (기능 설명, API, ASSET_FEATURES id 등)
3. API가 필요하면 `router.py`에 `router = APIRouter(...)` 정의
4. 앱 재시작 시 로더가 `router.py`를 찾아 등록

AI는 해당 폴더만 읽어서 기존 체계(API, 워크스페이스, ASSET_FEATURES)와 맞춰 연동·수정할 수 있습니다.
