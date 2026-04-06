/**
 * 잘린벽체(기둥으로 잘린 6+ 꼭지점 폴리곤) 처리 — 골조 벽체와 동일한 로직 참고.
 * 실제 동작은 app/static/plugins/masonry_object_define.js 에 통합되어 있음.
 *
 * 1) joinedClosedWalls: 골조와 동일하게 전체 loopData 전달.
 *    var joinedClosedWalls = frameDefDetectWallsFromClosedLoopData(loopData).filter(...);
 *    → frameDefBuildWallFromClosedLoop(엣지쌍·평행·두께·오버랩 등)로 비정형(6+) 포함 처리.
 *
 * 2) 6+ 꼭지점 루프에서 나온 벽에 __column_cut_wall 표시:
 *    for (loopData) { if (points.length >= 6) → joinedClosedWalls에서 entity_ids 일치하는 벽에 __column_cut_wall = true; }
 *
 * 3) fallback: 4·5 꼭지점만 처리 (6+는 continue로 스킵).
 *
 * 4) 기둥 트림 시 잘린벽체 제외:
 *    if (wall.__column_cut_wall) continue;
 */
