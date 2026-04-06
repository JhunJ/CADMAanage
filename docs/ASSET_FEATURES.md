# 에셋 기능 모듈 추가 가이드

워크스페이스 왼쪽 **에셋** 탭의 **기능** 리스트에 새 기능을 등록하고, 선택 시 우측에서 패널과 **활성화** 버튼으로 실행되도록 하는 방법입니다.

## 구조 요약

- **왼쪽**: 기능 리스트(`#assetFeatureList`) — `window.ASSET_FEATURES` 배열에서 자동 렌더링
- **우측**: 기능 선택 시 `#featureActivationPanel` 표시, 내부에 기능별 패널 + **활성화** 버튼
- **동작**: 리스트에서 항목 선택 → 우측에 해당 패널·활성화 버튼 표시 → **활성화** 클릭 시 `onActivate()` 실행

## 기능 디스크립터 (ASSET_FEATURES)

`app/static/workspace.html` 내 스크립트에서 `window.ASSET_FEATURES` 배열에 객체를 추가합니다.

### 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `id` | O | 고유 식별자 (예: `'version-compare'`, `'rhino'`). 리스트·패널 매칭에 사용 |
| `label` | O | 리스트에 표시할 이름 |
| `panelHtmlId` | O | 우측에 보여줄 패널 요소 id (예: `'featurePanel-version-compare'`) |
| `activateLabel` | - | 활성화 버튼 문구 (기본: `'활성화'`) |
| `onActivate` | O | 활성화 버튼 클릭 시 실행할 함수 |

### 패널 HTML

- 우측 `#featureActivationContent` 안에 `<div id="featurePanel-{id}" class="feature-panel">` 형태로 패널을 두면, 해당 기능 선택 시 이 패널만 `active` 클래스로 표시됩니다.
- 새 기능 추가 시:
  1. `#featureActivationContent` 안에 `<div id="featurePanel-새id" class="feature-panel">...</div>` 블록 추가
  2. `ASSET_FEATURES`에 `{ id: '새id', label: '...', panelHtmlId: 'featurePanel-새id', onActivate: function() { ... } }` 추가

## 예제 1: 버전 비교

```javascript
{
  id: 'version-compare',
  label: '버전 비교',
  panelHtmlId: 'featurePanel-version-compare',
  activateLabel: '비교 보기',
  onActivate: function() {
    var baseId = document.getElementById('assetCompareBase').value;
    var targetId = document.getElementById('assetCompareTarget').value;
    if (!baseId || !targetId || baseId === targetId) {
      viewInfoEl.textContent = '이전 버전과 현재 버전을 각각 선택하세요.';
      return;
    }
    document.getElementById('compareBase').value = baseId;
    document.getElementById('compareTarget').value = targetId;
    viewMode = 'compare';
    loadCompareView();
  }
}
```

- 패널에는 `#assetCompareBase`, `#assetCompareTarget` 셀렉트가 있으며, `loadCompareCommits()`는 프로젝트 변경 시·기능 선택 시 호출되어 옵션을 채웁니다.

## 예제 2: 라이노 연동

```javascript
{
  id: 'rhino',
  label: '라이노 연동',
  panelHtmlId: 'featurePanel-rhino',
  activateLabel: '라이노에서 열기',
  onActivate: function() {
    var pid = viewProjectSelect ? viewProjectSelect.value : '';
    var cid = viewCommitSelect ? viewCommitSelect.value : '';
    if (!pid || !cid) {
      showMsg('msg', '좌측 에셋에서 프로젝트와 버전을 선택하세요.', 'error');
      return;
    }
    var url = 'cadmanage://open?project_id=' + pid + '&commit_id=' + cid + '&api_base=' + encodeURIComponent(window.location.origin);
    window.location.href = url;
  }
}
```

- 좌측 에셋에서 선택한 프로젝트·버전이 라이노로 열립니다. 패널에는 실행파일 받기·연동 정보 복사·DXF 내려받기 버튼이 있으며, 모두 `viewProjectSelect`/`viewCommitSelect` 값을 사용합니다.

## 개발 페이지에서 추가한 플러그인 (CadManagePlugin)

개발 페이지(/dev)에서 추가한 플러그인의 **활성화 코드**는 전역 스코프에서 실행되므로, 워크스페이스 내부의 `showMsg`, `viewInfoEl` 등에 직접 접근할 수 없습니다. 대신 **전역 객체 `CadManagePlugin`** 을 사용하세요.

- **메시지 표시**: `CadManagePlugin.showMsg('msg', '메시지', 'success');` — 두 번째 인자에 문구, 세 번째에 `'success'` / `'error'` / `'info'` 등
- **뷰어 안내 문구**: `CadManagePlugin.setViewInfo('텍스트');` — 에셋 탭 하단 뷰어 정보 영역에 표시

활성화 코드에서 예외가 나면 자동으로 뷰어 안내 영역에 오류 메시지가 표시되고, 콘솔에 로그가 남습니다.

## 패널 HTML 시 주의사항

- 패널 HTML 안에 넣는 입력·버튼 등에는 **페이지에 이미 있는 id와 겹치지 않는 고유한 id**를 사용하세요. (예: `my-feature-input1`, `my-feature-btn`) 다른 기능의 `assetCompareBase` 등과 중복되면 `getElementById` 결과가 잘못될 수 있습니다.

## 속성 활용 팁

- **프로젝트/버전**: `viewProjectSelect`, `viewCommitSelect`로 현재 에셋 탭에서 선택된 프로젝트·버전 사용 가능
- **속성 키**: `commitCommonAttrKeys`, `commitIndividualAttrKeys` 또는 `/api/projects/{id}/attribute_keys` API로 공통·개별 속성 키 조회
- **엔티티/커밋**: `/api/commits/{id}/entities`, `/api/projects/{id}/commits` 등 기존 API 활용

## 새 기능 추가 체크리스트

1. `#featureActivationContent` 안에 `<div id="featurePanel-{id}" class="feature-panel">` 및 필요한 폼/버튼 추가
2. `window.ASSET_FEATURES`에 `{ id, label, panelHtmlId, activateLabel?, onActivate }` 푸시
3. 기능 선택 시 패널에서 사용하는 셀렉트를 채우려면 `initAssetFeatureList()` 내 해당 기능 클릭 시 분기에서 필요한 로드 함수 호출 (예: `loadCompareCommits()`)
4. `onActivate`에서 폼 검증 후 API 호출·페이지 이동 등 실행

이 레지스트리 방식으로 기능을 추가하면 왼쪽 리스트와 우측 활성화 흐름에 자동으로 연결됩니다.
