# 기능: 버전 비교 (Version Compare)

이전 버전(커밋)과 현재 버전 간 엔티티 변경 내역(추가/삭제/변경)을 조회·표시하는 기능입니다.

## 에셋 기능 등록

- **id**: `version-compare`
- **패널 id**: `featurePanel-version-compare`
- **등록 위치**: `app/static/workspace.html` 내 `window.ASSET_FEATURES` 배열
- **활성화 시**: `assetCompareBase`, `assetCompareTarget` 선택값으로 비교 뷰 로드 (`loadCompareView()`)

## 사용 API

- **GET** `/api/commits/{commit_id}/changeset`  
  - 부모 커밋 → 해당 커밋 사이의 changeset 조회 (from_commit_id, to_commit_id, items)
- **구현 위치**: `app/api/changesets.py` (코어 라우터, 이 기능 폴더 밖)

## 웹 UI

- **워크스페이스**: `#featurePanel-version-compare` 내 `#assetCompareBase`, `#assetCompareTarget` 셀렉트, 비교 보기 버튼
- **뷰 모드**: `viewMode === 'compare'`, `loadCompareView()` 로 이전/현재 버전 도면 겹쳐 보기

## 라우터

이 기능은 별도 `router.py`를 두지 않습니다. changesets API는 `app/main.py`에서 `app.api.changesets.router`로 이미 등록되어 있습니다. 이 폴더는 기능 설명·연동 지점만 정리한 문서입니다.

## 새 기능 추가 시

`app/plugins/version_compare/`와 이 FEATURE.md를 참고해, 버전 비교와 연동되는 새 기능(예: 필터, 내보내기)을 추가할 때 동일한 API·패널 id를 사용하면 됩니다.
