# 기능: 조적 정의 (ACI3 기반 벽체 자동분류)

`masonry-object-define` 기능은 ACI3(최종 표시색 기준) 객체를 대상으로 **벽체만** 자동 인지하고 분류합니다. 기둥은 없습니다.

## 에셋 기능 등록

- **id**: `masonry-object-define`
- **패널 id**: `featurePanel-masonry-object-define`
- **카테고리**: `2d`
- **활성화 버튼**: `조적 자동탐지`

## 현재 구현 위치

- UI 패널 마크업/기능 등록: `app/static/workspace.html`
- 조적정의 로직(JS): `app/static/plugins/masonry_object_define.js`
- 로드 방식: `workspace.html` IIFE 내부에서 `/static/plugins/masonry_object_define.js`를 읽어 평가 (골조 스크립트 로드 이후)
- 저장 속성 키:
  - `masonry_definition_label`
  - `masonry_group_id`
  - `masonry_group_no`
  - `masonry_group_role`
  - `masonry_kind` (항상 `wall`)
  - `masonry_class_key`
  - `masonry_wall_thickness_mm`
  - `masonry_wall_override_json`

## 골조 정의 대비 차이

- **색상**: ACI 2 → ACI **3**
- **대상**: 기둥+벽체 → **벽체만** (기둥 탐지/분류/선택 UI 없음)
- **속성 접두사**: `frame_*` → `masonry_*` (동일 도면에서 골조와 조적 동시 사용 가능)

## 자동분류 개요

1. `LINE/LWPOLYLINE/POLYLINE` 중 ACI3 대상 엔티티만 추출
2. 골조와 동일한 벽체 탐지 파이프라인 사용 (기둥 단계 생략, excludeSet 빈 객체)
3. 긴 평행 선분쌍의 수직거리로 벽체 두께 산정
4. 두께 군집 후 클래스화, 클래스 목록 선택 시 오버레이 표시
5. 선택/전체 분류를 masonry_* 속성으로 저장하고 적용된 묶음 목록 제공

## ACI4 / 해치

- ACI4 벽체는 **벽 중심이 해치 폴리곤 내부**인 경우만 인정한다.
- **해치 수집**: `masonryCollectHatchPolysWithBlocks(cid)`가 (1) 전역 `allEntities`의 HATCH(`frameDefCollectHatchPolys`)와 (2) **블록 내부 해치**를 합쳐 반환한다. 블록 해치는 `/api/commits/:id/blocks/inserts` 및 `/api/commits/:id/blocks/defs/:id/entities`로 블록별 HATCH를 가져와 인서트 기준 변환(위치·회전·스케일) 후 월드 좌표로 추가하므로, 블록 안의 해치도 ACI4 벽체 인식에 사용된다.
- **선택/적용**: "ACI4만 선택하기" 및 클래스 선택·속성 적용 시 **벽체 엔티티(LINE, LWPOLYLINE, POLYLINE)만** 선택·적용 대상이 되며, HATCH 등 비벽체는 제외된다.
