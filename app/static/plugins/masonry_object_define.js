/* masonry-object-define: ACI3 기반 조적(벽체만) 자동분류. 골조(frame) 모듈에 의존. */
var MASONRY_DEF_ATTR_KEYS = [
  'masonry_definition_label',
  'masonry_group_id',
  'masonry_group_no',
  'masonry_group_role',
  'masonry_kind',
  'masonry_class_key',
  'masonry_wall_thickness_mm',
  'masonry_wall_override_json'
];
var MASONRY_DEF_ACI = 3;
var MASONRY_DEF_ACI4 = 4;
var MASONRY_DEF_WALL_OVERRIDE_ATTR = 'masonry_wall_override_json';
/** 조적 전면 단순화: 작은 벽 포함 위해 완화 (기존 2000) */
var MASONRY_DEF_MIN_WALL_PERIMETER_MM = 1200;
/** 해치를 감싸는 ACI4 닫힌 라인까지 포함하려면 둘레 기준을 낮춤 (기존 800) */
var MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_MM = 500;
/** ACI4 닫힌 폴리곤 안에 해치가 있으면 이 둘레 이상이면 디스크립터 포함 (작은 벽도 읽기) */
var MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_WITH_HATCH_MM = 300;
/** 단일 4·5꼭지점(닫힌 사각형) ACI3: 둘레 완화 (기존 1500) */
var MASONRY_DEF_MIN_WALL_PERIMETER_SINGLE_RECT_MM = 1000;
/** 디버그 포함 판정: 디스크립터 bbox 확장 거리(mm). 폴리곤 밖이어도 이 거리 이내면 '포함'으로 봄 */
var MASONRY_DEF_BBOX_CONTAIN_MM = 2000;
/** 조적 벽체 최소 두께(mm). 50mm 이하는 벽체가 아니므로 제외 */
var MASONRY_DEF_MIN_WALL_THICKNESS_MM = 50;
/** 조적 전용: 선을 이어서 닫힌 루프로 볼 때 끝점 스냅 거리(mm). 이 값보다 멀리 떨어진 선은 한 루프로 연결하지 않음 (끊긴 벽이 이어지지 않도록) */
var MASONRY_DEF_LOOP_SNAP_MM = 5;

/** 폴리곤이 직사각형에 가까운지 형상만으로 판단 (꼭지 4~5개, bbox 대비 면적 비율) */
function masonryDefIsApproximatelyRectangular(points) {
  if (!Array.isArray(points) || points.length < 4 || points.length > 5) return false;
  var n = points.length;
  var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (var i = 0; i < n; i++) {
    var x = Number(points[i].x) || 0, y = Number(points[i].y) || 0;
    if (x < minX) minX = x; if (y < minY) minY = y;
    if (x > maxX) maxX = x; if (y > maxY) maxY = y;
  }
  var bboxArea = (maxX - minX) * (maxY - minY);
  if (bboxArea < 1e-6) return false;
  var area = 0;
  for (var j = 0; j < n; j++) {
    var a = points[j], b = points[(j + 1) % n];
    area += (Number(a.x) || 0) * (Number(b.y) || 0) - (Number(b.x) || 0) * (Number(a.y) || 0);
  }
  area = Math.abs(area) * 0.5;
  return area >= bboxArea * 0.75;
}

/** bbox를 장변=길이(seg_a·seg_b 방향), 단변=폭(두께)으로 벽 세그먼트 생성. 단일 폴리라인 형상용 */
function masonryDefBboxToWallSegments(minX, minY, maxX, maxY) {
  var w = maxX - minX, h = maxY - minY;
  if (!(w > 1e-6 && h > 1e-6)) return null;
  var seg_a, seg_b;
  if (w >= h) {
    seg_a = { p1: { x: minX, y: minY }, p2: { x: maxX, y: minY } };
    seg_b = { p1: { x: minX, y: maxY }, p2: { x: maxX, y: maxY } };
  } else {
    seg_a = { p1: { x: minX, y: minY }, p2: { x: minX, y: maxY } };
    seg_b = { p1: { x: maxX, y: minY }, p2: { x: maxX, y: maxY } };
  }
  return { seg_a: seg_a, seg_b: seg_b };
}

/**
 * 기둥으로 잘린 폴리곤(6+꼭지점)에서 가장 긴 직선 세그먼트 방향으로 직사각형(벽체) 생성.
 * 장변=폴리곤을 그 방향으로 투영한 범위, 단변=수직 범위(두께). 기둥과 겹침을 줄여 quad가 잘리지 않게 함.
 * @param {Array<{x:number,y:number}>} pts 폐곡선 꼭지점 (중복 끝점 제외)
 * @returns {{ seg_a: {p1,p2}, seg_b: {p1,p2} } | null}
 */
function masonryDefLongestSegmentRectFromPolygon(pts) {
  if (!Array.isArray(pts) || pts.length < 4) return null;
  var n = pts.length;
  var longestLen = 0;
  var ux = 1;
  var uy = 0;
  for (var i = 0; i < n; i++) {
    var a = pts[i];
    var b = pts[(i + 1) % n];
    var ax = Number(a.x) || 0, ay = Number(a.y) || 0;
    var bx = Number(b.x) || 0, by = Number(b.y) || 0;
    var dx = bx - ax, dy = by - ay;
    var len = Math.hypot(dx, dy);
    if (len > longestLen && len > 1e-6) {
      longestLen = len;
      ux = dx / len;
      uy = dy / len;
    }
  }
  if (longestLen < 1e-6) return null;
  var vx = -uy;
  var vy = ux;
  var cx = 0, cy = 0;
  for (var j = 0; j < n; j++) {
    cx += Number(pts[j].x) || 0;
    cy += Number(pts[j].y) || 0;
  }
  cx /= n;
  cy /= n;
  var tMin = Infinity, tMax = -Infinity, sMin = Infinity, sMax = -Infinity;
  for (var k = 0; k < n; k++) {
    var px = Number(pts[k].x) || 0, py = Number(pts[k].y) || 0;
    var tx = px - cx, ty = py - cy;
    var t = tx * ux + ty * uy;
    var s = tx * vx + ty * vy;
    if (t < tMin) tMin = t;
    if (t > tMax) tMax = t;
    if (s < sMin) sMin = s;
    if (s > sMax) sMax = s;
  }
  var thick = sMax - sMin;
  var minThick = typeof MASONRY_DEF_MIN_WALL_THICKNESS_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_THICKNESS_MM : 50;
  var maxThick = typeof FRAME_DEF_WALL_MAX_THICKNESS_MM !== 'undefined' ? FRAME_DEF_WALL_MAX_THICKNESS_MM : 1000;
  if (!(thick >= minThick && thick <= maxThick)) return null;
  var seg_a = {
    p1: { x: cx + tMin * ux + sMin * vx, y: cy + tMin * uy + sMin * vy },
    p2: { x: cx + tMax * ux + sMin * vx, y: cy + tMax * uy + sMin * vy }
  };
  var seg_b = {
    p1: { x: cx + tMin * ux + sMax * vx, y: cy + tMin * uy + sMax * vy },
    p2: { x: cx + tMax * ux + sMax * vx, y: cy + tMax * uy + sMax * vy }
  };
  return { seg_a: seg_a, seg_b: seg_b };
}

function masonryDefStateDefaults() {
  return {
    includeAci4: false,
    walls: [],
    wallClasses: [],
    wallClassesAci3: [],
    wallClassesAci4: [],
    definedGroups: [],
    activeClassKey: '',
    activeSelectionScope: 'all',
    selectedDefinedGroupId: '',
    lastCommitId: null,
    previewVisible: true,
    dimOthers: true,
    showGapIssues: true,
    gapIssues: [],
    rawSegs: [],
    descs: [],
    loadedWallOverrides: {},
    pendingWallOverrides: {},
    loadedWallOverrideEntityIds: [],
    overlayCoverageIndex: null,
    gapIssueLimited: false,
    hatchPolys: []
  };
}

function masonryDefGetState() {
  if (typeof window.masonryDefState !== 'object' || !window.masonryDefState) {
    window.masonryDefState = masonryDefStateDefaults();
  }
  var st = window.masonryDefState;
  if (st.dimOthers !== true && st.dimOthers !== false) st.dimOthers = true;
  if (st.previewVisible !== true && st.previewVisible !== false) st.previewVisible = true;
  if (st.showGapIssues !== true && st.showGapIssues !== false) st.showGapIssues = true;
  if (!Array.isArray(st.walls)) st.walls = [];
  if (!Array.isArray(st.wallClasses)) st.wallClasses = [];
  if (!Array.isArray(st.wallClassesAci3)) st.wallClassesAci3 = [];
  if (!Array.isArray(st.wallClassesAci4)) st.wallClassesAci4 = [];
  if (!Array.isArray(st.definedGroups)) st.definedGroups = [];
  if (!Array.isArray(st.gapIssues)) st.gapIssues = [];
  if (!Array.isArray(st.rawSegs)) st.rawSegs = [];
  if (!Array.isArray(st.descs)) st.descs = [];
  if (!st.loadedWallOverrides || typeof st.loadedWallOverrides !== 'object') st.loadedWallOverrides = {};
  if (!st.pendingWallOverrides || typeof st.pendingWallOverrides !== 'object') st.pendingWallOverrides = {};
  if (!Array.isArray(st.loadedWallOverrideEntityIds)) st.loadedWallOverrideEntityIds = [];
  if (st.includeAci4 !== true && st.includeAci4 !== false) st.includeAci4 = false;
  return st;
}

function masonryCurrentCommitId() {
  if (typeof frameDefCurrentCommitId === 'function') return frameDefCurrentCommitId();
  var v = '';
  if (typeof getActiveViewCommitId === 'function') v = getActiveViewCommitId();
  if (!v && typeof viewCommitSelect !== 'undefined' && viewCommitSelect) v = viewCommitSelect.value;
  return String(v || '').trim();
}

function masonryIsAci3(ent) {
  return typeof frameDefIsAciValue === 'function' && frameDefIsAciValue(ent, MASONRY_DEF_ACI);
}

function masonryIsAci4(ent) {
  return typeof frameDefIsAciValue === 'function' && frameDefIsAciValue(ent, MASONRY_DEF_ACI4);
}

function masonryIsMasonryTargetEntity(ent) {
  if (!ent || ent.isBlockInsert) return false;
  var type = String(ent.entity_type || '').toUpperCase();
  if (!(typeof FRAME_DEF_ALLOWED_ENTITY_TYPES !== 'undefined' && FRAME_DEF_ALLOWED_ENTITY_TYPES[type])) return false;
  return masonryIsAci3(ent);
}

function masonryPolyPerimeter(points, closed) {
  if (!Array.isArray(points) || points.length < 2) return 0;
  var sum = 0;
  for (var i = 0; i < points.length - 1; i++) {
    var a = points[i], b = points[i + 1];
    if (!a || !b) continue;
    var dx = (Number(b.x) || 0) - (Number(a.x) || 0), dy = (Number(b.y) || 0) - (Number(a.y) || 0);
    sum += Math.sqrt(dx * dx + dy * dy);
  }
  if (closed && points.length >= 3 && points[0] && points[points.length - 1]) {
    var fa = points[0], la = points[points.length - 1];
    var ldx = (Number(fa.x) || 0) - (Number(la.x) || 0), ldy = (Number(fa.y) || 0) - (Number(la.y) || 0);
    sum += Math.sqrt(ldx * ldx + ldy * ldy);
  }
  return sum;
}

/** 닫힌 폴리곤 안에 엘레베이터/바닥 선(LINE 등, LAYER에 FLOR-EVRT)이 있으면 true → 조적에서 제외 */
function masonryDefPolygonContainsInnerLines(polyPoints, excludeEntityId, allEntities) {
  if (!Array.isArray(polyPoints) || polyPoints.length < 3 || !Array.isArray(allEntities)) return false;
  var pointInPoly = typeof frameDefPointInPolygon === 'function' ? frameDefPointInPolygon : null;
  if (!pointInPoly) return false;
  var poly = polyPoints.map(function(p) { return { x: Number(p.x) || 0, y: Number(p.y) || 0 }; });
  var lineTypes = { LINE: true, LWPOLYLINE: true, POLYLINE: true };
  for (var i = 0; i < allEntities.length; i++) {
    var e = allEntities[i];
    if (!e || e.id == null || e.id === excludeEntityId || e.isBlockInsert) continue;
    var eType = String(e.entity_type || e.type || '').toUpperCase();
    if (!lineTypes[eType]) continue;
    var layer = String(e.layer == null ? '' : e.layer).toUpperCase();
    if (layer.indexOf('FLOR-EVRT') < 0 && layer.indexOf('A-FLOR-EVRT') < 0) continue;
    var pt = null;
    if (e.point) pt = { x: Number(e.point.x) || 0, y: Number(e.point.y) || 0 };
    else if (e.points && e.points.length >= 1) pt = { x: Number(e.points[0].x) || 0, y: Number(e.points[0].y) || 0 };
    if (!pt) continue;
    if (pointInPoly(pt, poly)) return true;
    if (e.points && e.points.length >= 2) {
      var mid = { x: (Number(e.points[0].x) || 0) + (Number(e.points[1].x) || 0), y: (Number(e.points[0].y) || 0) + (Number(e.points[1].y) || 0) };
      mid.x /= 2; mid.y /= 2;
      if (pointInPoly(mid, poly)) return true;
    }
  }
  return false;
}

function masonryCollectDescriptors() {
  var st = masonryDefGetState();
  var out = [], ents = typeof allEntities !== 'undefined' ? allEntities : [];
  var includeAci4 = st.includeAci4 === true;
  var minPerimeterAci3 = typeof MASONRY_DEF_MIN_WALL_PERIMETER_MM === 'number' ? MASONRY_DEF_MIN_WALL_PERIMETER_MM : 2000;
  var minPerimeterAci4 = typeof MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_MM === 'number' ? MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_MM : 800;
  for (var i = 0; i < ents.length; i++) {
    var ent = ents[i];
    if (!ent || ent.isBlockInsert || ent.id == null) continue;
    var layer = String(ent.layer == null ? '' : ent.layer).toUpperCase();
    if (layer.indexOf('DOOR') >= 0 || layer.indexOf('WINDOW') >= 0) continue;
    var type = String(ent.entity_type || '').toUpperCase();
    if (!(typeof FRAME_DEF_ALLOWED_ENTITY_TYPES !== 'undefined' && FRAME_DEF_ALLOWED_ENTITY_TYPES[type])) continue;
    var aci = null;
    if (masonryIsAci3(ent)) aci = MASONRY_DEF_ACI;
    else if (includeAci4 && masonryIsAci4(ent)) aci = MASONRY_DEF_ACI4;
    if (aci == null) continue;
    var pts = Array.isArray(ent.points) ? ent.points : [];
    if (pts.length < 2) continue;
    var clean = [];
    for (var p = 0; p < pts.length; p++) {
      var pt = pts[p]; if (!pt) continue;
      var v = { x: Number(pt.x) || 0, y: Number(pt.y) || 0 };
      if (clean.length && typeof frameDefPointEq === 'function' && frameDefPointEq(clean[clean.length - 1], v, 1e-6)) continue;
      clean.push(v);
    }
    if (clean.length < 2) continue;
    var closed = typeof frameDefEntityClosedFlag === 'function' ? frameDefEntityClosedFlag(ent, type, clean) : false;
    if (closed && clean.length >= 3 && typeof frameDefPointEq === 'function' && typeof FRAME_DEF_LOOP_SNAP_MM !== 'undefined' && !frameDefPointEq(clean[0], clean[clean.length - 1], FRAME_DEF_LOOP_SNAP_MM)) {
      clean.push({ x: Number(clean[0].x) || 0, y: Number(clean[0].y) || 0 });
    }
    var minPerimeter = (aci === MASONRY_DEF_ACI4) ? minPerimeterAci4 : minPerimeterAci3;
    if (closed) {
      var perim = masonryPolyPerimeter(clean, true);
      /* ACI3/ACI4 공통: 폴리곤 안에 해치가 있으면 둘레 기준 완화 (작은 벽·A-WALL-ALC 등) */
      if (clean.length >= 3) {
        var pointInPoly = typeof frameDefPointInPolygon === 'function' ? frameDefPointInPolygon : null;
        if (pointInPoly) {
          for (var h = 0; h < ents.length; h++) {
            var he = ents[h];
            if (!he || String(he.entity_type || '').toUpperCase() !== 'HATCH') continue;
            var g = he.geometry || he;
            var hx = (g && g.x != null) ? Number(g.x) : (he.x != null ? Number(he.x) : NaN);
            var hy = (g && g.y != null) ? Number(g.y) : (he.y != null ? Number(he.y) : NaN);
            if (!isFinite(hx) || !isFinite(hy)) {
              var pos = he.position || he.insertion_point;
              if (pos) { hx = Number(pos.x); hy = Number(pos.y); }
            }
            if (isFinite(hx) && isFinite(hy) && pointInPoly({ x: hx, y: hy }, clean)) {
              minPerimeter = typeof MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_WITH_HATCH_MM === 'number' ? MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_WITH_HATCH_MM : 400;
              break;
            }
          }
        }
      }
      if (aci === MASONRY_DEF_ACI && (clean.length === 5 || clean.length === 4)) {
        var singleRectMin = typeof MASONRY_DEF_MIN_WALL_PERIMETER_SINGLE_RECT_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_PERIMETER_SINGLE_RECT_MM : 1500;
        if (perim < singleRectMin) continue;
      } else if (perim < minPerimeter) continue;
      if (typeof masonryDefPolygonContainsInnerLines === 'function' && masonryDefPolygonContainsInnerLines(clean, ent.id, ents)) continue;
    }
    out.push({
      id: Number(ent.id),
      type: type,
      ent: ent,
      points: clean,
      scope_key: typeof frameDefEntityHierarchyRootKey === 'function' ? frameDefEntityHierarchyRootKey(ent) : '',
      layer: String(ent.layer == null ? '' : ent.layer),
      by_layer: (ent.props == null || ent.props.color_bylayer !== false),
      closed: closed,
      aci: aci
    });
  }
  return out;
}

function masonryParseWktPolygonPoints(wkt) {
  if (!wkt || typeof wkt !== 'string') return [];
  var s = ('' + wkt).replace(/^SRID=\d+;\s*/i, '').trim();
  var pm = s.match(/POLYGON\s*(?:Z\s*)?\(\(([^)]+)\)\)/i);
  if (pm) {
    return pm[1].split(',').map(function(p) {
      var parts = p.trim().split(/\s+/);
      var x = parseFloat(parts[0]);
      var y = parseFloat(parts[1]);
      return { x: isFinite(x) ? x : 0, y: isFinite(y) ? y : 0 };
    }).filter(function(pt) { return pt; });
  }
  var m = s.match(/\(([^)]+)\)/);
  if (m) {
    return m[1].split(',').map(function(p) {
      var parts = p.trim().split(/\s+/);
      var x = parseFloat(parts[0]);
      var y = parseFloat(parts[1]);
      return { x: isFinite(x) ? x : 0, y: isFinite(y) ? y : 0 };
    }).filter(function(pt) { return pt; });
  }
  return [];
}

function masonryTransformPointByInsert(p, insert) {
  if (!p || !insert) return p;
  var x = Number(p.x) || 0, y = Number(p.y) || 0;
  var sx = Number(insert.scale_x) || 1;
  var sy = Number(insert.scale_y) || 1;
  if (sx === 0) sx = 1;
  if (sy === 0) sy = 1;
  x *= sx;
  y *= sy;
  var rot = Number(insert.rotation) || 0;
  if (rot !== 0) {
    var rad = (rot * Math.PI) / 180;
    var c = Math.cos(rad), s = Math.sin(rad);
    var nx = x * c - y * s;
    var ny = x * s + y * c;
    x = nx;
    y = ny;
  }
  var origin = insert.insert_point;
  var ox = 0, oy = 0;
  if (typeof origin === 'string' && origin.match(/POINT|\(/)) {
    var pts = origin.replace(/^[^(]*\(/, '').replace(/\)/g, '').trim().split(/\s+/);
    if (pts.length >= 2) { ox = parseFloat(pts[0]) || 0; oy = parseFloat(pts[1]) || 0; }
  } else if (origin && typeof origin === 'object' && (origin.x != null || origin.y != null)) {
    ox = Number(origin.x) || 0;
    oy = Number(origin.y) || 0;
  }
  return { x: x + ox, y: y + oy };
}

function masonryCollectHatchPolysFromBlockDef(defEntities, insert) {
  var out = [];
  if (!defEntities || !Array.isArray(defEntities) || !insert) return out;
  for (var i = 0; i < defEntities.length; i++) {
    var e = defEntities[i];
    if (!e || (String(e.entity_type || '').toUpperCase()) !== 'HATCH') continue;
    var wkt = e.geom;
    if (!wkt) continue;
    var pts = masonryParseWktPolygonPoints(wkt);
    if (pts.length < 3) continue;
    var world = pts.map(function(p) { return masonryTransformPointByInsert(p, insert); });
    out.push({ id: 'bi-' + (insert.id || '') + '-h-' + i, points: world });
  }
  return out;
}

function masonryCollectHatchPolysWithBlocks(cid) {
  var base = typeof frameDefCollectHatchPolys === 'function' ? frameDefCollectHatchPolys() : [];
  if (!cid && typeof masonryCurrentCommitId === 'function') cid = masonryCurrentCommitId();
  if (!cid || typeof fetch !== 'function') return Promise.resolve(base);
  var baseIds = {};
  for (var b = 0; b < base.length; b++) { if (base[b] && base[b].id != null) baseIds[String(base[b].id)] = true; }
  return fetch('/api/commits/' + encodeURIComponent(cid) + '/blocks/inserts')
    .then(function(r) { return r.ok ? r.json() : { inserts: [] }; })
    .then(function(data) {
      var inserts = data.inserts || [];
      if (!inserts.length) return base;
      var defIdToInserts = {};
      for (var k = 0; k < inserts.length; k++) {
        var bi = inserts[k];
        var defId = bi.block_def_id;
        if (defId == null) continue;
        if (!defIdToInserts[defId]) defIdToInserts[defId] = [];
        defIdToInserts[defId].push(bi);
      }
      var defIds = Object.keys(defIdToInserts);
      if (!defIds.length) return base;
      var promises = defIds.map(function(defId) {
        return fetch('/api/commits/' + encodeURIComponent(cid) + '/blocks/defs/' + encodeURIComponent(defId) + '/entities?limit=2000')
          .then(function(r) { return r.ok ? r.json() : { entities: [] }; })
          .then(function(res) { return { defId: defId, entities: res.entities || [] }; });
      });
      return Promise.all(promises).then(function(results) {
        var blockHatches = [];
        for (var r = 0; r < results.length; r++) {
          var defId = results[r].defId;
          var entities = results[r].entities || [];
          var insertList = defIdToInserts[defId] || [];
          for (var ii = 0; ii < insertList.length; ii++) {
            var hatches = masonryCollectHatchPolysFromBlockDef(entities, insertList[ii]);
            for (var h = 0; h < hatches.length; h++) blockHatches.push(hatches[h]);
          }
        }
        return base.concat(blockHatches);
      });
    })
    .catch(function() { return base; });
}

function masonryWallsFromHatchPolys(hatchPolys) {
  var out = [];
  if (!Array.isArray(hatchPolys) || !hatchPolys.length || typeof frameDefHatchPolyToRect !== 'function' || typeof frameDefApplyWallGeometry !== 'function') return out;
  var minT = typeof MASONRY_DEF_MIN_WALL_THICKNESS_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_THICKNESS_MM : 50;
  var maxT = typeof FRAME_DEF_WALL_MAX_THICKNESS_MM !== 'undefined' ? FRAME_DEF_WALL_MAX_THICKNESS_MM : 1000;
  for (var i = 0; i < hatchPolys.length; i++) {
    var hp = hatchPolys[i];
    if (!hp || !Array.isArray(hp.points) || hp.points.length < 3) continue;
    var rect = frameDefHatchPolyToRect(hp.points);
    if (!rect || !rect.seg_a || !rect.seg_b) continue;
    var wall = { entity_ids: [], scope_keys: [], __masonry: true };
    if (hp.id != null && typeof hp.id === 'number') wall.entity_ids = [hp.id];
    frameDefApplyWallGeometry(wall, rect.seg_a, rect.seg_b, { source: 'hatch' });
    var t = typeof frameDefWallThickness === 'function' ? frameDefWallThickness(wall) : 0;
    if (t <= minT || t > maxT) continue;
    out.push(wall);
  }
  return out;
}

function masonryDefWallBbox(wall) {
  if (!wall) return null;
  var parts = (wall.parts && wall.parts.length) ? wall.parts : [wall];
  var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (var i = 0; i < parts.length; i++) {
    var p = parts[i];
    if (!p || !p.seg_a || !p.seg_b) continue;
    var pts = [p.seg_a.p1, p.seg_a.p2, p.seg_b.p1, p.seg_b.p2];
    for (var j = 0; j < pts.length; j++) {
      if (!pts[j]) continue;
      var x = Number(pts[j].x) || 0, y = Number(pts[j].y) || 0;
      if (x < minX) minX = x; if (y < minY) minY = y;
      if (x > maxX) maxX = x; if (y > maxY) maxY = y;
    }
  }
  if (!isFinite(minX) || !isFinite(maxX) || minX >= maxX) return null;
  if (!isFinite(minY) || !isFinite(maxY) || minY >= maxY) return null;
  return { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
}

function masonryDefHatchBbox(hp) {
  if (!hp || !Array.isArray(hp.points) || hp.points.length < 2) return null;
  var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (var i = 0; i < hp.points.length; i++) {
    var p = hp.points[i];
    if (!p) continue;
    var x = Number(p.x) || 0, y = Number(p.y) || 0;
    if (x < minX) minX = x; if (y < minY) minY = y;
    if (x > maxX) maxX = x; if (y > maxY) maxY = y;
  }
  if (!isFinite(minX) || minX >= maxX || !isFinite(minY) || minY >= maxY) return null;
  return { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
}

/** points가 없거나 bbox가 너무 작은 해치는 allEntities의 HATCH 삽입점(geometry)으로 bbox 보강. 트림 시 연속 이어짐 방지용 */
function masonryDefAugmentHatchPolysWithInsertionPoints(hatchPolys) {
  if (!Array.isArray(hatchPolys)) hatchPolys = [];
  var seenIds = {};
  for (var i = 0; i < hatchPolys.length; i++) {
    var hp = hatchPolys[i];
    if (hp && hp.id != null) seenIds[String(hp.id)] = true;
  }
  var ents = typeof allEntities !== 'undefined' ? allEntities : [];
  var fallbackSideMm = 500;
  var idToInsertion = {};
  for (var j = 0; j < ents.length; j++) {
    var e = ents[j];
    if (!e || String(e.entity_type || '').toUpperCase() !== 'HATCH') continue;
    var g = e.geometry || e;
    var gx = (g && g.x != null) ? Number(g.x) : (e.x != null ? Number(e.x) : NaN);
    var gy = (g && g.y != null) ? Number(g.y) : (e.y != null ? Number(e.y) : NaN);
    if (!isFinite(gx) || !isFinite(gy)) {
      var pos = e.position || e.insertion_point;
      if (pos) { gx = Number(pos.x); gy = Number(pos.y); }
    }
    if (isFinite(gx) && isFinite(gy) && e.id != null) idToInsertion[String(e.id)] = { gx: gx, gy: gy };
  }
  var out = [];
  for (var i = 0; i < hatchPolys.length; i++) {
    var hp = hatchPolys[i];
    if (!hp) { out.push(hp); continue; }
    var hasPoints = Array.isArray(hp.points) && hp.points.length >= 2;
    if (hasPoints) { out.push(hp); continue; }
    var ins = hp.id != null ? idToInsertion[String(hp.id)] : null;
    if (ins) {
      var s = fallbackSideMm;
      out.push({
        id: hp.id,
        points: [
          { x: ins.gx - s, y: ins.gy - s },
          { x: ins.gx + s, y: ins.gy - s },
          { x: ins.gx + s, y: ins.gy + s },
          { x: ins.gx - s, y: ins.gy + s }
        ]
      });
    } else {
      out.push(hp);
    }
  }
  for (var j = 0; j < ents.length; j++) {
    var e = ents[j];
    if (!e || String(e.entity_type || '').toUpperCase() !== 'HATCH') continue;
    if (e.id != null && seenIds[String(e.id)]) continue;
    var layer = String(e.layer || '');
    if (layer.indexOf('MASN-PAT') < 0 && layer.indexOf('WALL-MASN-PAT') < 0) continue;
    var g = e.geometry || e;
    var gx = (g && g.x != null) ? Number(g.x) : (e.x != null ? Number(e.x) : NaN);
    var gy = (g && g.y != null) ? Number(g.y) : (e.y != null ? Number(e.y) : NaN);
    if (!isFinite(gx) || !isFinite(gy)) {
      var pos = e.position || e.insertion_point;
      if (pos) { gx = Number(pos.x); gy = Number(pos.y); }
    }
    if (!isFinite(gx) || !isFinite(gy)) continue;
    seenIds[String(e.id)] = true;
    var s = fallbackSideMm;
    out.push({
      id: e.id,
      points: [
        { x: gx - s, y: gy - s },
        { x: gx + s, y: gy - s },
        { x: gx + s, y: gy + s },
        { x: gx - s, y: gy + s }
      ]
    });
  }
  return out;
}

function masonryDefBboxOverlap(b1, b2) {
  if (!b1 || !b2) return false;
  return b1.minX <= b2.maxX && b2.minX <= b1.maxX && b1.minY <= b2.maxY && b2.minY <= b1.maxY;
}

/** 직선 세그먼트를 직사각형으로 클리핑한 뒤, rect 바깥에 있는 구간만 반환. segment = { p1: {x,y}, p2: {x,y} }, rect = { minX, minY, maxX, maxY }. 반환: [{ p1, p2 }, ...] (0~2개) */
function masonryDefClipSegmentOutsideRect(segment, rect) {
  if (!segment || !segment.p1 || !segment.p2 || !rect) return segment && segment.p1 && segment.p2 ? [{ p1: { x: Number(segment.p1.x) || 0, y: Number(segment.p1.y) || 0 }, p2: { x: Number(segment.p2.x) || 0, y: Number(segment.p2.y) || 0 } }] : [];
  var x1 = Number(segment.p1.x) || 0, y1 = Number(segment.p1.y) || 0, x2 = Number(segment.p2.x) || 0, y2 = Number(segment.p2.y) || 0;
  var minX = Number(rect.minX) || 0, minY = Number(rect.minY) || 0, maxX = Number(rect.maxX) || 0, maxY = Number(rect.maxY) || 0;
  if (minX >= maxX || minY >= maxY) return [{ p1: { x: x1, y: y1 }, p2: { x: x2, y: y2 } }];
  var dx = x2 - x1, dy = y2 - y1;
  var inside = function(x, y) { return x >= minX && x <= maxX && y >= minY && y <= maxY; };
  var ts = [];
  if (Math.abs(dx) > 1e-12) {
    var tx = (minX - x1) / dx;
    if (tx >= 0 && tx <= 1) { var y = y1 + tx * dy; if (y >= minY && y <= maxY) ts.push(tx); }
    tx = (maxX - x1) / dx;
    if (tx >= 0 && tx <= 1) { y = y1 + tx * dy; if (y >= minY && y <= maxY) ts.push(tx); }
  }
  if (Math.abs(dy) > 1e-12) {
    var ty = (minY - y1) / dy;
    if (ty >= 0 && ty <= 1) { var x = x1 + ty * dx; if (x >= minX && x <= maxX) ts.push(ty); }
    ty = (maxY - y1) / dy;
    if (ty >= 0 && ty <= 1) { x = x1 + ty * dx; if (x >= minX && x <= maxX) ts.push(ty); }
  }
  ts.sort(function(a, b) { return a - b; });
  var uniq = [];
  for (var u = 0; u < ts.length; u++) if (u === 0 || ts[u] - ts[u - 1] > 1e-9) uniq.push(ts[u]);
  if (uniq.length === 0) {
    if (inside(x1, y1) && inside(x2, y2)) return [];
    return [{ p1: { x: x1, y: y1 }, p2: { x: x2, y: y2 } }];
  }
  if (uniq.length === 1) {
    var t = uniq[0];
    var in1 = inside(x1, y1), in2 = inside(x2, y2);
    if (in1 && !in2) return [{ p1: { x: x1 + t * dx, y: y1 + t * dy }, p2: { x: x2, y: y2 } }];
    if (!in1 && in2) return [{ p1: { x: x1, y: y1 }, p2: { x: x1 + t * dx, y: y1 + t * dy } }];
    return [{ p1: { x: x1, y: y1 }, p2: { x: x2, y: y2 } }];
  }
  var t1 = uniq[0], t2 = uniq[uniq.length - 1];
  var out = [];
  if (t1 > 1e-9) out.push({ p1: { x: x1, y: y1 }, p2: { x: x1 + t1 * dx, y: y1 + t1 * dy } });
  if (t2 < 1 - 1e-9) out.push({ p1: { x: x1 + t2 * dx, y: y1 + t2 * dy }, p2: { x: x2, y: y2 } });
  return out;
}

/** 중심선 세그먼트(p1~p2)와 두께로 part(seg_a, seg_b) 생성. frameDefWallPartToRectQuad와 동일 기하. */
function masonryDefCenterlineToPart(p1, p2, thicknessMm) {
  if (!p1 || !p2 || !(thicknessMm > 1e-6)) return null;
  var x1 = Number(p1.x) || 0, y1 = Number(p1.y) || 0, x2 = Number(p2.x) || 0, y2 = Number(p2.y) || 0;
  var dx = x2 - x1, dy = y2 - y1;
  var len = Math.sqrt(dx * dx + dy * dy);
  if (!(len > 1e-9)) return null;
  var ax = dx / len, ay = dy / len;
  var nx = -ay, ny = ax;
  var half = (Number(thicknessMm) || 0) / 2;
  var sa1 = { x: x1 + nx * half, y: y1 + ny * half }, sa2 = { x: x2 + nx * half, y: y2 + ny * half };
  var sb1 = { x: x1 - nx * half, y: y1 - ny * half }, sb2 = { x: x2 - nx * half, y: y2 - ny * half };
  return { seg_a: { p1: sa1, p2: sa2 }, seg_b: { p1: sb1, p2: sb2 } };
}

/** 골조 플러그인과 동일한 방식으로 기둥 감지 (벽 오버레이를 기둥에서 끊기 위해) */
function masonryDefGetColumns() {
  var frameDescs = typeof frameDefCollectDescriptors === 'function' ? frameDefCollectDescriptors() : [];
  var frameRawSegs = typeof frameDefExtractSegments === 'function' ? frameDefExtractSegments(frameDescs) : [];
  var frameLoopData = (typeof frameDefCollectClosedLineLoops === 'function' ? frameDefCollectClosedLineLoops(frameRawSegs) : []).concat(
    typeof frameDefCollectClosedPolylineLoops === 'function' ? frameDefCollectClosedPolylineLoops(frameDescs) : []
  );
  var rawCols = [];
  if (typeof frameDefDetectColumnsFromPolylines === 'function') rawCols = rawCols.concat(frameDefDetectColumnsFromPolylines(frameDescs));
  if (typeof frameDefDetectColumnsFromLoopData === 'function') rawCols = rawCols.concat(frameDefDetectColumnsFromLoopData(frameLoopData));
  if (typeof frameDefDedupeColumns === 'function') rawCols = frameDefDedupeColumns(rawCols);
  var split = typeof frameDefSplitColumnsAndClosedWalls === 'function' ? frameDefSplitColumnsAndClosedWalls(rawCols, frameRawSegs) : { columns: [], walls: [] };
  return split.columns || [];
}

/** 폴리곤을 직선 한쪽 반평면으로 클리핑 (Sutherland–Hodgman). edge: { x?, y?, left?, bottom? } */
function masonryDefClipPolygonToHalfPlane(poly, edge) {
  if (!Array.isArray(poly) || poly.length < 3) return null;
  var out = [];
  var n = poly.length;
  var inside = function(p) {
    var x = Number(p.x) || 0, y = Number(p.y) || 0;
    if (edge.x != null) return edge.left ? x <= edge.x : x >= edge.x;
    if (edge.y != null) return edge.bottom ? y <= edge.y : y >= edge.y;
    return false;
  };
  var isect = function(a, b) {
    var ax = Number(a.x) || 0, ay = Number(a.y) || 0, bx = Number(b.x) || 0, by = Number(b.y) || 0;
    if (edge.x != null) {
      var dx = bx - ax;
      if (Math.abs(dx) < 1e-10) return { x: edge.x, y: (ay + by) * 0.5 };
      var t = (edge.x - ax) / dx;
      if (t < 0) t = 0; else if (t > 1) t = 1;
      return { x: edge.x, y: ay + t * (by - ay) };
    }
    if (edge.y != null) {
      var dy = by - ay;
      if (Math.abs(dy) < 1e-10) return { x: (ax + bx) * 0.5, y: edge.y };
      var t = (edge.y - ay) / dy;
      if (t < 0) t = 0; else if (t > 1) t = 1;
      return { x: ax + t * (bx - ax), y: edge.y };
    }
    return { x: ax, y: ay };
  };
  for (var i = 0; i < n; i++) {
    var a = poly[i], b = poly[(i + 1) % n];
    var isAIn = inside(a), isBIn = inside(b);
    if (isAIn && isBIn) out.push({ x: Number(b.x) || 0, y: Number(b.y) || 0 });
    else if (isAIn && !isBIn) { out.push(isect(a, b)); }
    else if (!isAIn && isBIn) { out.push(isect(a, b)); out.push({ x: Number(b.x) || 0, y: Number(b.y) || 0 }); }
  }
  if (out.length < 3) return null;
  return out;
}

/** 폴리곤에서 직사각형 영역을 뺀 부분들(기둥으로 끊은 결과). rect: { minX, minY, maxX, maxY } */
function masonryDefClipPolygonByRect(poly, rect) {
  if (!Array.isArray(poly) || poly.length < 3 || !rect || rect.minX >= rect.maxX || rect.minY >= rect.maxY) return [poly];
  var minX = Number(rect.minX) || 0, minY = Number(rect.minY) || 0, maxX = Number(rect.maxX) || 0, maxY = Number(rect.maxY) || 0;
  var pad = 0.5;
  var out = [];
  var halfPlanes = [
    { x: minX - pad, left: true },
    { x: maxX + pad, left: false },
    { y: minY - pad, bottom: true },
    { y: maxY + pad, bottom: false }
  ];
  for (var h = 0; h < halfPlanes.length; h++) {
    var clipped = masonryDefClipPolygonToHalfPlane(poly, halfPlanes[h]);
    if (clipped && clipped.length >= 3) out.push(clipped);
  }
  /* 직사각형과 겹칠 때만 바깥 조각들 반환; 폴리곤이 rect 안에 완전히 들어가면 [] (트림으로 제거) */
  return out;
}

/**
 * 조적 벽체를 인식한 선 범위 + 파싱한 폭(두께)으로 만든 직사각형 해치 하나로 표시.
 * 골조의 frameDefWallPartToRectQuad 방식을 사용해 벽당 직사각형 quad 하나로 오버레이를 덮어씀.
 * (wall.seg_a, wall.seg_b와 두께로 한 개의 직사각형을 만들어 벽체 객체로 분류·표시)
 */
function masonryDefSetWallOverlayToRectHatch(walls) {
  if (!Array.isArray(walls)) return;
  var rectQuad = typeof frameDefWallPartToRectQuad === 'function' ? frameDefWallPartToRectQuad : null;
  var overlapQuad = typeof frameDefWallOverlapQuad === 'function' ? frameDefWallOverlapQuad : null;
  for (var w = 0; w < walls.length; w++) {
    var wall = walls[w];
    if (!wall || !wall.__masonry) continue;
    if (!wall.seg_a || !wall.seg_b) continue;
    var quad = rectQuad ? frameDefWallPartToRectQuad(wall) : null;
    if (!quad || quad.length < 4) quad = overlapQuad ? frameDefWallOverlapQuad(wall) : null;
    if (quad && quad.length >= 4) {
      if (!wall.__overlay_cache) wall.__overlay_cache = { quads: [], line_parts: [], anchor: null };
      wall.__overlay_cache.wall_id = wall.wall_id;
      wall.__overlay_cache.quads = [quad];
      if (wall.parts && wall.parts.length) {
        wall.__overlay_cache.line_parts = wall.parts.slice(0, 1);
        wall.__overlay_cache.anchor = wall.parts[0];
      }
    }
  }
}

/** 벽 오버레이 쿼드를 기둥 bbox로 잘라 기둥 위치에서 끊김 */
function masonryDefTrimWallOverlaysByColumns(walls, columns) {
  if (!Array.isArray(walls) || !Array.isArray(columns) || !columns.length) return;
  var colBboxes = [];
  for (var c = 0; c < columns.length; c++) {
    var col = columns[c];
    if (!col) continue;
    var bb = col.bbox;
    if (bb && typeof bb.minX === 'number' && typeof bb.maxX === 'number' && typeof bb.minY === 'number' && typeof bb.maxY === 'number') {
      colBboxes.push(bb);
    } else if (Array.isArray(col.quad_points) && col.quad_points.length >= 4) {
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (var q = 0; q < col.quad_points.length; q++) {
        var pt = col.quad_points[q];
        if (!pt) continue;
        var x = Number(pt.x) || 0, y = Number(pt.y) || 0;
        if (x < minX) minX = x; if (y < minY) minY = y; if (x > maxX) maxX = x; if (y > maxY) maxY = y;
      }
      if (isFinite(minX) && isFinite(maxX) && minX < maxX && isFinite(minY) && isFinite(maxY) && minY < maxY) colBboxes.push({ minX: minX, minY: minY, maxX: maxX, maxY: maxY });
    }
  }
  if (!colBboxes.length) return;
  for (var w = 0; w < walls.length; w++) {
    var wall = walls[w];
    if (!wall || !wall.__overlay_cache || !Array.isArray(wall.__overlay_cache.quads)) continue;
    if (wall.__column_cut_wall) continue;
    var quads = wall.__overlay_cache.quads;
    var newQuads = [];
    for (var q = 0; q < quads.length; q++) {
      var quad = quads[q];
      if (!quad || quad.length < 3) continue;
      var poly = quad.map(function(p) { return { x: Number(p.x) || 0, y: Number(p.y) || 0 }; });
      var current = [poly];
      for (var b = 0; b < colBboxes.length; b++) {
        var bbox = colBboxes[b];
        var next = [];
        for (var k = 0; k < current.length; k++) {
          var part = current[k];
          var pMinX = Infinity, pMinY = Infinity, pMaxX = -Infinity, pMaxY = -Infinity;
          for (var vi = 0; vi < part.length; vi++) {
            var v = part[vi];
            var vx = Number(v.x) || 0, vy = Number(v.y) || 0;
            if (vx < pMinX) pMinX = vx; if (vy < pMinY) pMinY = vy; if (vx > pMaxX) pMaxX = vx; if (vy > pMaxY) pMaxY = vy;
          }
          if (!masonryDefBboxOverlap({ minX: pMinX, minY: pMinY, maxX: pMaxX, maxY: pMaxY }, bbox)) { next.push(part); continue; }
          var parts = masonryDefClipPolygonByRect(part, bbox);
          for (var pi = 0; pi < parts.length; pi++) if (parts[pi] && parts[pi].length >= 3) next.push(parts[pi]);
        }
        current = next;
      }
      for (var ni = 0; ni < current.length; ni++) if (current[ni] && current[ni].length >= 3) newQuads.push(current[ni]);
    }
    wall.__overlay_cache.quads = newQuads;
  }
}

/** 해치 bbox 트림 시 경계 여유(mm). 이만큼 확장해서 잘라 연속 이어짐을 확실히 끊음 */
var MASONRY_DEF_HATCH_TRIM_MARGIN_MM = 80;
/** 트림 클리핑에 추가로 더 넣는 갭(mm). 이만큼 더 잘라서 트림 후 쿼드가 해치 경계에 닿지 않게 함 */
var MASONRY_DEF_HATCH_TRIM_GAP_MM = 2;
/** 두 해치 사이 구간을 트림할 때, 이 거리(mm) 이내로 떨어진 해치 쌍만 "사이" 영역으로 추가 */
var MASONRY_DEF_HATCH_BETWEEN_MAX_GAP_MM = 5000;

/** 해치 쌍 사이(between) bbox 목록 반환. 트림·part 분할에서 공통 사용. 반환: [{ minX, minY, maxX, maxY }, ...] */
function masonryDefCollectBetweenHatchBboxes(hatchPolys) {
  if (!Array.isArray(hatchPolys) || hatchPolys.length < 2) return [];
  var rawBboxes = [];
  for (var h = 0; h < hatchPolys.length; h++) {
    var hp = hatchPolys[h];
    rawBboxes.push(hp ? masonryDefHatchBbox(hp) : null);
  }
  var validRawCount = 0;
  for (var r = 0; r < rawBboxes.length; r++) if (rawBboxes[r]) validRawCount++;
  if (validRawCount < 2) return [];
  var maxBetweenGap = typeof MASONRY_DEF_HATCH_BETWEEN_MAX_GAP_MM === 'number' ? MASONRY_DEF_HATCH_BETWEEN_MAX_GAP_MM : 5000;
  var betweenMargin = typeof MASONRY_DEF_HATCH_TRIM_GAP_MM === 'number' ? MASONRY_DEF_HATCH_TRIM_GAP_MM : 2;
  var out = [];
  for (var i = 0; i < rawBboxes.length; i++) {
    if (!rawBboxes[i]) continue;
    var bi = rawBboxes[i];
    for (var j = i + 1; j < rawBboxes.length; j++) {
      if (!rawBboxes[j]) continue;
      var bj = rawBboxes[j];
      var overlapY = bi.minY <= bj.maxY && bj.minY <= bi.maxY;
      if (!overlapY) continue;
      var minY = Math.min(bi.minY, bj.minY);
      var maxY = Math.max(bi.maxY, bj.maxY);
      if (bi.maxX < bj.minX) {
        var gapMm = bj.minX - bi.maxX;
        if (gapMm <= maxBetweenGap && gapMm >= 0) {
          out.push({ minX: bi.maxX - betweenMargin, minY: minY - betweenMargin, maxX: bj.minX + betweenMargin, maxY: maxY + betweenMargin });
        }
      } else if (bj.maxX < bi.minX) {
        var gapMm2 = bi.minX - bj.maxX;
        if (gapMm2 <= maxBetweenGap && gapMm2 >= 0) {
          out.push({ minX: bj.maxX - betweenMargin, minY: minY - betweenMargin, maxX: bi.minX + betweenMargin, maxY: maxY + betweenMargin });
        }
      }
    }
  }
  return out;
}

/** 벽 오버레이를 다른 해치 bbox로 잘라, 해치 경계에서 끊김(연속 이어짐 방지). 디버그 타겟 부위 대응 */
function masonryDefTrimWallOverlaysByOtherHatches(walls, hatchPolys) {
  if (!Array.isArray(walls) || !Array.isArray(hatchPolys) || hatchPolys.length < 2) return;
  var margin = typeof MASONRY_DEF_HATCH_TRIM_MARGIN_MM === 'number' ? MASONRY_DEF_HATCH_TRIM_MARGIN_MM : 80;
  var gap = typeof MASONRY_DEF_HATCH_TRIM_GAP_MM === 'number' ? MASONRY_DEF_HATCH_TRIM_GAP_MM : 2;
  var clipMargin = margin + gap;
  var hatchBboxes = [];
  for (var h = 0; h < hatchPolys.length; h++) {
    var hp = hatchPolys[h];
    if (!hp) continue;
    var bb = masonryDefHatchBbox(hp);
    if (bb) {
      hatchBboxes.push({
        id: hp.id != null ? hp.id : h,
        bbox: { minX: bb.minX - clipMargin, minY: bb.minY - clipMargin, maxX: bb.maxX + clipMargin, maxY: bb.maxY + clipMargin }
      });
    }
  }
  var betweenBboxes = typeof masonryDefCollectBetweenHatchBboxes === 'function' ? masonryDefCollectBetweenHatchBboxes(hatchPolys) : [];
  for (var b = 0; b < betweenBboxes.length; b++) {
    hatchBboxes.push({ id: 'between-' + b, bbox: betweenBboxes[b] });
  }
  if (hatchBboxes.length < 1) return;
  var pointInPoly = typeof frameDefPointInPolygon === 'function' ? frameDefPointInPolygon : null;
  var wallCenter = typeof frameDefWallItemCenter === 'function' ? frameDefWallItemCenter : null;
  for (var w = 0; w < walls.length; w++) {
    var wall = walls[w];
    if (!wall || !wall.__overlay_cache || !Array.isArray(wall.__overlay_cache.quads)) continue;
    var ownHatchIds = {};
    if (String(wall.source || '') === 'hatch' && wall.entity_ids && wall.entity_ids.length) {
      for (var ei = 0; ei < wall.entity_ids.length; ei++) ownHatchIds[String(wall.entity_ids[ei])] = true;
    }
    if (String(wall.source || '') === 'hatch' && wallCenter && pointInPoly) {
      var c = wallCenter(wall);
      if (c) for (var hi = 0; hi < hatchPolys.length; hi++) {
        var hp0 = hatchPolys[hi];
        if (hp0 && hp0.points && hp0.points.length >= 3 && pointInPoly(c, hp0.points)) ownHatchIds[String(hp0.id != null ? hp0.id : hi)] = true;
      }
    }
    var quads = wall.__overlay_cache.quads;
    var newQuads = [];
    for (var q = 0; q < quads.length; q++) {
      var quad = quads[q];
      if (!quad || quad.length < 3) continue;
      var poly = quad.map(function(p) { return { x: Number(p.x) || 0, y: Number(p.y) || 0 }; });
      var current = [poly];
      for (var b = 0; b < hatchBboxes.length; b++) {
        var hid = String(hatchBboxes[b].id);
        if (ownHatchIds[hid]) continue;
        var bbox = hatchBboxes[b].bbox;
        var next = [];
        for (var k = 0; k < current.length; k++) {
          var part = current[k];
          var pMinX = Infinity, pMinY = Infinity, pMaxX = -Infinity, pMaxY = -Infinity;
          for (var vi = 0; vi < part.length; vi++) {
            var v = part[vi];
            var vx = Number(v.x) || 0, vy = Number(v.y) || 0;
            if (vx < pMinX) pMinX = vx; if (vy < pMinY) pMinY = vy; if (vx > pMaxX) pMaxX = vx; if (vy > pMaxY) pMaxY = vy;
          }
          if (!masonryDefBboxOverlap({ minX: pMinX, minY: pMinY, maxX: pMaxX, maxY: pMaxY }, bbox)) { next.push(part); continue; }
          var parts = masonryDefClipPolygonByRect(part, bbox);
          for (var pi = 0; pi < parts.length; pi++) if (parts[pi] && parts[pi].length >= 3) next.push(parts[pi]);
        }
        current = next;
      }
      for (var ni = 0; ni < current.length; ni++) if (current[ni] && current[ni].length >= 3) newQuads.push(current[ni]);
    }
    wall.__overlay_cache.quads = newQuads;
  }
}

/** 조적 벽의 part를 해치 사이(between) 구간에서 끊어, 해당 구간에는 part가 없도록 함. 오버레이 빌드 시 해치 사이에 quad가 생기지 않게 함. */
function masonryDefSplitWallPartsByHatchGaps(walls, hatchPolys) {
  if (!Array.isArray(walls) || !Array.isArray(hatchPolys) || hatchPolys.length < 2) return;
  var betweenBboxes = typeof masonryDefCollectBetweenHatchBboxes === 'function' ? masonryDefCollectBetweenHatchBboxes(hatchPolys) : [];
  if (betweenBboxes.length < 1) return;
  var getCenterSegment = typeof frameDefWallCenterSegment === 'function' ? frameDefWallCenterSegment : null;
  var getThickness = typeof frameDefWallThickness === 'function' ? frameDefWallThickness : null;
  if (!getCenterSegment || !getThickness) return;
  var minPartLenMm = 1;
  for (var w = 0; w < walls.length; w++) {
    var wall = walls[w];
    if (!wall || !wall.__masonry) continue;
    var parts = (wall.parts && wall.parts.length) ? wall.parts : [wall];
    var newParts = [];
    for (var p = 0; p < parts.length; p++) {
      var part = parts[p];
      var centerSeg = getCenterSegment(part);
      var thick = getThickness(part);
      if (!centerSeg || !(thick > 1e-6)) {
        newParts.push(part);
        continue;
      }
      var segment = { p1: { x: centerSeg.p1.x, y: centerSeg.p1.y }, p2: { x: centerSeg.p2.x, y: centerSeg.p2.y } };
      var segments = [segment];
      for (var b = 0; b < betweenBboxes.length; b++) {
        var nextSegs = [];
        for (var s = 0; s < segments.length; s++) {
          var outside = masonryDefClipSegmentOutsideRect(segments[s], betweenBboxes[b]);
          for (var o = 0; o < outside.length; o++) nextSegs.push(outside[o]);
        }
        segments = nextSegs;
      }
      for (var s = 0; s < segments.length; s++) {
        var seg = segments[s];
        var dx = seg.p2.x - seg.p1.x, dy = seg.p2.y - seg.p1.y;
        var len = Math.sqrt(dx * dx + dy * dy);
        if (len > minPartLenMm) {
          var newPart = masonryDefCenterlineToPart(seg.p1, seg.p2, thick);
          if (newPart) newParts.push(newPart);
        }
      }
    }
    wall.parts = newParts;
  }
}

function masonryDefSplitWallsByHatches(walls, hatchPolys) {
  if (!Array.isArray(walls) || !Array.isArray(hatchPolys) || !hatchPolys.length) return walls;
  var pointInPoly = typeof frameDefPointInPolygon === 'function' ? frameDefPointInPolygon : null;
  var wallCenter = typeof frameDefWallItemCenter === 'function' ? frameDefWallItemCenter : null;
  var out = [];
  for (var wi = 0; wi < walls.length; wi++) {
    var w = walls[wi];
    if (!w || !w.__masonry) { out.push(w); continue; }
    var scopeKeys = w.scope_keys || [];
    var isBlockInternal = scopeKeys.some(function(sk) { return String(sk).trim().indexOf('bi:') === 0; });
    if (isBlockInternal) { out.push(w); continue; }
    if (w.source === 'closed-bbox') { out.push(w); continue; }
    var wBbox = masonryDefWallBbox(w);
    if (!wBbox) { out.push(w); continue; }
    var overlapping = [];
    for (var h = 0; h < hatchPolys.length; h++) {
      var hp = hatchPolys[h];
      if (!hp) continue;
      var hBbox = masonryDefHatchBbox(hp);
      if (!hBbox || !masonryDefBboxOverlap(wBbox, hBbox)) continue;
      overlapping.push(hp);
    }
    if (overlapping.length === 0) { out.push(w); continue; }
    if (overlapping.length === 1) {
      var hp0 = overlapping[0];
      if (wallCenter && pointInPoly && hp0.points && hp0.points.length >= 3) {
        var center = wallCenter(w);
        if (!center || !pointInPoly(center, hp0.points)) { out.push(w); continue; }
      }
      var rect = typeof frameDefHatchPolyToRect === 'function' ? frameDefHatchPolyToRect(hp0.points) : null;
      if (rect && rect.seg_a && rect.seg_b && typeof frameDefApplyWallGeometry === 'function') {
        frameDefApplyWallGeometry(w, rect.seg_a, rect.seg_b, { source: 'hatch' });
        w.__masonry = true;
      }
      out.push(w);
      continue;
    }
    var multiPushed = false;
    for (var oi = 0; oi < overlapping.length; oi++) {
      var hpOi = overlapping[oi];
      if (wallCenter && pointInPoly && hpOi.points && hpOi.points.length >= 3) {
        var c = wallCenter(w);
        if (!c || !pointInPoly(c, hpOi.points)) continue;
      }
      var rect = typeof frameDefHatchPolyToRect === 'function' ? frameDefHatchPolyToRect(hpOi.points) : null;
      if (!rect || !rect.seg_a || !rect.seg_b || typeof frameDefApplyWallGeometry !== 'function') continue;
      var clone = {
        entity_ids: (w.entity_ids || []).slice(),
        scope_keys: (w.scope_keys || []).slice(),
        __masonry: true
      };
      frameDefApplyWallGeometry(clone, rect.seg_a, rect.seg_b, { source: 'hatch' });
      out.push(clone);
      multiPushed = true;
    }
    if (!multiPushed) out.push(w);
  }
  return out;
}

/**
 * 조적 전면 단순화: 닫힌 루프 전체를 한 경로로 벽 변환.
 * 4·5 꼭지점: bbox 또는 frameDefHatchPolyToRect.
 * 6+ 꼭지점: longest-segment 우선, 실패 시 bbox, __column_cut_wall 부여.
 */
function masonryWallsFromClosedLoops(loopData) {
  if (!Array.isArray(loopData)) return [];
  var hatchToRect = typeof frameDefHatchPolyToRect === 'function';
  var applyGeo = typeof frameDefApplyWallGeometry === 'function';
  if (!hatchToRect || !applyGeo) return [];
  var minT = typeof MASONRY_DEF_MIN_WALL_THICKNESS_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_THICKNESS_MM : 50;
  var maxT = typeof FRAME_DEF_WALL_MAX_THICKNESS_MM !== 'undefined' ? FRAME_DEF_WALL_MAX_THICKNESS_MM : 1000;
  var out = [];
  for (var j = 0; j < loopData.length; j++) {
    var loop = loopData[j];
    if (!loop || !Array.isArray(loop.points) || loop.points.length < 4) continue;
    var eids = loop.entity_ids;
    if (!Array.isArray(eids) || !eids.length) continue;
    var loopPts = loop.points || [];
    var nPts = loopPts.length;
    var singleFourVertex = (eids.length === 1 && (nPts === 5 || nPts === 4));
    var columnCutLoop = nPts >= 6;
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var pi = 0; pi < loopPts.length; pi++) {
      var px = Number(loopPts[pi].x) || 0, py = Number(loopPts[pi].y) || 0;
      if (px < minX) minX = px; if (py < minY) minY = py;
      if (px > maxX) maxX = px; if (py > maxY) maxY = py;
    }
    var rect = null;
    if (columnCutLoop) {
      if (typeof masonryDefLongestSegmentRectFromPolygon === 'function') {
        rect = masonryDefLongestSegmentRectFromPolygon(loopPts);
      }
      if (!rect && typeof masonryDefBboxToWallSegments === 'function') {
        rect = masonryDefBboxToWallSegments(minX, minY, maxX, maxY);
      }
    } else if (singleFourVertex && typeof masonryDefBboxToWallSegments === 'function') {
      rect = masonryDefBboxToWallSegments(minX, minY, maxX, maxY);
    } else {
      var usePad = typeof masonryDefIsApproximatelyRectangular === 'function' && masonryDefIsApproximatelyRectangular(loopPts);
      var pad = usePad ? (typeof MASONRY_DEF_BBOX_CONTAIN_MM !== 'undefined' ? MASONRY_DEF_BBOX_CONTAIN_MM : 2000) : 0;
      var ptsForRect = loopPts;
      if (pad > 0) {
        ptsForRect = [
          { x: minX - pad, y: minY - pad },
          { x: maxX + pad, y: minY - pad },
          { x: maxX + pad, y: maxY + pad },
          { x: minX - pad, y: maxY + pad }
        ];
      }
      rect = hatchToRect ? frameDefHatchPolyToRect(ptsForRect) : null;
    }
    if (!rect || !rect.seg_a || !rect.seg_b) continue;
    var wall = {
      entity_ids: eids.slice(),
      scope_keys: Array.isArray(loop.scope_keys) ? loop.scope_keys.slice() : [],
      __masonry: true
    };
    frameDefApplyWallGeometry(wall, rect.seg_a, rect.seg_b, { source: 'closed-bbox' });
    if (columnCutLoop) wall.__column_cut_wall = true;
    var t = typeof frameDefWallThickness === 'function' ? frameDefWallThickness(wall) : 0;
    if (t > minT && t <= maxT) out.push(wall);
  }
  return out;
}

/** 루프에 안 들어간 닫힌 폴리라인만 구제 (조적 전면 단순화 후에도 유지) */
function masonryDefEnsureClosedDescriptorWalls(walls, descs) {
  if (!Array.isArray(walls) || !Array.isArray(descs)) return walls;
  var hasClosedBboxFor = {};
  for (var wi = 0; wi < walls.length; wi++) {
    var w = walls[wi];
    if (!w || String(w.source || '') !== 'closed-bbox') continue;
    var ids = w.entity_ids;
    if (Array.isArray(ids)) for (var ei = 0; ei < ids.length; ei++) hasClosedBboxFor[String(ids[ei])] = true;
  }
  var hatchToRect = typeof frameDefHatchPolyToRect === 'function';
  var applyGeo = typeof frameDefApplyWallGeometry === 'function';
  if (!hatchToRect || !applyGeo) return walls;
  var minT = typeof MASONRY_DEF_MIN_WALL_THICKNESS_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_THICKNESS_MM : 50;
  var maxT = typeof FRAME_DEF_WALL_MAX_THICKNESS_MM !== 'undefined' ? FRAME_DEF_WALL_MAX_THICKNESS_MM : 1000;
  var out = walls.slice();
  for (var d = 0; d < descs.length; d++) {
    var desc = descs[d];
    if (!desc || desc.closed !== true) continue;
    var type = String(desc.type || '').toUpperCase();
    if (type !== 'LWPOLYLINE' && type !== 'POLYLINE') continue;
    if (hasClosedBboxFor[String(desc.id)]) continue;
    var pts = Array.isArray(desc.points) ? desc.points : [];
    if (pts.length < 4) continue;
    var poly = pts.map(function(p) { return { x: Number(p.x) || 0, y: Number(p.y) || 0 }; });
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var pi = 0; pi < poly.length; pi++) {
      var px = poly[pi].x, py = poly[pi].y;
      if (px < minX) minX = px; if (py < minY) minY = py;
      if (px > maxX) maxX = px; if (py > maxY) maxY = py;
    }
    var rect = null;
    var singleFourVertex = (pts.length === 5);
    if (singleFourVertex && typeof masonryDefBboxToWallSegments === 'function') {
      var pad = 1;
      rect = masonryDefBboxToWallSegments(minX - pad, minY - pad, maxX + pad, maxY + pad);
    } else {
      var pad = 1;
      if (typeof masonryDefIsApproximatelyRectangular === 'function' && masonryDefIsApproximatelyRectangular(poly)) {
        pad = typeof MASONRY_DEF_BBOX_CONTAIN_MM !== 'undefined' ? MASONRY_DEF_BBOX_CONTAIN_MM : 2000;
      }
      var expandedPoly = [
        { x: minX - pad, y: minY - pad },
        { x: maxX + pad, y: minY - pad },
        { x: maxX + pad, y: maxY + pad },
        { x: minX - pad, y: maxY + pad }
      ];
      rect = hatchToRect ? frameDefHatchPolyToRect(expandedPoly) : null;
    }
    if (!rect || !rect.seg_a || !rect.seg_b) continue;
    var wall = {
      entity_ids: [desc.id],
      scope_keys: [String(desc.scope_key || '').trim()],
      source: 'closed-bbox',
      __masonry: true
    };
    frameDefApplyWallGeometry(wall, rect.seg_a, rect.seg_b, { source: 'closed-bbox' });
    var t = typeof frameDefWallThickness === 'function' ? frameDefWallThickness(wall) : 0;
    if (t > minT && t <= maxT) out.push(wall);
  }
  return out;
}

function masonryDetectNow() {
  var st = masonryDefGetState();
  if (typeof viewMode !== 'undefined' && viewMode !== 'single') {
    if (typeof showMsg === 'function') showMsg('msg', '조적 정의는 단일 보기에서만 사용할 수 있습니다.', 'error');
    return [];
  }
  var cid = masonryCurrentCommitId();
  if (!cid) {
    if (typeof showMsg === 'function') showMsg('msg', '버전을 선택하세요.', 'error');
    return [];
  }
  var descs = masonryCollectDescriptors();
  var aci4EntityIds = {};
  for (var di = 0; di < descs.length; di++) {
    if (descs[di].aci === MASONRY_DEF_ACI4) aci4EntityIds[descs[di].id] = true;
  }
  var rawSegs = typeof frameDefExtractSegments === 'function' ? frameDefExtractSegments(descs) : [];
  /* 조적: 기존 선에 구속. 병합(merge)하지 않고 원본 세그먼트만 사용해, 해치 사이 등 갭에 벽이 생기지 않게 함. */
  var segs = typeof frameDefTrimWallOverlapSegments === 'function' ? frameDefTrimWallOverlapSegments(rawSegs) : rawSegs;
  var loopSnap = typeof MASONRY_DEF_LOOP_SNAP_MM !== 'undefined' ? MASONRY_DEF_LOOP_SNAP_MM : 5;
  var loopData = (typeof frameDefCollectClosedLineLoops === 'function' ? frameDefCollectClosedLineLoops(rawSegs, loopSnap) : []).concat(
    typeof frameDefCollectClosedPolylineLoops === 'function' ? frameDefCollectClosedPolylineLoops(descs) : []
  );
  /* 조적 전면 단순화: 꼭지점 4개 이상만 (상한 제거, 10+ 비정형·기둥 잘림 포함) */
  loopData = (loopData || []).filter(function(loop) {
    var n = (loop && loop.points && loop.points.length) || 0;
    return n >= 4;
  });
  var excludeSet = {};
  var cols = typeof masonryDefGetColumns === 'function' ? masonryDefGetColumns() : [];
  /* 조적: 보간(track-graph) 보류, 닫힌 루프 위주만 사용 */
  var openWalls = [];
  var pairedLoopWallsRaw = typeof frameDefDetectWallsFromClosedLoopPairs === 'function' ? frameDefDetectWallsFromClosedLoopPairs(loopData).filter(function(w) {
    if (!w || !w.entity_ids || !w.entity_ids.length) return false;
    return true;
  }) : [];
  /* 조적: 닫힌 루프 쌍 벽은 필터 없이 전부 사용 */
  var pairedLoopWalls = pairedLoopWallsRaw;
  /* 조적 전면 단순화: 단일 경로로 닫힌 루프 → 벽 (골조 closed-join·fallback 제거) */
  var joinedClosedWalls = typeof masonryWallsFromClosedLoops === 'function' ? masonryWallsFromClosedLoops(loopData) : [];
  var wallSupportSeed = openWalls.concat(pairedLoopWalls);
  var closedWallsLegacy = [];
  var supportedClosedWallsLegacy = typeof frameDefFilterClosedWallsBySupport === 'function' ? frameDefFilterClosedWallsBySupport(closedWallsLegacy, wallSupportSeed) : [];
  var supportedJoinedClosedWalls = typeof frameDefFilterClosedWallsBySupport === 'function' ? frameDefFilterClosedWallsBySupport(joinedClosedWalls, wallSupportSeed) : [];
  var supportedClosedWalls = supportedClosedWallsLegacy.concat(supportedJoinedClosedWalls);
  var supportedWallKeys = {};
  for (var si = 0; si < supportedJoinedClosedWalls.length; si++) {
    var k = (supportedJoinedClosedWalls[si].entity_ids || []).slice().sort().join(',');
    if (k) supportedWallKeys[k] = true;
  }
  for (var ji = 0; ji < joinedClosedWalls.length; ji++) {
    var w = joinedClosedWalls[ji];
    if (!w) continue;
    var key = (w.entity_ids || []).slice().sort().join(',');
    if (key && !supportedWallKeys[key]) supportedClosedWalls.push(w);
  }
  var rawWalls = openWalls.concat(pairedLoopWalls, supportedClosedWalls);
  var mergedWalls = typeof frameDefMergeWallItems === 'function' ? frameDefMergeWallItems(rawWalls) : rawWalls;
  var walls = typeof frameDefDedupeWallsByGeometry === 'function' ? frameDefDedupeWallsByGeometry(mergedWalls) : mergedWalls;
  var minT = typeof MASONRY_DEF_MIN_WALL_THICKNESS_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_THICKNESS_MM : 50;
  var maxT = typeof FRAME_DEF_WALL_MAX_THICKNESS_MM !== 'undefined' ? FRAME_DEF_WALL_MAX_THICKNESS_MM : 1000;
  walls = walls.filter(function(w) {
    var t = typeof frameDefWallThickness === 'function' ? frameDefWallThickness(w) : 0;
    return t > minT && t <= maxT;
  });
  for (var mi = 0; mi < walls.length; mi++) {
    if (walls[mi]) walls[mi].__masonry = true;
  }
  if (typeof frameDefAutoNormalizeWallAxis === 'function') frameDefAutoNormalizeWallAxis(walls);
  if (typeof frameDefPrepareWallOverlayCaches === 'function') frameDefPrepareWallOverlayCaches(walls, true);
  var ow;
  for (ow = 0; ow < walls.length; ow++) {
    if (walls[ow] && typeof frameDefApplyWallGeometryFromOverlay === 'function') frameDefApplyWallGeometryFromOverlay(walls[ow]);
  }
  st.hatchPolys = typeof frameDefCollectHatchPolys === 'function' ? frameDefCollectHatchPolys() : [];
  if (typeof masonryDefAugmentHatchPolysWithInsertionPoints === 'function') st.hatchPolys = masonryDefAugmentHatchPolysWithInsertionPoints(st.hatchPolys);
  if (Object.keys(aci4EntityIds).length > 0 && Array.isArray(st.hatchPolys) && st.hatchPolys.length > 0) {
    walls = walls.filter(function(w) {
      var ids = w.entity_ids || [];
      var hasAci4 = false;
      for (var ei = 0; ei < ids.length; ei++) {
        if (aci4EntityIds[ids[ei]]) { hasAci4 = true; break; }
      }
      if (!hasAci4) return true;
      var center = typeof frameDefWallItemCenter === 'function' ? frameDefWallItemCenter(w) : null;
      if (!center) return false;
      return typeof frameDefPointInAnyHatch === 'function' && frameDefPointInAnyHatch(center, st.hatchPolys);
    });
  }
  if (Array.isArray(st.hatchPolys) && st.hatchPolys.length > 0 && typeof frameDefHatchPolyToRect === 'function' && typeof frameDefApplyWallGeometry === 'function') {
    walls = masonryDefSplitWallsByHatches(walls, st.hatchPolys);
  }
  if (Object.keys(aci4EntityIds).length > 0 && Array.isArray(st.hatchPolys) && st.hatchPolys.length > 0 && typeof frameDefWallItemCenter === 'function' && typeof frameDefPointInAnyHatch === 'function') {
    walls = walls.filter(function(w) {
      var ids = w.entity_ids || [];
      var hasAci4 = false;
      for (var ei = 0; ei < ids.length; ei++) { if (aci4EntityIds[ids[ei]]) { hasAci4 = true; break; } }
      if (!hasAci4) return true;
      var center = frameDefWallItemCenter(w);
      return center && frameDefPointInAnyHatch(center, st.hatchPolys);
    });
  }
  var maxT2 = typeof FRAME_DEF_WALL_MAX_THICKNESS_MM !== 'undefined' ? FRAME_DEF_WALL_MAX_THICKNESS_MM : 1000;
  var minT2 = typeof MASONRY_DEF_MIN_WALL_THICKNESS_MM !== 'undefined' ? MASONRY_DEF_MIN_WALL_THICKNESS_MM : 50;
  walls = walls.filter(function(w) {
    var t = typeof frameDefWallThickness === 'function' ? frameDefWallThickness(w) : 0;
    return t > minT2 && t <= maxT2;
  });
  if (typeof frameDefAssignWallStableKeys === 'function') frameDefAssignWallStableKeys(walls, cid);
  var loadedOverrides = {};
  var mergedOverrides = {};
  if (typeof frameDefBuildMergedWallOverrideMap === 'function') mergedOverrides = frameDefBuildMergedWallOverrideMap(loadedOverrides, st.pendingWallOverrides || {});
  if (typeof frameDefApplyWallOverrides === 'function') frameDefApplyWallOverrides(walls, mergedOverrides);
  for (var preWi = 0; preWi < walls.length; preWi++) walls[preWi].wall_id = 'wall-' + String(preWi + 1);
  if (typeof frameDefPrepareWallOverlayCaches === 'function') frameDefPrepareWallOverlayCaches(walls);
  walls = typeof frameDefFilterDominatedParallelWalls === 'function' ? frameDefFilterDominatedParallelWalls(walls, mergedOverrides) : walls;
  walls = typeof masonryDefEnsureClosedDescriptorWalls === 'function' ? masonryDefEnsureClosedDescriptorWalls(walls, descs) : walls;
  if (typeof masonryDefSplitWallPartsByHatchGaps === 'function' && Array.isArray(st.hatchPolys) && st.hatchPolys.length >= 2) masonryDefSplitWallPartsByHatchGaps(walls, st.hatchPolys);
  if (typeof frameDefPrepareWallOverlayCaches === 'function') frameDefPrepareWallOverlayCaches(walls);
  /* 조적: 인식한 범위 + 파싱한 폭으로 직사각형 해치 하나를 벽체 표시로 사용 (골조 참고) */
  if (typeof masonryDefSetWallOverlayToRectHatch === 'function') masonryDefSetWallOverlayToRectHatch(walls);
  if (typeof masonryDefTrimWallOverlaysByColumns === 'function' && cols && cols.length) masonryDefTrimWallOverlaysByColumns(walls, cols);
  if (typeof masonryDefTrimWallOverlaysByOtherHatches === 'function' && Array.isArray(st.hatchPolys) && st.hatchPolys.length >= 2) masonryDefTrimWallOverlaysByOtherHatches(walls, st.hatchPolys);
  for (var wi = 0; wi < walls.length; wi++) walls[wi].wall_id = 'wall-' + String(wi + 1);
  var aci3Walls = [];
  var aci4Walls = [];
  for (var si = 0; si < walls.length; si++) {
    var w = walls[si];
    var ids = w.entity_ids || [];
    var hasAci4 = false;
    for (var qi = 0; qi < ids.length; qi++) { if (aci4EntityIds[ids[qi]]) { hasAci4 = true; break; } }
    if (hasAci4) aci4Walls.push(w); else aci3Walls.push(w);
  }
  var wc3 = typeof frameDefClusterWallThickness === 'function' ? frameDefClusterWallThickness(aci3Walls) : { classes: [], tol: 0 };
  var wc4 = typeof frameDefClusterWallThickness === 'function' ? frameDefClusterWallThickness(aci4Walls) : { classes: [], tol: 0 };
  var classes3 = (wc3 && wc3.classes) ? wc3.classes : [];
  var classes4 = (wc4 && wc4.classes) ? wc4.classes : [];
  for (var c3i = 0; c3i < classes3.length; c3i++) {
    if (classes3[c3i]) classes3[c3i].key = 'aci3:' + (classes3[c3i].key || '');
  }
  for (var c4i = 0; c4i < classes4.length; c4i++) {
    if (classes4[c4i]) classes4[c4i].key = 'aci4:' + (classes4[c4i].key || '');
  }
  st.wallClassesAci3 = classes3;
  st.wallClassesAci4 = classes4;
  st.wallClasses = classes3.concat(classes4);
  var wc = wc3.tol != null ? wc3 : wc4;
  st._gapIssueLimitReason = '';
  st._gapIssueLimitExceptionMessage = '';
  try {
    st.overlayCoverageIndex = typeof frameDefBuildWallOverlayCoverageIndex === 'function' ? frameDefBuildWallOverlayCoverageIndex(walls) : null;
  } catch (e) {
    st.overlayCoverageIndex = null;
    st.gapIssueLimited = true;
  }
  var gapIssues = [];
  try {
    if (typeof frameDefCollectWallGapIssues === 'function') gapIssues = frameDefCollectWallGapIssues(walls, cols);
  } catch (e) {}
  try {
    if (typeof frameDefCollectGapIssuesByHatchBoundary === 'function') {
      var boundaryGaps = frameDefCollectGapIssuesByHatchBoundary(walls, rawSegs, cols);
      for (var bi = 0; bi < boundaryGaps.length; bi++) gapIssues.push(boundaryGaps[bi]);
    }
  } catch (e) {}
  if (typeof frameDefDedupeGapIssues === 'function') gapIssues = frameDefDedupeGapIssues(gapIssues);
  if (typeof frameDefMergeOverlappingGapIssues === 'function') gapIssues = frameDefMergeOverlappingGapIssues(gapIssues);
  if (typeof frameDefFilterGapIssuesOutsideColumns === 'function') gapIssues = frameDefFilterGapIssuesOutsideColumns(gapIssues, cols);
  if (typeof frameDefFilterGapIssuesOnlyIsolated === 'function' && typeof FRAME_DEF_GAP_ISOLATED_MIN_DIST_MM !== 'undefined') {
    gapIssues = frameDefFilterGapIssuesOnlyIsolated(gapIssues, walls, FRAME_DEF_GAP_ISOLATED_MIN_DIST_MM);
  }
  st.walls = walls;
  st.activeClassKey = '';
  st.activeSelectionScope = 'all';
  st.selectedDefinedGroupId = '';
  st.lastCommitId = String(cid);
  st.loadedWallOverrides = loadedOverrides;
  st.loadedWallOverrideEntityIds = [];
  st.gapIssues = gapIssues;
  st.rawSegs = rawSegs.slice ? rawSegs.slice() : [];
  st.descs = descs.slice ? descs.slice() : [];
  masonryRefreshDefinedGroupList();
  masonryRenderClassList();
  if (typeof masonryDefPublishDebugReport === 'function') masonryDefPublishDebugReport();
  if (typeof draw === 'function') draw();
  var msg = '조적 자동탐지 완료: ACI3 벽체 ' + String(aci3Walls.length) + '개';
  if (aci4Walls.length > 0) msg += ' / ACI4 벽체(해치 내부만) ' + String(aci4Walls.length) + '개';
  if (wc && typeof wc.tol === 'number') msg += ' (두께군집 tol ' + (wc.tol.toFixed(1)) + 'mm)';
  if (typeof showMsg === 'function') showMsg('msg', msg, 'success');
  return walls;
}

function masonryCollectDefinedGroups() {
  var map = {};
  var ents = typeof allEntities !== 'undefined' ? allEntities : [];
  for (var i = 0; i < ents.length; i++) {
    var ent = ents[i];
    if (!ent || ent.isBlockInsert || ent.id == null) continue;
    var ua = ent.props && ent.props.user_attrs;
    if (!ua || typeof ua !== 'object') continue;
    var gid = String(ua.masonry_group_id || '').trim();
    if (!gid) continue;
    if (!map[gid]) {
      var no = parseInt(ua.masonry_group_no, 10);
      if (!(no > 0)) { var m = gid.match(/-(\d+)$/); no = m ? parseInt(m[1], 10) : 0; }
      map[gid] = { group_id: gid, group_no_num: no > 0 ? no : 0, label: String(ua.masonry_definition_label || '조적'), entity_ids: [] };
    }
    map[gid].entity_ids.push(Number(ent.id));
  }
  var out = Object.keys(map).map(function(k) {
    var g = map[k];
    g.entity_ids = typeof frameDefUniqueEntityIds === 'function' ? frameDefUniqueEntityIds(g.entity_ids) : g.entity_ids;
    return g;
  });
  out.sort(function(a, b) { return (b.group_no_num || 0) - (a.group_no_num || 0); });
  return out;
}

function masonryRefreshDefinedGroupList() {
  var st = masonryDefGetState();
  st.definedGroups = masonryCollectDefinedGroups();
  var sel = document.getElementById('masonryDefDefinedList');
  var sum = document.getElementById('masonryDefDefinedSummary');
  var oldSel = String(st.selectedDefinedGroupId || (sel ? sel.value : '') || '').trim();
  if (sel) {
    sel.innerHTML = '<option value="">(없음)</option>';
    for (var i = 0; i < st.definedGroups.length; i++) {
      var g = st.definedGroups[i];
      var op = document.createElement('option');
      op.value = String(g.group_id);
      op.textContent = String(g.group_id) + ' (' + String(g.entity_ids.length) + '개)';
      sel.appendChild(op);
    }
    var exists = st.definedGroups.some(function(g) { return String(g.group_id) === oldSel; });
    st.selectedDefinedGroupId = exists ? oldSel : '';
    sel.value = st.selectedDefinedGroupId;
  }
  if (sum) sum.textContent = st.definedGroups.length ? ('적용된 조적정의 묶음 ' + String(st.definedGroups.length) + '개') : '적용된 조적정의 묶음이 없습니다.';
}

function masonryClassByKey(key) {
  var st = masonryDefGetState();
  var list = st.wallClasses || [];
  for (var i = 0; i < list.length; i++) {
    if (String(list[i].key) === String(key)) return list[i];
  }
  return null;
}

function masonryClassLabel(cls) {
  if (!cls) return '';
  if (cls.kind === 'wall' && (cls.thickness_mm != null || (cls.items && cls.items[0]))) {
    var t = cls.thickness_mm != null ? cls.thickness_mm : (cls.items && cls.items[0] ? (cls.items[0].thickness_mm != null ? cls.items[0].thickness_mm : 0) : 0);
    return '벽체 ' + String(typeof frameDefRound10 === 'function' ? frameDefRound10(t) : Math.round(t / 10) * 10) + 'mm';
  }
  return cls.key || '';
}

function masonryRenderClassList() {
  var st = masonryDefGetState();
  var wallElAci3 = document.getElementById('masonryDefWallClassListAci3');
  var wallElAci4 = document.getElementById('masonryDefWallClassListAci4');
  var sumEl = document.getElementById('masonryDefSummary');
  var active = String(st.activeClassKey || '');
  var scope = String(st.activeSelectionScope || '');
  var btnAll = document.getElementById('masonryDefSelectAllBtn');
  var btnAci3 = document.getElementById('masonryDefSelectAci3Btn');
  var btnAci4 = document.getElementById('masonryDefSelectAci4Btn');
  function renderRows(list) {
    if (!list || !list.length) return '<div style="color:#57606a;">결과 없음</div>';
    var html = [];
    for (var i = 0; i < list.length; i++) {
      var c = list[i], on = String(c.key) === active;
      html.push(
        '<div data-masonry-class="' + (typeof escapeHtml === 'function' ? escapeHtml(String(c.key)) : String(c.key)) + '" style="padding:7px 8px; border:1px solid ' + (on ? '#2563eb' : '#d0d7de') + '; border-radius:6px; cursor:pointer; background:' + (on ? '#eff6ff' : '#fff') + '; margin-bottom:6px;">' +
        '<div style="display:flex; justify-content:space-between; gap:8px;"><strong style="font-size:0.82rem;">' + (typeof escapeHtml === 'function' ? escapeHtml(masonryClassLabel(c)) : masonryClassLabel(c)) + '</strong><span style="font-size:0.78rem; color:#57606a;">' + String(c.count || 0) + '개</span></div></div>'
      );
    }
    return html.join('');
  }
  if (wallElAci3) wallElAci3.innerHTML = renderRows(st.wallClassesAci3 || []);
  if (wallElAci4) wallElAci4.innerHTML = renderRows(st.wallClassesAci4 || []);
  if (btnAll) { btnAll.style.background = scope === 'all' ? '#2563eb' : '#6e7781'; btnAll.style.borderColor = scope === 'all' ? '#1d4ed8' : '#6e7781'; btnAll.style.color = '#ffffff'; }
  if (btnAci3) { btnAci3.style.background = scope === 'aci3' ? '#2563eb' : '#6e7781'; btnAci3.style.borderColor = scope === 'aci3' ? '#1d4ed8' : '#6e7781'; btnAci3.style.color = '#ffffff'; }
  if (btnAci4) { btnAci4.style.background = scope === 'aci4' ? '#2563eb' : '#6e7781'; btnAci4.style.borderColor = scope === 'aci4' ? '#1d4ed8' : '#6e7781'; btnAci4.style.color = '#ffffff'; }
  if (sumEl) {
    var selectedLabel = '';
    if (active) {
      var activeClass = masonryClassByKey(active);
      selectedLabel = activeClass ? masonryClassLabel(activeClass) : active;
    } else if (scope) {
      selectedLabel = scope === 'all' ? '전체 선택' : (scope === 'aci3' ? 'ACI3만 선택' : (scope === 'aci4' ? 'ACI4만 선택' : scope));
    }
    var aci3Cnt = (st.wallClassesAci3 || []).reduce(function(s, c) { return s + (c.count || 0); }, 0);
    var aci4Cnt = (st.wallClassesAci4 || []).reduce(function(s, c) { return s + (c.count || 0); }, 0);
    var sumTxt = '자동 탐지: ACI3 벽체 ' + String(aci3Cnt) + '개';
    if (aci4Cnt > 0) sumTxt += ' / ACI4 벽체 ' + String(aci4Cnt) + '개';
    if (selectedLabel) sumTxt += ' / 선택: ' + selectedLabel;
    sumEl.textContent = sumTxt;
  }
}

function masonryFilterWallEntityIds(ids) {
  if (!Array.isArray(ids) || !ids.length) return ids;
  var ents = typeof allEntities !== 'undefined' ? allEntities : [];
  var byId = {};
  for (var i = 0; i < ents.length; i++) {
    if (ents[i] && ents[i].id != null) byId[String(ents[i].id)] = ents[i];
  }
  var allowed = (typeof FRAME_DEF_ALLOWED_ENTITY_TYPES !== 'undefined' && FRAME_DEF_ALLOWED_ENTITY_TYPES) ? FRAME_DEF_ALLOWED_ENTITY_TYPES : { LINE: true, LWPOLYLINE: true, POLYLINE: true };
  return ids.filter(function(id) {
    var ent = byId[String(id)];
    if (!ent) return false;
    var type = String(ent.entity_type || '').toUpperCase();
    return !!allowed[type];
  });
}

function masonryCollectScopeEntityIds(scope) {
  var st = masonryDefGetState(), ids = [];
  var s = String(scope || '').trim();
  if (s === 'all') {
    for (var wi = 0; wi < (st.wallClasses || []).length; wi++) ids = ids.concat((st.wallClasses[wi].entity_ids || []));
  } else if (s === 'aci3') {
    for (var w3 = 0; w3 < (st.wallClassesAci3 || []).length; w3++) ids = ids.concat((st.wallClassesAci3[w3].entity_ids || []));
  } else if (s === 'aci4') {
    for (var w4 = 0; w4 < (st.wallClassesAci4 || []).length; w4++) ids = ids.concat((st.wallClassesAci4[w4].entity_ids || []));
  }
  ids = typeof frameDefUniqueEntityIds === 'function' ? frameDefUniqueEntityIds(ids) : ids;
  return masonryFilterWallEntityIds(ids);
}

function masonrySelectScope(scope, silent) {
  var st = masonryDefGetState(), s = String(scope || '').trim();
  if (s !== 'all' && s !== 'aci3' && s !== 'aci4') return false;
  var ids = masonryCollectScopeEntityIds(s);
  st.activeSelectionScope = s;
  st.activeClassKey = '';
  st.selectedDefinedGroupId = '';
  if (typeof frameDefSetSelectedEntities === 'function') frameDefSetSelectedEntities(ids);
  masonryRenderClassList();
  if (typeof draw === 'function') draw();
  var scopeLabel = s === 'all' ? '전체 선택' : (s === 'aci3' ? 'ACI3만 선택' : 'ACI4만 선택');
  if (!silent && typeof showMsg === 'function') showMsg('msg', '선택: ' + scopeLabel, 'info');
  return true;
}

function masonrySelectClass(key, silent) {
  var st = masonryDefGetState(), k = String(key || '').trim(), cls = masonryClassByKey(k);
  if (!k || !cls) return false;
  st.activeClassKey = k;
  st.activeSelectionScope = '';
  st.selectedDefinedGroupId = '';
  var ids = masonryFilterWallEntityIds(cls.entity_ids || []);
  if (typeof frameDefSetSelectedEntities === 'function') frameDefSetSelectedEntities(ids);
  masonryRenderClassList();
  if (typeof draw === 'function') draw();
  if (!silent && typeof showMsg === 'function') showMsg('msg', '선택: ' + masonryClassLabel(cls), 'info');
  return true;
}

function masonrySelectDefinedGroup(gid, silent) {
  var st = masonryDefGetState();
  var g = (st.definedGroups || []).find(function(x) { return String(x.group_id) === String(gid); });
  if (!g) return false;
  st.selectedDefinedGroupId = String(g.group_id);
  st.activeClassKey = '';
  st.activeSelectionScope = '';
  if (typeof frameDefSetSelectedEntities === 'function') frameDefSetSelectedEntities(g.entity_ids || []);
  masonryRenderClassList();
  if (typeof draw === 'function') draw();
  if (!silent && typeof showMsg === 'function') showMsg('msg', '적용 묶음 선택: ' + String(g.group_id), 'info');
  return true;
}

function masonryCollectTargetsForApply() {
  var st = masonryDefGetState(), targets = [];
  if (st.selectedDefinedGroupId) {
    var g = (st.definedGroups || []).find(function(x) { return String(x.group_id) === String(st.selectedDefinedGroupId); });
    if (g) return [{ kind: 'defined', label: String(g.group_id), entity_ids: g.entity_ids || [] }];
  }
  if (st.activeClassKey) {
    var cls = masonryClassByKey(st.activeClassKey);
    if (cls && cls.entity_ids) return [{ kind: 'wall', class_key: cls.key, entity_ids: cls.entity_ids, thickness_mm: cls.thickness_mm }];
  }
  var scope = String(st.activeSelectionScope || '').trim();
  if (scope === 'all') {
    for (var wi = 0; wi < (st.wallClasses || []).length; wi++) targets.push(st.wallClasses[wi]);
  } else if (scope === 'aci3') {
    for (var w3 = 0; w3 < (st.wallClassesAci3 || []).length; w3++) targets.push(st.wallClassesAci3[w3]);
  } else if (scope === 'aci4') {
    for (var w4 = 0; w4 < (st.wallClassesAci4 || []).length; w4++) targets.push(st.wallClassesAci4[w4]);
  }
  if (!scope && (st.wallClasses || []).length) {
    for (var wj = 0; wj < (st.wallClasses || []).length; wj++) targets.push(st.wallClasses[wj]);
  }
  return targets;
}

function masonryCollectMaxGroupNo() {
  var maxNo = 0;
  var ents = typeof allEntities !== 'undefined' ? allEntities : [];
  for (var i = 0; i < ents.length; i++) {
    var ent = ents[i], ua = ent && ent.props && ent.props.user_attrs;
    if (!ent || ent.isBlockInsert || ent.id == null || !ua || typeof ua !== 'object') continue;
    var no = parseInt(ua.masonry_group_no, 10);
    if (!(no > 0)) { var m = String(ua.masonry_group_id || '').match(/-(\d+)$/); if (m) no = parseInt(m[1], 10); }
    if (no > maxNo) maxNo = no;
  }
  return maxNo;
}

function masonryPadNo(n) {
  var x = parseInt(n, 10);
  if (!(x > 0)) x = 1;
  return x > 999 ? String(x) : String(x).padStart(3, '0');
}

function masonryNormalizeLabel(v) {
  var s = String(v == null ? '' : v).trim();
  return s || '조적';
}

async function masonryEnsureProjectAttrKeys() {
  var pid = (typeof viewProjectSelect !== 'undefined' && viewProjectSelect) ? String(viewProjectSelect.value || '').trim() : '';
  if (!pid) return;
  try {
    var prRes = await fetch('/api/projects/' + pid);
    if (!prRes.ok) return;
    var project = await prRes.json().catch(function() { return {}; });
    var settings = project && project.settings && typeof project.settings === 'object' ? project.settings : {};
    var common = Array.isArray(settings.common_attr_keys) ? settings.common_attr_keys.slice() : [];
    var changed = false;
    for (var i = 0; i < MASONRY_DEF_ATTR_KEYS.length; i++) {
      if (common.indexOf(MASONRY_DEF_ATTR_KEYS[i]) < 0) { common.push(MASONRY_DEF_ATTR_KEYS[i]); changed = true; }
    }
    if (!changed) return;
    await fetch('/api/projects/' + pid, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings: { common_attr_keys: common } })
    });
  } catch (_) {}
}

async function masonryPatchEntityAttrs(commitId, updates) {
  var ids = Object.keys(updates || {});
  if (!ids.length) return { okCount: 0, failed: [] };
  var cursor = 0, okCount = 0, failed = [];
  var limit = Math.min(8, ids.length);
  var workers = [];
  async function worker() {
    while (true) {
      if (cursor >= ids.length) break;
      var idx = cursor;
      cursor += 1;
      var id = ids[idx], attrs = updates[id];
      try {
        var res = await fetch('/api/commits/' + commitId + '/entities/' + id, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_attrs: attrs })
        });
        if (!res.ok) {
          failed.push({ id: Number(id), reason: await res.text().catch(function() { return res.statusText; }) });
          continue;
        }
        okCount += 1;
        var ent = typeof frameDefEntityById === 'function' ? frameDefEntityById(id) : null;
        if (ent) { ent.props = ent.props || {}; ent.props.user_attrs = JSON.parse(JSON.stringify(attrs)); }
      } catch (e) {
        failed.push({ id: Number(id), reason: (e && e.message) || '네트워크 오류' });
      }
    }
  }
  for (var w = 0; w < limit; w++) workers.push(worker());
  await Promise.all(workers);
  return { okCount: okCount, failed: failed };
}

async function masonryApplySelection() {
  var st = masonryDefGetState();
  if (typeof viewMode !== 'undefined' && viewMode !== 'single') {
    if (typeof showMsg === 'function') showMsg('msg', '조적 정의는 단일 보기에서만 적용할 수 있습니다.', 'error');
    return;
  }
  var cid = masonryCurrentCommitId();
  if (!cid) {
    if (typeof showMsg === 'function') showMsg('msg', '버전을 선택하세요.', 'error');
    return;
  }
  if (st.lastCommitId && String(st.lastCommitId) !== String(cid)) {
    if (typeof masonryResetState === 'function') masonryResetState({ keepLabel: true });
    if (typeof showMsg === 'function') showMsg('msg', '버전이 변경되어 상태를 초기화했습니다. 다시 탐지하세요.', 'info');
    return;
  }
  var targets = masonryCollectTargetsForApply();
  if (!targets.length) {
    if (typeof showMsg === 'function') showMsg('msg', '적용할 조적 분류가 없습니다.', 'error');
    return;
  }
  targets.sort(function(a, b) {
    var ay = (a.center && a.center.y) != null ? a.center.y : 0;
    var by = (b.center && b.center.y) != null ? b.center.y : 0;
    if (Math.abs(by - ay) > 1e-9) return by - ay;
    return ((a.center && a.center.x) != null ? a.center.x : 0) - ((b.center && b.center.x) != null ? b.center.x : 0);
  });
  var labelEl = document.getElementById('masonryDefLabelInput');
  var label = masonryNormalizeLabel(labelEl ? labelEl.value : '');
  if (labelEl) labelEl.value = label;
  var updates = {};
  var groupNo = masonryCollectMaxGroupNo() + 1;
  var groupCount = 0;
  var firstAppliedId = '';
  var round10 = typeof frameDefRound10 === 'function' ? frameDefRound10 : function(v) { return Math.round((Number(v) || 0) / 10) * 10; };
  var entityById = typeof frameDefEntityById === 'function' ? frameDefEntityById : function() { return null; };
  for (var i = 0; i < targets.length; i++) {
    var t = targets[i];
    if (!t || !t.entity_ids || !t.entity_ids.length) continue;
    var noStr = masonryPadNo(groupNo + groupCount);
    var gid = label + '-' + noStr;
    if (!firstAppliedId) firstAppliedId = gid;
    groupCount += 1;
    var ids = typeof frameDefUniqueEntityIds === 'function' ? frameDefUniqueEntityIds(t.entity_ids) : t.entity_ids;
    ids = masonryFilterWallEntityIds(ids);
    for (var ei = 0; ei < ids.length; ei++) {
      var eid = Number(ids[ei]);
      if (!(eid > 0)) continue;
      var ent = entityById(eid);
      var cur = (ent && ent.props && ent.props.user_attrs && typeof ent.props.user_attrs === 'object') ? JSON.parse(JSON.stringify(ent.props.user_attrs)) : {};
      cur.masonry_definition_label = label;
      cur.masonry_group_id = gid;
      cur.masonry_group_no = noStr;
      cur.masonry_group_role = 'origin';
      cur.masonry_kind = 'wall';
      cur.masonry_class_key = String(t.class_key != null ? t.class_key : (t.key != null ? t.key : ''));
      cur.masonry_wall_thickness_mm = t.thickness_mm != null ? String(round10(t.thickness_mm)) : '';
      updates[eid] = cur;
    }
  }
  if (!Object.keys(updates).length) {
    if (typeof showMsg === 'function') showMsg('msg', '적용할 엔티티가 없습니다.', 'error');
    return;
  }
  await masonryEnsureProjectAttrKeys();
  var result = await masonryPatchEntityAttrs(cid, updates);
  masonryRefreshDefinedGroupList();
  if (result.okCount > 0 && firstAppliedId && typeof masonrySelectDefinedGroup === 'function') masonrySelectDefinedGroup(firstAppliedId, true);
  if (typeof updateCadPropsPanel === 'function') updateCadPropsPanel();
  if (typeof updateRightDetail === 'function') updateRightDetail();
  if (typeof loadAttrManage === 'function') loadAttrManage();
  if (typeof loadQueryAttrKeys === 'function') loadQueryAttrKeys();
  if (typeof draw === 'function') draw();
  var msg = !result.failed.length ? ('조적 속성 적용 완료: ' + String(result.okCount) + '개 엔티티 / ' + String(groupCount) + '개 묶음') : ('부분 적용: 성공 ' + String(result.okCount) + ', 실패 ' + String(result.failed.length));
  if (typeof showMsg === 'function') showMsg('msg', msg, !result.failed.length ? 'success' : 'error');
}

function masonryPreviewGroups() {
  var st = masonryDefGetState(), out = [];
  if (st.selectedDefinedGroupId) {
    var g = (st.definedGroups || []).find(function(x) { return String(x.group_id) === String(st.selectedDefinedGroupId); });
    if (g) {
      out.push({ kind: 'defined', label: String(g.group_id), entity_ids: typeof frameDefUniqueEntityIds === 'function' ? frameDefUniqueEntityIds(g.entity_ids || []) : (g.entity_ids || []) });
      return out;
    }
  }
  if (st.activeClassKey) {
    var cls = masonryClassByKey(st.activeClassKey);
    if (cls) out.push({ kind: 'wall', class_obj: cls });
    return out;
  }
  var scope = String(st.activeSelectionScope || '').trim();
  if (!scope && (st.wallClasses || []).length) scope = 'all';
  if (scope === 'all') {
    for (var wi = 0; wi < (st.wallClasses || []).length; wi++) out.push({ kind: 'wall', class_obj: st.wallClasses[wi] });
  } else if (scope === 'aci3') {
    for (var w3 = 0; w3 < (st.wallClassesAci3 || []).length; w3++) out.push({ kind: 'wall', class_obj: st.wallClassesAci3[w3] });
  } else if (scope === 'aci4') {
    for (var w4 = 0; w4 < (st.wallClassesAci4 || []).length; w4++) out.push({ kind: 'wall', class_obj: st.wallClassesAci4[w4] });
  }
  return out;
}

function masonryDrawPreviewOverlays() {
  if (typeof selectedFeatureId !== 'undefined' && selectedFeatureId !== 'masonry-object-define') return;
  var st = masonryDefGetState();
  if (st.previewVisible === false) return;
  var groups = masonryPreviewGroups();
  if (!groups.length) return;
  if (typeof ctx === 'undefined' || !ctx || typeof toScreen !== 'function') return;
  ctx.save();
  if (typeof ctx.font !== 'undefined') ctx.font = '11px sans-serif';
  for (var i = 0; i < groups.length; i++) {
    var g = groups[i];
    if (g.kind === 'defined' && typeof frameDefDrawDefinedOverlay === 'function') frameDefDrawDefinedOverlay(g);
    else if (g.class_obj && typeof frameDefDrawClassOverlay === 'function') frameDefDrawClassOverlay(g.class_obj);
  }
  ctx.restore();
}

function masonryRefreshPanelState() {
  masonryRefreshDefinedGroupList();
  masonryRenderClassList();
  var overlayChk = document.getElementById('masonryDefPreviewOverlayChk');
  var dimOthersChk = document.getElementById('masonryDefDimOthersChk');
  var gapChk = document.getElementById('masonryDefShowGapIssuesChk');
  var includeAci4Chk = document.getElementById('masonryDefIncludeAci4Chk');
  var st = masonryDefGetState();
  if (overlayChk) overlayChk.checked = st.previewVisible !== false;
  if (dimOthersChk) dimOthersChk.checked = st.dimOthers === true;
  if (gapChk) gapChk.checked = st.showGapIssues !== false;
  if (includeAci4Chk) includeAci4Chk.checked = st.includeAci4 === true;
}

function masonryResetState(opts) {
  var st = masonryDefGetState();
  var keepLabel = !!(opts && opts.keepLabel);
  st.walls = [];
  st.wallClasses = [];
  st.wallClassesAci3 = [];
  st.wallClassesAci4 = [];
  st.definedGroups = [];
  st.activeClassKey = '';
  st.activeSelectionScope = 'all';
  st.selectedDefinedGroupId = '';
  st.gapIssues = [];
  st.rawSegs = [];
  st.descs = [];
  st.loadedWallOverrides = {};
  st.pendingWallOverrides = {};
  st.loadedWallOverrideEntityIds = [];
  st.overlayCoverageIndex = null;
  st.gapIssueLimited = false;
  if (!(opts && opts.keepCommit)) st.lastCommitId = null;
  if (!keepLabel) {
    var labelEl = document.getElementById('masonryDefLabelInput');
    if (labelEl) labelEl.value = '조적';
  }
  masonryRefreshPanelState();
  if (typeof draw === 'function') draw();
}

function masonryHandleContextChange(commitId) {
  var st = masonryDefGetState();
  var cid = String(commitId == null ? '' : commitId).trim();
  if (!cid) { masonryResetState({ keepLabel: true }); return; }
  masonryRefreshDefinedGroupList();
  if (st.lastCommitId && String(st.lastCommitId) !== cid) masonryResetState({ keepLabel: true });
}

function masonryDefDebugDump() {
  var st = masonryDefGetState();
  var lines = [];
  lines.push('=== 조적 디버그 덤프 ===');
  lines.push('lastCommitId: ' + String(st.lastCommitId || ''));
  lines.push('includeAci4: ' + !!st.includeAci4);
  lines.push('walls: ' + (st.walls && st.walls.length) + '개');
  lines.push('descs: ' + (st.descs && st.descs.length) + '개');
  lines.push('hatchPolys: ' + (st.hatchPolys && st.hatchPolys.length) + '개');
  lines.push('wallClassesAci3: ' + (st.wallClassesAci3 && st.wallClassesAci3.length) + '개');
  lines.push('wallClassesAci4: ' + (st.wallClassesAci4 && st.wallClassesAci4.length) + '개');
  var walls = st.walls || [];
  for (var i = 0; i < Math.min(walls.length, 10); i++) {
    var w = walls[i];
    if (!w) continue;
    var parts = (w.parts && w.parts.length) ? w.parts : [w];
    lines.push('');
    lines.push('--- 벽 #' + (i + 1) + ' wall_id=' + (w.wall_id || '') + ' thickness_mm=' + (w.thickness_mm != null ? w.thickness_mm : '') + ' __masonry=' + !!w.__masonry + ' parts=' + parts.length);
    for (var j = 0; j < parts.length; j++) {
      var p = parts[j];
      if (!p || !p.seg_a || !p.seg_b) continue;
      var sa = p.seg_a, sb = p.seg_b;
      lines.push('  part' + j + ' seg_a: (' + (sa.p1 && sa.p1.x) + ',' + (sa.p1 && sa.p1.y) + ')-(' + (sa.p2 && sa.p2.x) + ',' + (sa.p2 && sa.p2.y) + ')');
      lines.push('  part' + j + ' seg_b: (' + (sb.p1 && sb.p1.x) + ',' + (sb.p1 && sb.p1.y) + ')-(' + (sb.p2 && sb.p2.x) + ',' + (sb.p2 && sb.p2.y) + ')');
    }
  }
  if (walls.length > 10) lines.push('\n... 외 ' + (walls.length - 10) + '개 벽 생략');
  return lines.join('\n');
}

/** 조적 전용 디버그 타겟 (골조 타겟과 별개). 연속 이어짐 현상 확인용 해치 부위 + 미인식 객체 디버깅용 */
function masonryDefGetDebugTargets() {
  return [
    { x: 99862.9100507558, y: 35722.21485229865, label: 'A-WALL-MASN Polyline (99862.91, 35722.21)' },
    { x: 117912.9100507554, y: 257707.2148522987, label: 'Hatch PAT2 연속이어짐-1 (117912.91, 257707.21)' },
    { x: 96457.9100507544, y: 257857.2148522987, label: 'Hatch PAT2 연속이어짐-2 (96457.91, 257857.21)' },
    { x: 94492.91005075536, y: 257782.21485229836, label: '두 해치 사이 연속이어짐 (92527~96457) (94492.91, 257782.21)' },
    { x: 112412.9100507553, y: 256437.2148522977, label: '기둥으로 잘린 Polyline (112412.91, 256437.21)' },
    { x: 91727.91005075625, y: 263982.214852298, label: '안에 해치 있는 작은 벽 Hatch (91727.91, 263982.21)' }
  ];
}

function masonryDefWhyNotMasonry(ent) {
  if (!ent) return { ok: false, reason: '엔티티 없음' };
  if (ent.isBlockInsert) return { ok: false, reason: '블록 삽입점(선택 대상 아님)' };
  if (ent.id == null) return { ok: false, reason: 'id 없음' };
  var layer = String(ent.layer == null ? '' : ent.layer).toUpperCase();
  if (layer.indexOf('DOOR') >= 0 || layer.indexOf('WINDOW') >= 0) return { ok: false, reason: '레이어가 DOOR/WINDOW임', layer: ent.layer };
  var type = String(ent.entity_type || '').toUpperCase();
  var allowed = typeof FRAME_DEF_ALLOWED_ENTITY_TYPES !== 'undefined' && FRAME_DEF_ALLOWED_ENTITY_TYPES[type];
  if (!allowed) return { ok: false, reason: '허용 타입 아님 (LINE/LWPOLYLINE/POLYLINE 등)', type: type };
  var pts = Array.isArray(ent.points) ? ent.points : [];
  if (pts.length < 2) return { ok: false, reason: '포인트 2개 미만', point_count: pts.length };
  var resolvedAci = typeof frameDefEntityDisplayAci === 'function' ? frameDefEntityDisplayAci(ent) : null;
  var st = masonryDefGetState();
  var includeAci4 = st.includeAci4 === true;
  var isAci3 = typeof frameDefIsAciValue === 'function' && frameDefIsAciValue(ent, MASONRY_DEF_ACI);
  var isAci4 = includeAci4 && typeof frameDefIsAciValue === 'function' && frameDefIsAciValue(ent, MASONRY_DEF_ACI4);
  if (!isAci3 && !isAci4) {
    var aciNote = resolvedAci != null ? ' (해당 레이어/색상 ACI=' + resolvedAci + ')' : ' (레이어 색상 미매칭)';
    return { ok: false, reason: '조적은 ACI 3 또는 ACI 4만 사용함' + aciNote, resolved_aci: resolvedAci, layer: ent.layer, color: ent.color };
  }
  var clean = [];
  for (var p = 0; p < pts.length; p++) {
    var pt = pts[p]; if (!pt) continue;
    var v = { x: Number(pt.x) || 0, y: Number(pt.y) || 0 };
    if (clean.length && typeof frameDefPointEq === 'function' && frameDefPointEq(clean[clean.length - 1], v, 1e-6)) continue;
    clean.push(v);
  }
  if (clean.length < 2) return { ok: false, reason: '유효 포인트 2개 미만' };
  var closed = typeof frameDefEntityClosedFlag === 'function' ? frameDefEntityClosedFlag(ent, type, clean) : false;
  var minPerimeter = (isAci4 ? (typeof MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_MM === 'number' ? MASONRY_DEF_MIN_WALL_PERIMETER_ACI4_MM : 800) : (typeof MASONRY_DEF_MIN_WALL_PERIMETER_MM === 'number' ? MASONRY_DEF_MIN_WALL_PERIMETER_MM : 2000));
  if (closed && masonryPolyPerimeter(clean, true) < minPerimeter) {
    return { ok: false, reason: '닫힌 폴리라인 둘레가 최소 기준 미만 (mm)', perimeter_min: minPerimeter, perimeter: masonryPolyPerimeter(clean, true), closed: true };
  }
  return { ok: true };
}

/** 타겟 좌표 근처 엔티티 중 폴리라인/라인을 나열하고, 디스크립터 포함 여부·미포함 시 사유를 반환 (디버깅용) */
function masonryDefDebugEntitiesNearTarget(target, descIds, radiusMm) {
  var tx = Number(target.x) || 0, ty = Number(target.y) || 0;
  var radius = Number(radiusMm) > 0 ? radiusMm : 2500;
  var descSet = {};
  if (Array.isArray(descIds)) for (var i = 0; i < descIds.length; i++) descSet[String(descIds[i])] = true;
  var ents = typeof allEntities !== 'undefined' ? allEntities : [];
  var out = [];
  for (var i = 0; i < ents.length; i++) {
    var e = ents[i];
    if (!e || e.id == null) continue;
    var type = String(e.entity_type || e.type || '').toUpperCase();
    if (type !== 'LWPOLYLINE' && type !== 'POLYLINE' && type !== 'LINE') continue;
    var layer = String(e.layer || '');
    if (layer.toUpperCase().indexOf('A-WALL-MASN') < 0 && layer.toUpperCase().indexOf('A-WALL-ALC') < 0) continue;
    var dist = Infinity;
    if (e.point) dist = Math.hypot((Number(e.point.x) || 0) - tx, (Number(e.point.y) || 0) - ty);
    else if (e.points && e.points.length >= 1) {
      for (var j = 0; j < e.points.length; j++) {
        var p = e.points[j];
        if (!p) continue;
        var d = Math.hypot((Number(p.x) || 0) - tx, (Number(p.y) || 0) - ty);
        if (d < dist) dist = d;
      }
    }
    if (dist > radius) continue;
    var inDescs = descSet[String(e.id)] === true;
    var why = inDescs ? null : (typeof masonryDefWhyNotMasonry === 'function' ? masonryDefWhyNotMasonry(e) : { reason: 'unknown' });
    out.push({
      id: e.id,
      entity_type: e.entity_type || e.type,
      layer: layer,
      point_count: (e.points && e.points.length) || 0,
      dist_to_target_mm: Math.round(dist),
      in_descriptors: inDescs,
      why_not: why
    });
  }
  out.sort(function(a, b) { return (a.dist_to_target_mm || 0) - (b.dist_to_target_mm || 0); });
  return out.slice(0, 15);
}

function masonryDefNearbyNotDescriptors(targetPoint, radiusMm, descIds, maxCount) {
  var ents = typeof allEntities !== 'undefined' ? allEntities : [];
  var x = Number(targetPoint.x) || 0, y = Number(targetPoint.y) || 0;
  var descSet = {};
  if (Array.isArray(descIds)) for (var i = 0; i < descIds.length; i++) descSet[String(descIds[i])] = true;
  var radius = Number(radiusMm) > 0 ? radiusMm : 5000;
  var max = Math.min(Number(maxCount) || 10, 20);
  var out = [];
  for (var i = 0; i < ents.length && out.length < max; i++) {
    var e = ents[i];
    if (!e || e.id == null || descSet[String(e.id)]) continue;
    var dist = Infinity;
    if (e.point) dist = Math.hypot(e.point.x - x, e.point.y - y);
    else if (e.points && e.points.length >= 1) {
      for (var j = 0; j < e.points.length; j++) {
        var p = e.points[j];
        if (!p) continue;
        var d = Math.hypot((Number(p.x) || 0) - x, (Number(p.y) || 0) - y);
        if (d < dist) dist = d;
      }
    }
    if (dist > radius) continue;
    var why = masonryDefWhyNotMasonry(e);
    out.push({
      id: e.id,
      type: e.entity_type,
      layer: e.layer,
      block_insert_id: e.block_insert_id,
      dist: Math.round(dist),
      why_not: why
    });
  }
  out.sort(function(a, b) { return (a.dist || 0) - (b.dist || 0); });
  return out.slice(0, max);
}

function masonryDefDescriptorsContainingPoint(pt, descs) {
  if (!pt || !Array.isArray(descs)) return [];
  var out = [];
  var pointInPoly = typeof frameDefPointInPolygon === 'function' ? frameDefPointInPolygon : null;
  var px = Number(pt.x) || 0, py = Number(pt.y) || 0;
  var tol = 100;
  var bboxContainMm = typeof MASONRY_DEF_BBOX_CONTAIN_MM !== 'undefined' ? MASONRY_DEF_BBOX_CONTAIN_MM : 2000;
  for (var i = 0; i < descs.length; i++) {
    var d = descs[i];
    if (!d || d.closed !== true) continue;
    var pts = Array.isArray(d.points) ? d.points : [];
    if (pts.length < 4) continue;
    var poly = pts.map(function(p) { return { x: Number(p.x) || 0, y: Number(p.y) || 0 }; });
    if (pointInPoly && pointInPoly(pt, poly)) { out.push({ id: d.id, type: d.type, layer: d.layer || '', scope_key: (d.scope_key || '').trim() }); continue; }
    var near = false;
    for (var j = 0; j < poly.length; j++) {
      var a = poly[j], b = poly[(j + 1) % poly.length];
      if (!a || !b) continue;
      var dist = typeof masonryDefDistPointToSegment === 'function' ? masonryDefDistPointToSegment(px, py, a.x, a.y, b.x, b.y) : Infinity;
      if (dist <= tol) { near = true; break; }
    }
    if (near) { out.push({ id: d.id, type: d.type, layer: d.layer || '', scope_key: (d.scope_key || '').trim() }); continue; }
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var pi = 0; pi < poly.length; pi++) {
      var p = poly[pi];
      if (p.x < minX) minX = p.x; if (p.y < minY) minY = p.y;
      if (p.x > maxX) maxX = p.x; if (p.y > maxY) maxY = p.y;
    }
    if (px >= minX - bboxContainMm && px <= maxX + bboxContainMm && py >= minY - bboxContainMm && py <= maxY + bboxContainMm) {
      out.push({ id: d.id, type: d.type, layer: d.layer || '', scope_key: (d.scope_key || '').trim() });
    }
  }
  return out;
}

/** 타겟이 단일 5꼭지점(닫힌 사각형) 대상으로 제대로 포함되는지 디버깅용 판정 */
function masonryDefDebugSingleFourVertexCheck(target, descs, walls) {
  var tx = Number(target.x) || 0, ty = Number(target.y) || 0;
  var out = {
    target_xy: { x: tx, y: ty },
    nearest_descriptor: null,
    point_count: null,
    single_four_vertex_eligible: false,
    in_wall_list: false,
    wall_ids_with_descriptor: [],
    treated_as_single_four_vertex: false,
    summary: ''
  };
  if (!Array.isArray(descs) || !descs.length) {
    out.summary = '디스크립터 없음';
    return out;
  }
  var best = null, bestDist = Infinity;
  for (var i = 0; i < descs.length; i++) {
    var d = descs[i];
    if (!d || d.closed !== true) continue;
    var pts = Array.isArray(d.points) ? d.points : [];
    if (pts.length < 4) continue;
    var dist = Infinity;
    if (typeof frameDefDebugDescriptorDistance === 'function') dist = frameDefDebugDescriptorDistance(target, d);
    else if (pts.length > 0) {
      var cx = 0, cy = 0;
      for (var k = 0; k < pts.length; k++) { cx += Number(pts[k].x) || 0; cy += Number(pts[k].y) || 0; }
      cx /= pts.length; cy /= pts.length;
      dist = Math.hypot(tx - cx, ty - cy);
    }
    if (dist < bestDist) { bestDist = dist; best = d; }
  }
  if (!best) {
    out.summary = '타겟 근처 닫힌 디스크립터 없음';
    return out;
  }
  var ptCount = (best.points && best.points.length) || 0;
  out.nearest_descriptor = { id: best.id, layer: best.layer || '', scope_key: (best.scope_key || '').trim() };
  out.point_count = ptCount;
  out.single_four_vertex_eligible = (ptCount === 5);
  var wallIds = [];
  for (var w = 0; w < (walls && walls.length) || 0; w++) {
    var wall = walls[w];
    if (!wall || !Array.isArray(wall.entity_ids)) continue;
    for (var e = 0; e < wall.entity_ids.length; e++) {
      if (String(wall.entity_ids[e]) === String(best.id)) {
        wallIds.push(wall.wall_id || ('wall-' + (w + 1)));
        break;
      }
    }
  }
  out.wall_ids_with_descriptor = wallIds;
  out.in_wall_list = wallIds.length > 0;
  var singleTreat = false;
  if (wallIds.length > 0 && out.single_four_vertex_eligible) {
    for (var wi = 0; wi < walls.length; wi++) {
      var ww = walls[wi];
      if (!ww || !Array.isArray(ww.entity_ids)) continue;
      var hasDesc = false;
      for (var ei = 0; ei < ww.entity_ids.length; ei++) { if (String(ww.entity_ids[ei]) === String(best.id)) { hasDesc = true; break; } }
      if (!hasDesc) continue;
      if (String(ww.source || '') === 'closed-bbox' && ww.entity_ids.length === 1) { singleTreat = true; break; }
    }
  }
  out.treated_as_single_four_vertex = singleTreat;
  if (out.in_wall_list && out.single_four_vertex_eligible && out.treated_as_single_four_vertex) {
    out.summary = '해당: 단일 5꼭지점(닫힌 사각형)으로 벽체 목록에 포함됨 (장변=길이, 단변=폭)';
  } else if (out.in_wall_list) {
    out.summary = '벽체 목록에는 포함됨 (단일 5꼭지점 전용 처리 아님)';
  } else if (out.single_four_vertex_eligible) {
    out.summary = '단일 5꼭지점 조건 충족하나 벽체 목록에 없음';
  } else {
    out.summary = '단일 5꼭지점 아님(point_count=' + ptCount + ') 또는 타겟과 매칭되는 디스크립터 없음';
  }
  return out;
}

function masonryDefDistPointToSegment(px, py, ax, ay, bx, by) {
  var dx = bx - ax, dy = by - ay;
  var len2 = dx * dx + dy * dy;
  if (len2 < 1e-12) return Math.hypot(px - ax, py - ay);
  var t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2));
  var qx = ax + t * dx, qy = ay + t * dy;
  return Math.hypot(px - qx, py - qy);
}

function masonryDefPointNearWallQuads(wall, pt, toleranceMm) {
  var cache = typeof frameDefBuildWallOverlayCache === 'function' ? frameDefBuildWallOverlayCache(wall) : null;
  var quads = cache && Array.isArray(cache.quads) ? cache.quads : [];
  var tol = Number(toleranceMm) > 0 ? toleranceMm : 100;
  var px = Number(pt.x) || 0, py = Number(pt.y) || 0;
  for (var q = 0; q < quads.length; q++) {
    var quad = quads[q];
    if (!Array.isArray(quad) || quad.length < 3) continue;
    for (var i = 0; i < quad.length; i++) {
      var a = quad[i], b = quad[(i + 1) % quad.length];
      if (!a || !b) continue;
      var d = masonryDefDistPointToSegment(px, py, Number(a.x)||0, Number(a.y)||0, Number(b.x)||0, Number(b.y)||0);
      if (d <= tol) return true;
    }
  }
  return false;
}

function masonryDefWallsContainingPoint(pt, walls) {
  if (!pt || !Array.isArray(walls)) return [];
  var out = [];
  var wallContains = typeof frameDefPointInWallOverlayQuads === 'function' ? frameDefPointInWallOverlayQuads : null;
  var nearWall = typeof masonryDefPointNearWallQuads === 'function' ? masonryDefPointNearWallQuads : null;
  var descs = (typeof masonryDefGetState === 'function' ? masonryDefGetState() : {}).descs || [];
  var descById = {};
  for (var di = 0; di < descs.length; di++) {
    var d = descs[di];
    if (d && d.id != null) descById[String(d.id)] = d;
  }
  var bboxContainMm = typeof MASONRY_DEF_BBOX_CONTAIN_MM !== 'undefined' ? MASONRY_DEF_BBOX_CONTAIN_MM : 2000;
  var px = Number(pt.x) || 0, py = Number(pt.y) || 0;
  for (var i = 0; i < walls.length; i++) {
    var w = walls[i];
    if (!w) continue;
    if (wallContains && wallContains(w, pt)) { out.push(w.wall_id || ('wall-' + (i + 1))); continue; }
    if (nearWall && nearWall(w, pt, 100)) { out.push(w.wall_id || ('wall-' + (i + 1))); continue; }
    var ids = w.entity_ids || [];
    for (var ei = 0; ei < ids.length; ei++) {
      var desc = descById[String(ids[ei])];
      if (!desc || !Array.isArray(desc.points) || desc.points.length < 4) continue;
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (var pi = 0; pi < desc.points.length; pi++) {
        var p = desc.points[pi];
        var qx = Number(p.x) || 0, qy = Number(p.y) || 0;
        if (qx < minX) minX = qx; if (qy < minY) minY = qy;
        if (qx > maxX) maxX = qx; if (qy > maxY) maxY = qy;
      }
      if (px >= minX - bboxContainMm && px <= maxX + bboxContainMm && py >= minY - bboxContainMm && py <= maxY + bboxContainMm) {
        out.push(w.wall_id || ('wall-' + (i + 1)));
        break;
      }
    }
  }
  return out;
}

/** 해치(96457 등) 좌우 연속 이어짐 원인 분석: 타겟 근처 해치 목록 + 각 벽의 쿼드가 해치 bbox와 겹치는지 */
function masonryDefDebugHatchTrimAtTarget(target, walls, hatchPolys, wallsContainingIds) {
  if (!target || !Array.isArray(walls) || !Array.isArray(hatchPolys)) return null;
  var tx = Number(target.x) || 0, ty = Number(target.y) || 0;
  var radiusMm = 3000;
  var margin = typeof MASONRY_DEF_HATCH_TRIM_MARGIN_MM === 'number' ? MASONRY_DEF_HATCH_TRIM_MARGIN_MM : 80;
  var pointInPoly = typeof frameDefPointInPolygon === 'function' ? frameDefPointInPolygon : null;
  var hatchesNear = [];
  for (var h = 0; h < hatchPolys.length; h++) {
    var hp = hatchPolys[h];
    if (!hp) continue;
    var bb = masonryDefHatchBbox(hp);
    if (!bb) continue;
    var cx = (bb.minX + bb.maxX) * 0.5, cy = (bb.minY + bb.maxY) * 0.5;
    var distToCenter = Math.hypot(tx - cx, ty - cy);
    var distToBbox = Math.max(bb.minX - tx, tx - bb.maxX, bb.minY - ty, ty - bb.maxY);
    if (distToCenter > radiusMm && distToBbox > 500) continue;
    var targetInside = !!(hp.points && hp.points.length >= 3 && pointInPoly && pointInPoly(target, hp.points));
    hatchesNear.push({
      id: hp.id != null ? hp.id : h,
      bbox: { minX: bb.minX, minY: bb.minY, maxX: bb.maxX, maxY: bb.maxY },
      bbox_with_margin: { minX: bb.minX - margin, minY: bb.minY - margin, maxX: bb.maxX + margin, maxY: bb.maxY + margin },
      target_inside: targetInside,
      dist_center_mm: Math.round(distToCenter)
    });
  }
  var wallSet = {};
  if (Array.isArray(wallsContainingIds)) for (var i = 0; i < wallsContainingIds.length; i++) wallSet[String(wallsContainingIds[i])] = true;
  var wallsDetail = [];
  for (var w = 0; w < walls.length; w++) {
    var wall = walls[w];
    if (!wall) continue;
    var wid = wall.wall_id || ('wall-' + (w + 1));
    if (!wallSet[wid]) continue;
    var cache = wall.__overlay_cache;
    var quads = (cache && Array.isArray(cache.quads)) ? cache.quads : [];
    var overlapping = [];
    for (var hi = 0; hi < hatchesNear.length; hi++) {
      var hbbox = hatchesNear[hi].bbox_with_margin;
      for (var q = 0; q < quads.length; q++) {
        var quad = quads[q];
        if (!quad || quad.length < 3) continue;
        var qMinX = Infinity, qMinY = Infinity, qMaxX = -Infinity, qMaxY = -Infinity;
        for (var vi = 0; vi < quad.length; vi++) {
          var v = quad[vi];
          var vx = Number(v.x) || 0, vy = Number(v.y) || 0;
          if (vx < qMinX) qMinX = vx; if (vy < qMinY) qMinY = vy;
          if (vx > qMaxX) qMaxX = vx; if (vy > qMaxY) qMaxY = vy;
        }
        if (masonryDefBboxOverlap({ minX: qMinX, minY: qMinY, maxX: qMaxX, maxY: qMaxY }, hbbox)) {
          overlapping.push({ hatch_id: hatchesNear[hi].id, quad_index: q, quad_bbox: { minX: qMinX, minY: qMinY, maxX: qMaxX, maxY: qMaxY } });
        }
      }
    }
    wallsDetail.push({
      wall_id: wid,
      source: String(wall.source || ''),
      quad_count: quads.length,
      quads_overlapping_hatch_bbox: overlapping
    });
  }
  return { hatches_near_target: hatchesNear, walls_trim_detail: wallsDetail };
}

function masonryDefPublishDebugReport() {
  if (typeof window === 'undefined') return null;
  var targets = masonryDefGetDebugTargets();
  if (!targets.length) {
    window.masonryDefLastDebug = null;
    if (typeof masonryDefRenderDebugPanel === 'function') masonryDefRenderDebugPanel();
    return null;
  }
  var st = masonryDefGetState();
  var descs = st.descs || [];
  var walls = st.walls || [];
  var hatchPolys = st.hatchPolys || [];
  var rawSegs = st.rawSegs || [];
  var descIds = descs.map(function(d) { return d.id; });
  var targetsList = targets.slice();
  var reports = [];
  for (var ti = 0; ti < targetsList.length; ti++) {
    var target = { x: Number(targetsList[ti].x) || 0, y: Number(targetsList[ti].y) || 0 };
    var descRows = [];
    if (typeof frameDefDebugDescriptorSummary === 'function') {
      descRows = descs.slice().map(function(desc) { return frameDefDebugDescriptorSummary(desc, target); }).filter(Boolean).sort(function(a, b) { return (a.dist || 0) - (b.dist || 0); }).slice(0, 8);
    }
    var wallRows = [];
    if (typeof frameDefDebugWallSummary === 'function') {
      wallRows = walls.slice().map(function(w) { return frameDefDebugWallSummary(w, target); }).filter(Boolean).sort(function(a, b) { return (a.dist || 0) - (b.dist || 0); }).slice(0, 8);
    }
    var inHatch = typeof frameDefPointInAnyHatch === 'function' && frameDefPointInAnyHatch(target, hatchPolys);
    var nearbyNotDescs = typeof masonryDefNearbyNotDescriptors === 'function' ? masonryDefNearbyNotDescriptors(target, 5000, descIds, 10) : [];
    var descsContaining = typeof masonryDefDescriptorsContainingPoint === 'function' ? masonryDefDescriptorsContainingPoint(target, descs) : [];
    var wallsContaining = typeof masonryDefWallsContainingPoint === 'function' ? masonryDefWallsContainingPoint(target, walls) : [];
    var single4vertexCheck = typeof masonryDefDebugSingleFourVertexCheck === 'function' ? masonryDefDebugSingleFourVertexCheck(target, descs, walls) : null;
    var entitiesNearTarget = typeof masonryDefDebugEntitiesNearTarget === 'function' ? masonryDefDebugEntitiesNearTarget(target, descIds, 2500) : [];
    var labelStr = String(targetsList[ti].label || ('target-' + (ti + 1)));
    var hatchTrimDiag = (labelStr.indexOf('연속이어짐') >= 0 && typeof masonryDefDebugHatchTrimAtTarget === 'function')
      ? masonryDefDebugHatchTrimAtTarget(target, walls, hatchPolys, wallsContaining) : null;
    reports.push({
      label: labelStr,
      target: { x: target.x, y: target.y },
      nearest_descriptors: descRows,
      nearest_walls: wallRows,
      descriptors_containing_target: descsContaining,
      walls_containing_target: wallsContaining,
      target_in_hatch: !!inHatch,
      hatch_polys_count: hatchPolys.length,
      nearby_not_descriptors: nearbyNotDescs,
      single_4vertex_check: single4vertexCheck,
      entities_near_target: entitiesNearTarget,
      hatch_trim_diagnostic: hatchTrimDiag
    });
  }
  var payload = {
    commit_id: st.lastCommitId,
    generated_at: new Date().toISOString(),
    targets: reports,
    walls_count: walls.length,
    descs_count: descs.length,
    wall_classes_aci3: (st.wallClassesAci3 || []).length,
    wall_classes_aci4: (st.wallClassesAci4 || []).length
  };
  window.masonryDefLastDebug = payload;
  try { if (typeof masonryDefRenderDebugPanel === 'function') masonryDefRenderDebugPanel(); } catch (_) {}
  return payload;
}

function masonryDefDebugEscape(v) {
  var s = String(v == null ? '' : v);
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function masonryDefRenderDebugPanel() {
  if (typeof document === 'undefined') return;
  var metaEl = document.getElementById('masonryDefDebugMeta');
  var bodyEl = document.getElementById('masonryDefDebugBody');
  if (!bodyEl) return;
  var payload = (typeof window !== 'undefined') ? window.masonryDefLastDebug : null;
  if (metaEl) metaEl.textContent = payload ? '타겟 ' + (payload.targets && payload.targets.length) + '개 기준 (골조와 동일 타겟)' : '조적 자동탐지 후 타겟 기준 디버그가 채워집니다.';
  bodyEl.innerHTML = '';
  if (!payload || !payload.targets || !payload.targets.length) return;
  var allHtml = [];
  for (var i = 0; i < payload.targets.length; i++) {
    var t = payload.targets[i];
    allHtml.push('<div style="font-size:0.8rem; font-weight:600; color:#24292f; margin-bottom:4px;">' + masonryDefDebugEscape(t.label) + '</div>');
    allHtml.push('<div style="font-size:0.75rem; color:#57606a; margin-bottom:6px;">좌표: ' + masonryDefDebugEscape((t.target && t.target.x) != null ? t.target.x : '') + ', ' + masonryDefDebugEscape((t.target && t.target.y) != null ? t.target.y : '') + (t.target_in_hatch ? ' (해치 내부)' : '') + '</div>');
    if (t.descriptors_containing_target && t.descriptors_containing_target.length) {
      allHtml.push('<div style="font-size:0.75rem; margin-bottom:4px;"><strong>타겟이 내부에 있는 디스크립터:</strong> ');
      for (var dc = 0; dc < t.descriptors_containing_target.length; dc++) {
        var dcItem = t.descriptors_containing_target[dc];
        if (dc) allHtml.push(', ');
        allHtml.push('id=' + masonryDefDebugEscape(dcItem.id) + ' ' + masonryDefDebugEscape(dcItem.layer || '') + (dcItem.scope_key ? ' scope=' + masonryDefDebugEscape(dcItem.scope_key) : ''));
      }
      allHtml.push('</div>');
    } else {
      allHtml.push('<div style="font-size:0.75rem; color:#57606a; margin-bottom:4px;">타겟이 내부에 있는 디스크립터: 없음</div>');
    }
    if (t.walls_containing_target && t.walls_containing_target.length) {
      allHtml.push('<div style="font-size:0.75rem; margin-bottom:6px;"><strong>타겟이 내부에 있는 벽:</strong> ' + masonryDefDebugEscape(t.walls_containing_target.join(', ')) + '</div>');
    } else {
      allHtml.push('<div style="font-size:0.75rem; color:#57606a; margin-bottom:6px;">타겟이 내부에 있는 벽: 없음</div>');
    }
    if (t.entities_near_target && t.entities_near_target.length) {
      allHtml.push('<div style="font-size:0.75rem; margin-bottom:8px; padding:6px; border:1px solid #d0d7de; border-radius:6px; background:#f0f6fc;"><strong>타겟 근처 A-WALL 폴리라인/라인 엔티티</strong><br/>');
      for (var ei = 0; ei < t.entities_near_target.length; ei++) {
        var ent = t.entities_near_target[ei];
        allHtml.push('id=' + masonryDefDebugEscape(ent.id) + ' type=' + masonryDefDebugEscape(ent.entity_type) + ' layer=' + masonryDefDebugEscape((ent.layer || '').substring(0, 40)) + ' points=' + (ent.point_count || 0) + ' dist=' + (ent.dist_to_target_mm || '') + 'mm ');
        if (ent.in_descriptors) allHtml.push('<span style="color:#1a7f37;">디스크립터 포함</span>');
        else if (ent.why_not && ent.why_not.reason) allHtml.push('<span style="color:#cf2222;">미포함: ' + masonryDefDebugEscape(ent.why_not.reason) + '</span>');
        allHtml.push('<br/>');
      }
      allHtml.push('</div>');
    }
    if (t.single_4vertex_check) {
      var s4 = t.single_4vertex_check;
      var bg = (s4.treated_as_single_four_vertex && s4.in_wall_list) ? '#dafbe0' : ((s4.single_four_vertex_eligible && !s4.in_wall_list) ? '#fff8c5' : '#f6f8fa');
      allHtml.push('<div style="font-size:0.75rem; margin-bottom:8px; padding:8px; border-radius:6px; border:1px solid #d0d7de; background:' + bg + ';"><strong>단일 5꼭지점(닫힌 사각형) 해당 여부</strong><br/>');
      allHtml.push(masonryDefDebugEscape(s4.summary || '') + '<br/>');
      if (s4.nearest_descriptor) allHtml.push('근접 디스크립터: id=' + masonryDefDebugEscape(s4.nearest_descriptor.id) + ' layer=' + masonryDefDebugEscape(s4.nearest_descriptor.layer || '') + '<br/>');
      allHtml.push('꼭지점 수=' + masonryDefDebugEscape(s4.point_count) + ', 단일5꼭지점 조건=' + (s4.single_four_vertex_eligible ? '예' : '아니오') + ', 벽체목록 포함=' + (s4.in_wall_list ? '예' : '아니오'));
      if (s4.wall_ids_with_descriptor && s4.wall_ids_with_descriptor.length) allHtml.push(' → ' + masonryDefDebugEscape(s4.wall_ids_with_descriptor.join(', ')));
      allHtml.push(', 장변=길이/단변=폭 처리=' + (s4.treated_as_single_four_vertex ? '예' : '아니오') + '</div>');
    }
    if (t.hatch_trim_diagnostic) {
      var htd = t.hatch_trim_diagnostic;
      allHtml.push('<details open style="border:1px solid #0969da; border-radius:6px; background:#ddf4ff; margin-bottom:8px;"><summary style="padding:6px 8px; cursor:pointer; font-size:0.78rem;"><strong>해치 좌우 연속이어짐 분석 (해치·트림 진단)</strong></summary><div style="padding:6px 8px; border-top:1px solid #0969da; font-size:0.72rem;">');
      if (htd.hatches_near_target && htd.hatches_near_target.length) {
        allHtml.push('<div style="margin-bottom:6px;"><strong>타겟 근처 해치:</strong> ');
        for (var hi = 0; hi < htd.hatches_near_target.length; hi++) {
          var h = htd.hatches_near_target[hi];
          allHtml.push(' id=' + masonryDefDebugEscape(h.id) + ' bbox=[' + (h.bbox && h.bbox.minX != null ? (Math.round(h.bbox.minX) + ',' + Math.round(h.bbox.minY) + '~' + Math.round(h.bbox.maxX) + ',' + Math.round(h.bbox.maxY)) : '') + '] target_inside=' + (h.target_inside ? 'Y' : 'N') + ' dist_center=' + (h.dist_center_mm || '') + 'mm');
        }
        allHtml.push('</div>');
      } else {
        allHtml.push('<div style="color:#cf2222;">타겟 근처 해치 없음 → 트림에 사용된 해치 bbox가 없을 수 있음 (삽입점 보강 확인)</div>');
      }
      if (htd.walls_trim_detail && htd.walls_trim_detail.length) {
        allHtml.push('<div><strong>타겟 포함 벽별 쿼드·해치 bbox 겹침:</strong></div>');
        for (var wi = 0; wi < htd.walls_trim_detail.length; wi++) {
          var wd = htd.walls_trim_detail[wi];
          var overlap = (wd.quads_overlapping_hatch_bbox && wd.quads_overlapping_hatch_bbox.length) ? wd.quads_overlapping_hatch_bbox : [];
          var warn = overlap.length ? ' <span style="color:#cf2222;">→ ' + overlap.length + '개 쿼드가 해치 bbox와 겹침(트림 미적용/연속이어짐 원인)</span>' : '';
          allHtml.push('<div style="margin-left:8px;">' + masonryDefDebugEscape(wd.wall_id) + ' source=' + masonryDefDebugEscape(wd.source) + ' quads=' + (wd.quad_count || 0) + warn + '</div>');
        }
      }
      allHtml.push('</div></details>');
    }
    if (t.nearest_descriptors && t.nearest_descriptors.length) {
      allHtml.push('<details style="border:1px solid #d0d7de; border-radius:6px; background:#fff;"><summary style="padding:6px 8px; cursor:pointer; font-size:0.78rem;">가까운 descriptor (' + t.nearest_descriptors.length + ')</summary><div style="padding:6px 8px; border-top:1px solid #d0d7de; font-size:0.72rem;">');
      for (var d = 0; d < t.nearest_descriptors.length; d++) {
        var r = t.nearest_descriptors[d];
        allHtml.push('<div>id=' + masonryDefDebugEscape(r.id) + ' dist=' + masonryDefDebugEscape(r.dist) + ' type=' + masonryDefDebugEscape(r.type) + ' len=' + masonryDefDebugEscape(r.len) + ' scope=' + masonryDefDebugEscape(r.scope_key) + '</div>');
      }
      allHtml.push('</div></details>');
    }
    if (t.nearest_walls && t.nearest_walls.length) {
      allHtml.push('<details style="border:1px solid #d0d7de; border-radius:6px; background:#fff;"><summary style="padding:6px 8px; cursor:pointer; font-size:0.78rem;">가까운 벽 (' + t.nearest_walls.length + ')</summary><div style="padding:6px 8px; border-top:1px solid #d0d7de; font-size:0.72rem;">');
      for (var w = 0; w < t.nearest_walls.length; w++) {
        var r = t.nearest_walls[w];
        allHtml.push('<div>' + masonryDefDebugEscape(r.wall_id) + ' dist=' + masonryDefDebugEscape(r.dist) + ' thickness=' + masonryDefDebugEscape(r.thickness_mm) + '</div>');
      }
      allHtml.push('</div></details>');
    }
    if (t.nearby_not_descriptors && t.nearby_not_descriptors.length) {
      allHtml.push('<details open style="border:1px solid #d0d7de; border-radius:6px; background:#f6f8fa;"><summary style="padding:6px 8px; cursor:pointer; font-size:0.78rem;">근처에서 조적 디스크립터로 안 잡힌 객체 (' + t.nearby_not_descriptors.length + ')</summary><div style="padding:6px 8px; border-top:1px solid #d0d7de; font-size:0.72rem;">');
      for (var n = 0; n < t.nearby_not_descriptors.length; n++) {
        var nr = t.nearby_not_descriptors[n];
        var why = nr.why_not || {};
        var line = 'id=' + masonryDefDebugEscape(nr.id) + ' type=' + masonryDefDebugEscape(nr.type) + ' layer=' + masonryDefDebugEscape(nr.layer) + (nr.block_insert_id != null ? ' block_insert_id=' + nr.block_insert_id : '') + ' dist=' + masonryDefDebugEscape(nr.dist) + 'mm';
        allHtml.push('<div style="margin-bottom:4px;">' + line + '</div>');
        allHtml.push('<div style="margin-left:8px; color:#cf2222;">→ ' + masonryDefDebugEscape(why.reason || '') + (why.resolved_aci != null ? ' (resolved_aci=' + why.resolved_aci + ')' : '') + '</div>');
      }
      allHtml.push('</div></details>');
    }
  }
  bodyEl.innerHTML = allHtml.join('');
}

function bindMasonryDefPanelEvents() {
  var panel = document.getElementById('featurePanel-masonry-object-define');
  if (!panel || panel.dataset.masonryDefPanelBound === '1') return;
  panel.dataset.masonryDefPanelBound = '1';
  var applyBtn = document.getElementById('masonryDefApplyBtn');
  var selAllBtn = document.getElementById('masonryDefSelectAllBtn');
  var selAci3Btn = document.getElementById('masonryDefSelectAci3Btn');
  var selAci4Btn = document.getElementById('masonryDefSelectAci4Btn');
  var definedSel = document.getElementById('masonryDefDefinedList');
  var definedBtn = document.getElementById('masonryDefDefinedSelectBtn');
  var overlayChk = document.getElementById('masonryDefPreviewOverlayChk');
  var dimOthersChk = document.getElementById('masonryDefDimOthersChk');
  var gapChk = document.getElementById('masonryDefShowGapIssuesChk');
  var includeAci4Chk = document.getElementById('masonryDefIncludeAci4Chk');
  var debugDumpBtn = document.getElementById('masonryDefDebugDumpBtn');
  var debugClearBtn = document.getElementById('masonryDefDebugClearBtn');
  var debugPasteEl = document.getElementById('masonryDefDebugPaste');
  var debugCopyBtn = document.getElementById('masonryDefDebugCopyBtn');
  if (debugCopyBtn && !debugCopyBtn.dataset.masonryDefBound) {
    debugCopyBtn.dataset.masonryDefBound = '1';
    debugCopyBtn.addEventListener('click', function() {
      var payload = (typeof window !== 'undefined') ? window.masonryDefLastDebug : null;
      var txt = payload ? JSON.stringify(payload, null, 2) : '';
      if (!txt) { if (typeof showMsg === 'function') showMsg('msg', '복사할 디버그 결과가 없습니다. 조적 자동탐지를 먼저 실행하세요.', 'info'); return; }
      if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(txt).then(function() { if (typeof showMsg === 'function') showMsg('msg', '디버그 결과를 복사했습니다.', 'success'); }).catch(function() { if (typeof showMsg === 'function') showMsg('msg', '복사에 실패했습니다.', 'error'); });
      } else { if (typeof showMsg === 'function') showMsg('msg', '이 환경에서는 자동 복사를 지원하지 않습니다.', 'info'); }
    });
  }
  if (debugDumpBtn && debugPasteEl) debugDumpBtn.addEventListener('click', function() { debugPasteEl.value = masonryDefDebugDump(); });
  if (debugClearBtn && debugPasteEl) debugClearBtn.addEventListener('click', function() { debugPasteEl.value = ''; });
  if (selAllBtn) selAllBtn.addEventListener('click', function() { masonrySelectScope('all', false); });
  if (selAci3Btn) selAci3Btn.addEventListener('click', function() { masonrySelectScope('aci3', false); });
  if (selAci4Btn) selAci4Btn.addEventListener('click', function() { masonrySelectScope('aci4', false); });
  if (applyBtn) applyBtn.addEventListener('click', function() { masonryApplySelection(); });
  if (definedSel) definedSel.addEventListener('change', function() {
    var gid = String(definedSel.value || '').trim();
    if (gid) masonrySelectDefinedGroup(gid, true);
  });
  if (definedBtn) definedBtn.addEventListener('click', function() {
    var gid = String((definedSel && definedSel.value) || '').trim();
    if (!gid) { if (typeof showMsg === 'function') showMsg('msg', '선택된 적용 묶음이 없습니다.', 'info'); return; }
    masonrySelectDefinedGroup(gid, false);
  });
  if (overlayChk) {
    overlayChk.checked = masonryDefGetState().previewVisible !== false;
    overlayChk.addEventListener('change', function() { masonryDefGetState().previewVisible = !!overlayChk.checked; if (typeof draw === 'function') draw(); });
  }
  if (dimOthersChk) {
    dimOthersChk.checked = masonryDefGetState().dimOthers === true;
    dimOthersChk.addEventListener('change', function() { masonryDefGetState().dimOthers = !!dimOthersChk.checked; if (typeof draw === 'function') draw(); });
  }
  if (gapChk) {
    gapChk.checked = masonryDefGetState().showGapIssues !== false;
    gapChk.addEventListener('change', function() { masonryDefGetState().showGapIssues = !!gapChk.checked; if (typeof draw === 'function') draw(); });
  }
  if (includeAci4Chk) {
    includeAci4Chk.checked = masonryDefGetState().includeAci4 === true;
    includeAci4Chk.addEventListener('change', function() { masonryDefGetState().includeAci4 = !!includeAci4Chk.checked; });
  }
  function bindWallClassListClick(containerId) {
    var el = document.getElementById(containerId);
    if (!el || el.dataset.masonryDefBound === '1') return;
    el.dataset.masonryDefBound = '1';
    el.addEventListener('click', function(e) {
      var row = e.target && e.target.closest ? e.target.closest('[data-masonry-class]') : null;
      if (!row) return;
      var key = String(row.getAttribute('data-masonry-class') || '').trim();
      if (key) masonrySelectClass(key, false);
    });
  }
  bindWallClassListClick('masonryDefWallClassListAci3');
  bindWallClassListClick('masonryDefWallClassListAci4');
  masonryRefreshPanelState();
}
