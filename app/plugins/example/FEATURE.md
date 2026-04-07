# 예시 플러그인 (Example)

플러그인 추가 방법을 보여주는 템플릿입니다.

- `router.py` — FastAPI 라우터 정의, `router` 속성 필수
- `FEATURE.md` — 기능 설명, AI가 연동·수정 시 참고

이 폴더를 복사해 새 기능 폴더를 만들면 됩니다. `app/plugins/` 아래에 넣으면 로더가 `router.py`를 자동 등록합니다.
