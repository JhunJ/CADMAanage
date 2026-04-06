# 기능: 골조 정의 (ACI2 기반 기둥/벽체 자동분류)

`frame-object-define` 기능은 ACI2(최종 표시색 기준) 객체를 대상으로 기둥과 벽체를 자동 인지하고 분류합니다.

## 에셋 기능 등록

- **id**: `frame-object-define`
- **패널 id**: `featurePanel-frame-object-define`
- **카테고리**: `2d`
- **활성화 버튼**: `골조 자동탐지`

## 현재 구현 위치

- UI 패널 마크업/기능 등록: `app/static/workspace.html`
- 골조정의 로직(JS): `app/static/plugins/frame_object_define.js`
- 로드 방식: `workspace.html` IIFE 내부에서 `/static/plugins/frame_object_define.js`를 읽어 평가
- 저장 속성 키:
  - `frame_definition_label`
  - `frame_group_id`
  - `frame_group_no`
  - `frame_group_role`
  - `frame_kind` (`column` 또는 `wall`)
  - `frame_class_key`
  - `frame_column_orientation` (`horizontal` 또는 `vertical`)
  - `frame_wall_thickness_mm`

## 자동분류 개요

1. `LINE/LWPOLYLINE/POLYLINE` 중 ACI2 대상 엔티티만 추출
2. 닫힌 사각 폴리라인 + 4개 선분 루프에서 기둥 후보 추출
3. 기둥은 XY축 기준으로 가로/세로 강제 분류
4. 긴 평행 선분쌍의 수직거리로 벽체 두께 산정
5. 두께를 adaptive tolerance(`max(12mm, median*0.08)`)로 군집 후 10mm 단위 클래스화
6. 클래스 목록 선택 시 오버레이(색상+라벨) 표시 및 선택 연동
7. 선택/전체 분류를 속성으로 저장하고 적용된 묶음 목록 제공
