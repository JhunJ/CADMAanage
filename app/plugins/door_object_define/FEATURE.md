# 기능: 문 객체정의 (ARC 기반 개구부 자동분류)

`door-object-define` 기능은 ARC를 기준으로 개구부를 자동탐지하고, 폭(mm) 기준으로 문/양개문을 분류합니다.

## 에셋 기능 등록

- **id**: `door-object-define`
- **패널 id**: `featurePanel-door-object-define`
- **카테고리**: `2d`
- **활성화 버튼**: `ARC 자동탐지`

## 현재 구현 위치

- UI 패널 마크업/기능 등록: `app/static/workspace.html`
- 문 객체정의 로직(JS): `app/static/plugins/door_object_define.js`
- 로드 방식: `workspace.html` IIFE 내부에서 `/static/plugins/door_object_define.js`를 읽어 평가
- 저장 속성 키:
  - `door_definition_label`
  - `door_group_id`
  - `door_group_no`
  - `door_group_role`
  - `door_leaf_type` (`single` 또는 `double`)
  - `door_defined_width_mm` (10mm 단위 정의 폭)

## 자동분류 개요

1. ARC 후보를 블록/개별 엔티티에서 추출
2. ARC 조합(단일/쌍)을 개구부 단위로 그룹화
3. ARC 반지름 기반 폭 계산 + 엔드포인트 연결성으로 문/양개문 판별
4. 폭 클래스별 목록 표시
5. `문 전체 선택`, `양개문 전체 선택` 지원
6. 클래스별 `-10/+10` 폭 보정 후 속성 적용 지원
7. 가로 슬라이더(`탐지 민감도`)로 ARC 탐지 강도 조정 지원

## 유지관리 기준(권장)

현재 핵심 로직은 별도 JS 파일로 분리되어 있으며, 추가 확장 시 아래 단위 분리를 권장합니다.

1. `door_object_define_ui.js` (패널 렌더/이벤트)
2. `door_object_define_detect.js` (ARC 탐지/분류)
3. `door_object_define_apply.js` (속성 저장/동기화)

기능 동작 계약(id/패널 id/속성 키)은 위 값을 고정해 호환성을 유지합니다.
