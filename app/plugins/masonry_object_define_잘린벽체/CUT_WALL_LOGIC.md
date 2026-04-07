# 잘린벽체(기둥으로 잘린 폴리곤) 처리 로직

기둥 등으로 인해 꼭지점이 6개 이상인 닫힌 폴리라인(잘린벽체)은 **골조 벽체와 동일한 방식**으로 처리합니다.

## 요약

1. **전체 루프(4~9 꼭지점)**: 골조와 동일하게 `frameDefDetectWallsFromClosedLoopData(loopData)`에 **전체 loopData**를 넘겨, `frameDefBuildWallFromClosedLoop`(엣지쌍 선택·평행 쌍·두께 검사)로 벽체 생성.
2. **잘린벽체(6+ 꼭지점)**: 위와 동일한 closed-join 로직으로 처리. 별도 longest-segment/bbox fallback 없음.
3. **기둥 트림**: 6+ 꼭지점 루프에서 생성된 벽에는 `__column_cut_wall = true`를 붙이고, `masonryDefTrimWallOverlaysByColumns`에서 해당 벽은 기둥 bbox로 자르지 않음(스킵).  
   → 잘린벽체 오버레이가 기둥 한 번 더 트림으로 전부 제거되는 것을 막기 위함.

## 메인 플러그인에서의 적용

- `app/static/plugins/masonry_object_define.js`:
  - `joinedClosedWalls`: **전체 loopData**를 `frameDefDetectWallsFromClosedLoopData(loopData)`에 전달(골조와 동일).
  - 루프별로 `loopData` 중 `points.length >= 6`인 루프와 entity_ids가 같은 벽을 찾아 `__column_cut_wall = true` 설정.
  - `masonryDefWallsFromClosedLoopFallback`: 4·5 꼭지점만 처리(6+는 `continue`로 스킵).
  - `masonryDefTrimWallOverlaysByColumns`: `wall.__column_cut_wall`이면 해당 벽의 quads는 기둥으로 트림하지 않음.
