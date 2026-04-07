/* door-object-define logic extracted from workspace.html */
var DOOR_DEF_ATTR_KEYS = ['door_definition_label', 'door_group_id', 'door_group_no', 'door_group_role', 'door_leaf_type', 'door_defined_width_mm'];
var DOOR_DEF_MATCH_TOL_MM = 10.0;
var DOOR_DEF_MATCH_RATIO = 0.7;
var DOOR_DEF_MAX_TOL_MM = 45.0;
var DOOR_DEF_GRID_CELL_MM = 140.0;
var DOOR_DEF_MAX_ARC_ANCHORS = 140;
var DOOR_DEF_MAX_GENERIC_ANCHORS = 260;
var DOOR_DEF_MAX_ANGLE_HYP_ARC = 8;
var DOOR_DEF_MAX_ANGLE_HYP_GENERIC = 12;
var DOOR_DEF_MIN_ARC_WIDTH_MM_DEFAULT = 500;
var DOOR_DEF_MIN_ARC_WIDTH_MM_MIN = 100;
var DOOR_DEF_MIN_ARC_WIDTH_MM_MAX = 6000;
var DOOR_DEF_MAX_ARC_WIDTH_MM_DEFAULT = 5000;
var DOOR_DEF_MAX_ARC_WIDTH_MM_MIN = 100;
var DOOR_DEF_MAX_ARC_WIDTH_MM_MAX = 6000;
var DOOR_DEF_INCLUDE_EXTENT_DEFAULT = 100;
var DOOR_DEF_INCLUDE_EXTENT_MIN = 0;
var DOOR_DEF_INCLUDE_EXTENT_MAX = 100;
var DOOR_DEF_ARC_NEAR_GAUGE_DEFAULT = 95;
var DOOR_DEF_ARC_NEAR_GAUGE_MIN = 0;
var DOOR_DEF_ARC_NEAR_GAUGE_MAX = 140;
var DOOR_DEF_MIN_LINEAR_LEN_MM = 70;
function doorDefPrimaryMetric(item) {
  if (!item) return 0;
  var r = item.radius || 0;
  if (r > 0) return r;
  var len = item.length || 0;
  if (len > 0) return len;
  var area = item.area || 0;
  return area > 0 ? Math.sqrt(area) : 0;
}
function doorDefMetricDistance(a, b) {
  return Math.abs(doorDefPrimaryMetric(a) - doorDefPrimaryMetric(b));
}
function doorDefBuildTypeCounts(items) {
  var out = {};
  for (var i = 0; i < (items || []).length; i++) {
    var t = items[i] && items[i].type ? items[i].type : '?';
    out[t] = (out[t] || 0) + 1;
  }
  return out;
}
function doorDefGridCoord(v, cell) {
  var c = cell > 0 ? cell : DOOR_DEF_GRID_CELL_MM;
  return Math.floor((Number(v) || 0) / c);
}
function doorDefGridKey(ix, iy) {
  return String(ix) + '|' + String(iy);
}
function doorDefBuildTypeGrid(items, cell) {
  var c = cell > 0 ? cell : DOOR_DEF_GRID_CELL_MM;
  var buckets = {};
  for (var i = 0; i < (items || []).length; i++) {
    var d = items[i];
    if (!d || !d.centroid) continue;
    var ix = doorDefGridCoord(d.centroid.x, c);
    var iy = doorDefGridCoord(d.centroid.y, c);
    var key = doorDefGridKey(ix, iy);
    if (!buckets[key]) buckets[key] = [];
    buckets[key].push(d);
  }
  return { cell: c, buckets: buckets };
}
function doorDefSpatialPool(idx, type, center, radius) {
  if (!idx || !type) return [];
  var poolAll = idx.byType && idx.byType[type] ? idx.byType[type] : [];
  if (!poolAll.length) return [];
  var cx = center && isFinite(center.x) ? Number(center.x) : 0;
  var cy = center && isFinite(center.y) ? Number(center.y) : 0;
  var r = radius > 0 ? radius : DOOR_DEF_MATCH_TOL_MM;
  var grid = idx.byTypeGrid && idx.byTypeGrid[type] ? idx.byTypeGrid[type] : null;
  if (!grid || !grid.buckets) return poolAll;
  var cell = grid.cell > 0 ? grid.cell : DOOR_DEF_GRID_CELL_MM;
  var minX = doorDefGridCoord(cx - r, cell);
  var maxX = doorDefGridCoord(cx + r, cell);
  var minY = doorDefGridCoord(cy - r, cell);
  var maxY = doorDefGridCoord(cy + r, cell);
  var out = [];
  for (var ix = minX; ix <= maxX; ix++) {
    for (var iy = minY; iy <= maxY; iy++) {
      var key = doorDefGridKey(ix, iy);
      var cellItems = grid.buckets[key];
      if (!cellItems || !cellItems.length) continue;
      for (var j = 0; j < cellItems.length; j++) out.push(cellItems[j]);
    }
  }
  return out;
}
function doorDefArcAnchorNeighborhoodScore(anchorDesc, signature, idx, tol) {
  if (!anchorDesc || !signature || !idx) return 0;
  var rep = signature.representative_member;
  if (!rep || rep.type !== 'ARC') return 0;
  var typeCounts = signature.type_counts || {};
  var expArc = Math.max(1, typeCounts.ARC || 1);
  var expLinear = Math.max(1, (typeCounts.LINE || 0) + (typeCounts.LWPOLYLINE || 0) + (typeCounts.POLYLINE || 0));
  var radius = Math.max((signature.range && signature.range.diag ? signature.range.diag * 0.9 : 0), tol * 8, 120);
  var arcPool = doorDefSpatialPool(idx, 'ARC', anchorDesc.centroid, radius);
  var linePool = doorDefSpatialPool(idx, 'LINE', anchorDesc.centroid, radius);
  var lwPool = doorDefSpatialPool(idx, 'LWPOLYLINE', anchorDesc.centroid, radius);
  var plPool = doorDefSpatialPool(idx, 'POLYLINE', anchorDesc.centroid, radius);
  var arcCnt = 0;
  for (var a = 0; a < arcPool.length; a++) {
    var ad = arcPool[a];
    if (!ad || ad.id === anchorDesc.id) continue;
    var da = pointDist(anchorDesc.centroid, ad.centroid);
    if (isFinite(da) && da <= radius) arcCnt += 1;
  }
  var linCnt = 0;
  function countNear(pool) {
    for (var i = 0; i < pool.length; i++) {
      var d = pool[i];
      if (!d || d.id === anchorDesc.id) continue;
      var dl = pointDist(anchorDesc.centroid, d.centroid);
      if (isFinite(dl) && dl <= radius) linCnt += 1;
    }
  }
  countNear(linePool);
  countNear(lwPool);
  countNear(plPool);
  var arcCov = Math.min(1, arcCnt / Math.max(1, expArc - 1));
  var lineCov = Math.min(1, linCnt / expLinear);
  return (arcCov * 0.6) + (lineCov * 0.4);
}
function doorDefBuildRangeFromMembers(members) {
  if (!members || members.length === 0) {
    return {
      bbox: { minX: 0, minY: 0, maxX: 0, maxY: 0, w: 0, h: 0 },
      diag: 0,
      aspect: 1,
      radial: { min: 0, max: 0, avg: 0, p80: 0 }
    };
  }
  var relPts = [];
  var radial = [];
  var sum = 0;
  for (var i = 0; i < members.length; i++) {
    var rel = members[i].rel || { x: 0, y: 0 };
    relPts.push({ x: rel.x, y: rel.y });
    var rr = Math.hypot(rel.x, rel.y);
    radial.push(rr);
    sum += rr;
  }
  radial.sort(function(a, b) { return a - b; });
  var bbox = pointListBBox(relPts, { x: 0, y: 0 });
  var diag = Math.hypot(bbox.w || 0, bbox.h || 0);
  var p80Idx = Math.max(0, Math.floor((radial.length - 1) * 0.8));
  return {
    bbox: bbox,
    diag: diag,
    aspect: (bbox.h || 0) > 1e-9 ? ((bbox.w || 0) / (bbox.h || 0)) : 1,
    radial: {
      min: radial.length ? radial[0] : 0,
      max: radial.length ? radial[radial.length - 1] : 0,
      avg: radial.length ? (sum / radial.length) : 0,
      p80: radial.length ? radial[p80Idx] : 0
    }
  };
}
function doorDefAdaptiveTol(signature, baseTol) {
  var b = (baseTol > 0) ? baseTol : DOOR_DEF_MATCH_TOL_MM;
  var diag = signature && signature.range ? (signature.range.diag || 0) : 0;
  if (!(diag > 0)) return b;
  return Math.max(b, Math.min(DOOR_DEF_MAX_TOL_MM, diag * 0.03));
}
function doorDefPushAngleHypothesis(list, angle, weight) {
  if (!list) return;
  var a = doorDefNormalizeRad(angle || 0);
  var w = isFinite(weight) ? Number(weight) : 0;
  var mergeTol = Math.PI / 60; // 3deg
  for (var i = 0; i < list.length; i++) {
    if (doorDefAngleDiff(list[i].angle, a) <= mergeTol) {
      if (w < list[i].weight) {
        list[i].angle = a;
        list[i].weight = w;
      }
      return;
    }
  }
  list.push({ angle: a, weight: w });
}
function doorDefFindMemberById(signature, id) {
  var key = String(id);
  if (signature && signature.member_by_id && signature.member_by_id[key]) return signature.member_by_id[key];
  var members = signature && signature.members ? signature.members : [];
  for (var i = 0; i < members.length; i++) {
    if (String(members[i].id) === key) return members[i];
  }
  return null;
}
function doorDefAnchorContextScore(anchorDesc, signature, idx, tol) {
  if (!anchorDesc || !signature || !idx) return 0;
  var typeCounts = signature.type_counts || {};
  var coreTypes = signature.core_types || Object.keys(typeCounts);
  if (!coreTypes.length) return 0;
  var radius = Math.max((signature.range && signature.range.diag) || 0, tol * 4) + tol;
  if (!(radius > 0)) radius = tol * 6;
  var checked = 0;
  var score = 0;
  for (var i = 0; i < coreTypes.length && checked < 3; i++) {
    var t = coreTypes[i];
    var need = Math.max(1, Math.floor((typeCounts[t] || 1) * 0.6));
    var pool = doorDefSpatialPool(idx, t, anchorDesc.centroid, radius);
    if (!pool.length) continue;
    checked += 1;
    var cnt = 0;
    for (var p = 0; p < pool.length; p++) {
      var cand = pool[p];
      if (!cand || cand.id === anchorDesc.id) continue;
      var d = pointDist(anchorDesc.centroid, cand.centroid);
      if (isFinite(d) && d <= radius) {
        cnt += 1;
        if (cnt >= need) break;
      }
    }
    score += Math.min(1, cnt / need);
  }
  if (checked <= 0) return 0;
  var base = score / checked;
  var arcBias = doorDefArcAnchorNeighborhoodScore(anchorDesc, signature, idx, tol);
  if (signature && signature.representative_member && signature.representative_member.type === 'ARC') {
    return (base * 0.75) + (arcBias * 0.25);
  }
  return base;
}
function doorDefEstimateAngles(signature, anchorDesc, mirrored, tol, idx, seedSet) {
  var out = [];
  if (!signature || !anchorDesc) return out;
  var rep = signature.representative_member;
  if (!rep) return out;
  if (rep.orientation != null && anchorDesc.orientation != null) {
    var base = mirrored ? (anchorDesc.orientation + rep.orientation) : (anchorDesc.orientation - rep.orientation);
    doorDefPushAngleHypothesis(out, base, 0.1);
    var axisType = rep.type === 'LINE' || rep.type === 'LWPOLYLINE' || rep.type === 'POLYLINE';
    if (axisType) doorDefPushAngleHypothesis(out, base + Math.PI, 0.2);
  }
  var supportIds = signature.support_member_ids || [];
  var supportTol = Math.max(tol * 2.5, 18);
  var maxSupport = rep.type === 'ARC' ? 4 : 6;
  for (var s = 0; s < supportIds.length && s < maxSupport; s++) {
    var seedSupport = doorDefFindMemberById(signature, supportIds[s]);
    if (!seedSupport || seedSupport.id === rep.id) continue;
    var baseVec = seedSupport.rel_to_rep || {
      x: seedSupport.centroid.x - rep.centroid.x,
      y: seedSupport.centroid.y - rep.centroid.y
    };
    var baseLen = Math.hypot(baseVec.x, baseVec.y);
    if (!(baseLen > tol * 1.2)) continue;
    var refVec = mirrored ? { x: -baseVec.x, y: baseVec.y } : { x: baseVec.x, y: baseVec.y };
    var refDir = Math.atan2(refVec.y, refVec.x);
    var supportRadius = Math.max((signature.range && signature.range.diag) || 0, baseLen + supportTol) + tol;
    var pool = doorDefSpatialPool(idx, seedSupport.type, anchorDesc.centroid, supportRadius);
    var pushed = 0;
    var perSupportLimit = rep.type === 'ARC' ? 5 : 8;
    for (var p = 0; p < pool.length; p++) {
      var cand = pool[p];
      if (!cand || cand.id === anchorDesc.id || seedSet[cand.id]) continue;
      if (!doorDefMetricCompatible(seedSupport, cand, tol, { relativeTol: 0.24 })) continue;
      var candVec = { x: cand.centroid.x - anchorDesc.centroid.x, y: cand.centroid.y - anchorDesc.centroid.y };
      var candLen = Math.hypot(candVec.x, candVec.y);
      if (!isFinite(candLen) || Math.abs(candLen - baseLen) > supportTol) continue;
      var candDir = Math.atan2(candVec.y, candVec.x);
      var angle = candDir - refDir;
      var w = 0.7 + (Math.abs(candLen - baseLen) / Math.max(1, tol));
      doorDefPushAngleHypothesis(out, angle, w);
      pushed += 1;
      if (pushed >= perSupportLimit) break;
    }
  }
  var fallbackStep = rep.type === 'ARC' ? (Math.PI / 4) : (Math.PI / 6);
  var fallbackCount = rep.type === 'ARC' ? 8 : 12;
  if (out.length < 4) {
    for (var k = 0; k < fallbackCount; k++) {
      doorDefPushAngleHypothesis(out, fallbackStep * k, 6 + (k * 0.01));
    }
  }
  out.sort(function(a, b) { return a.weight - b.weight; });
  var maxHyp = rep.type === 'ARC' ? DOOR_DEF_MAX_ANGLE_HYP_ARC : DOOR_DEF_MAX_ANGLE_HYP_GENERIC;
  if (out.length > maxHyp) out = out.slice(0, maxHyp);
  return out;
}
function doorDefInverseTransformVec(v, angle, mirrored) {
  var back = doorDefRotateVec(v, -(angle || 0));
  return mirrored ? { x: -back.x, y: back.y } : back;
}
function doorDefGroupShapePenalty(signature, matchedPairs, center, angle, mirrored, tol) {
  if (!signature || !signature.range || !matchedPairs || matchedPairs.length < 2) return 0;
  var pts = [];
  var radial = [];
  for (var i = 0; i < matchedPairs.length; i++) {
    var cand = matchedPairs[i].cand;
    var rel = { x: cand.centroid.x - center.x, y: cand.centroid.y - center.y };
    var inv = doorDefInverseTransformVec(rel, angle, mirrored);
    pts.push(inv);
    radial.push(Math.hypot(inv.x, inv.y));
  }
  var bbox = pointListBBox(pts, { x: 0, y: 0 });
  var base = signature.range.bbox || { w: 0, h: 0 };
  var baseDiag = signature.range.diag || 0;
  var diag = Math.hypot(bbox.w || 0, bbox.h || 0);
  var wDiff = Math.abs((bbox.w || 0) - (base.w || 0));
  var hDiff = Math.abs((bbox.h || 0) - (base.h || 0));
  var diagDiff = Math.abs(diag - baseDiag);
  var hardTol = Math.max((tol || DOOR_DEF_MATCH_TOL_MM) * 2.5, baseDiag * 0.45);
  if (Math.max(wDiff, hDiff) > hardTol && diagDiff > hardTol) return Infinity;
  var sumR = 0;
  for (var r = 0; r < radial.length; r++) sumR += radial[r];
  var avgR = radial.length ? (sumR / radial.length) : 0;
  var baseAvgR = signature.range.radial ? (signature.range.radial.avg || 0) : 0;
  var denom = Math.max(baseDiag, tol || DOOR_DEF_MATCH_TOL_MM, 1);
  var radialPenalty = Math.abs(avgR - baseAvgR) / Math.max(baseAvgR, denom, 1);
  return ((wDiff + hDiff + diagDiff) / denom) * 6 + radialPenalty * 2;
}
function doorDefNormalizeLabel(v) {
  var s = String(v == null ? '' : v).trim();
  return s || '개폐문';
}
function doorDefPadNo(n) {
  var x = parseInt(n, 10);
  if (!(x > 0)) x = 1;
  if (x > 999) return String(x);
  return String(x).padStart(3, '0');
}
function doorDefCurrentCommitId() {
  var v = '';
  if (typeof getActiveViewCommitId === 'function') v = getActiveViewCommitId();
  if (!v && viewCommitSelect) v = viewCommitSelect.value;
  return String(v || '').trim();
}
function doorDefNormalizeRad(a) {
  var x = Number(a);
  if (!isFinite(x)) return 0;
  while (x > Math.PI) x -= Math.PI * 2;
  while (x < -Math.PI) x += Math.PI * 2;
  return x;
}
function doorDefAngleDiff(a, b) {
  return Math.abs(doorDefNormalizeRad((a || 0) - (b || 0)));
}
function doorDefAxisAngleDiff(a, b) {
  var d = doorDefAngleDiff(a, b);
  var d180 = Math.abs(Math.PI - d);
  return Math.min(d, d180);
}
function doorDefNormalizeRad2Pi(a) {
  var x = Number(a);
  if (!isFinite(x)) return 0;
  while (x < 0) x += Math.PI * 2;
  while (x >= Math.PI * 2) x -= Math.PI * 2;
  return x;
}
function doorDefNormalizeDeg360(a) {
  var x = Number(a);
  if (!isFinite(x)) return 0;
  while (x < 0) x += 360;
  while (x >= 360) x -= 360;
  return x;
}
function doorDefAngleSpanCCW(fromA, toA) {
  var a = doorDefNormalizeRad2Pi(fromA);
  var b = doorDefNormalizeRad2Pi(toA);
  return (b - a + Math.PI * 2) % (Math.PI * 2);
}
function doorDefBuildArcSweepInfo(arcDesc) {
  var a = arcDesc || null;
  if (!a) return null;
  var center = a.arc_center || a.centroid;
  var start = a.arc_start || null;
  var end = a.arc_end || null;
  if (!center || !start || !end) return null;
  var sa = doorDefNormalizeRad2Pi(Math.atan2((start.y || 0) - (center.y || 0), (start.x || 0) - (center.x || 0)));
  var ea = doorDefNormalizeRad2Pi(Math.atan2((end.y || 0) - (center.y || 0), (end.x || 0) - (center.x || 0)));
  var ma = null;
  if (a.arc_mid) {
    ma = doorDefNormalizeRad2Pi(Math.atan2((a.arc_mid.y || 0) - (center.y || 0), (a.arc_mid.x || 0) - (center.x || 0)));
  }
  var ccwSpan = doorDefAngleSpanCCW(sa, ea);
  var cwSpan = doorDefAngleSpanCCW(ea, sa);
  var ccw = true;
  if (ma != null) {
    ccw = doorDefAngleSpanCCW(sa, ma) <= (ccwSpan + 1e-6);
  } else if (a.sweep != null && isFinite(a.sweep)) {
    var sw = Math.abs(Number(a.sweep) || 0);
    if (sw > 0 && sw < 359.9) {
      ccw = Math.abs(ccwSpan - (sw * Math.PI / 180)) <= Math.abs(cwSpan - (sw * Math.PI / 180));
    }
  } else {
    ccw = ccwSpan <= cwSpan;
  }
  var span = ccw ? ccwSpan : cwSpan;
  if (span > Math.PI) {
    ccw = !ccw;
    span = (Math.PI * 2) - span;
  }
  if (!(span > 0)) return null;
  return {
    center: { x: Number(center.x) || 0, y: Number(center.y) || 0 },
    radius: Number(a.radius) || 0,
    start: sa,
    end: ea,
    ccw: !!ccw,
    span: span
  };
}
function doorDefPointInArcSweep(pt, arcInfo, opts) {
  if (!pt || !arcInfo || !arcInfo.center) return false;
  var dx = (Number(pt.x) || 0) - arcInfo.center.x;
  var dy = (Number(pt.y) || 0) - arcInfo.center.y;
  var dist = Math.hypot(dx, dy);
  if (!isFinite(dist)) return false;
  var rad = Number(arcInfo.radius) || 0;
  var tolOut = (opts && opts.radialTolOut > 0) ? opts.radialTolOut : Math.max(16, rad * 0.08);
  if (rad > 0 && dist > (rad + tolOut)) return false;
  var ang = doorDefNormalizeRad2Pi(Math.atan2(dy, dx));
  var angTol = (opts && opts.angleTolRad > 0) ? opts.angleTolRad : (Math.PI / 18); // 10deg
  if (arcInfo.ccw) {
    var rel = doorDefAngleSpanCCW(arcInfo.start, ang);
    return rel <= (arcInfo.span + angTol);
  }
  var relCw = doorDefAngleSpanCCW(arcInfo.end, ang);
  return relCw <= (arcInfo.span + angTol);
}
function doorDefRotateVec(v, angle) {
  var c = Math.cos(angle || 0);
  var s = Math.sin(angle || 0);
  return { x: v.x * c - v.y * s, y: v.x * s + v.y * c };
}
function doorDefTransformVec(v, angle, mirrored) {
  var base = mirrored ? { x: -v.x, y: v.y } : { x: v.x, y: v.y };
  return doorDefRotateVec(base, angle || 0);
}
function doorDefSweepFromProps(props, type) {
  if ((type || '') !== 'ARC') return null;
  var sa = parseFloatOrNull(props && props.start_angle);
  var ea = parseFloatOrNull(props && props.end_angle);
  if (sa == null || ea == null) return null;
  var d = ((ea - sa) % 360 + 360) % 360;
  if (d === 0) d = 360;
  return d;
}
function doorDefComputeRadius(ent, points, centroid) {
  var props = ent && ent.props ? ent.props : {};
  var r = parseFloatOrNull(props.radius);
  if (r != null && isFinite(r) && r > 0) return r;
  var type = ((ent && ent.entity_type) || '').toUpperCase();
  if ((type === 'CIRCLE' || type === 'ARC') && centroid && points && points.length > 0) {
    var sum = 0;
    for (var i = 0; i < points.length; i++) sum += pointDist(points[i], centroid);
    var avg = sum / points.length;
    return isFinite(avg) && avg > 0 ? avg : 0;
  }
  return 0;
}
function doorDefComputeArea(ent, points, type) {
  if (!points || points.length < 3) return 0;
  if (type === 'HATCH' || type === 'WIPEOUT' || ent.fill) return pointListArea(points);
  var first = points[0], last = points[points.length - 1];
  if (first && last && pointDist(first, last) < 1e-6) return pointListArea(points);
  return 0;
}
function doorDefComputeLength(ent, points, type, radius, sweepDeg) {
  if (type === 'CIRCLE' && radius > 0) return Math.PI * 2 * radius;
  if (type === 'ARC' && radius > 0 && sweepDeg != null) return (Math.PI * 2 * radius) * (sweepDeg / 360.0);
  return pointListLength(points);
}
function doorDefComputeOrientation(ent, points, centroid) {
  var type = ((ent && ent.entity_type) || '').toUpperCase();
  if ((type === 'TEXT' || type === 'MTEXT' || type === 'ATTRIB') && ent) {
    var rot = parseFloatOrNull(ent.rotation);
    if (rot == null) rot = parseFloatOrNull(ent.props && ent.props.rotation);
    if (rot != null) return rot * Math.PI / 180.0;
  }
  if (type === 'ARC' && centroid && points && points.length >= 3) {
    var mid = points[Math.floor(points.length / 2)];
    return Math.atan2(mid.y - centroid.y, mid.x - centroid.x);
  }
  if (points && points.length >= 2) {
    var bestLen = 0;
    var bestAng = 0;
    for (var i = 1; i < points.length; i++) {
      var a = points[i - 1], b = points[i];
      var dx = b.x - a.x, dy = b.y - a.y;
      var len = Math.hypot(dx, dy);
      if (len > bestLen + 1e-9) {
        bestLen = len;
        bestAng = Math.atan2(dy, dx);
      }
    }
    if (bestLen > 0) return bestAng;
  }
  return null;
}
function doorDefFitCircleBy3Points(a, b, c) {
  if (!a || !b || !c) return null;
  var x1 = Number(a.x) || 0, y1 = Number(a.y) || 0;
  var x2 = Number(b.x) || 0, y2 = Number(b.y) || 0;
  var x3 = Number(c.x) || 0, y3 = Number(c.y) || 0;
  var d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
  if (!isFinite(d) || Math.abs(d) < 1e-9) return null;
  var x1s = x1 * x1 + y1 * y1;
  var x2s = x2 * x2 + y2 * y2;
  var x3s = x3 * x3 + y3 * y3;
  var ux = (x1s * (y2 - y3) + x2s * (y3 - y1) + x3s * (y1 - y2)) / d;
  var uy = (x1s * (x3 - x2) + x2s * (x1 - x3) + x3s * (x2 - x1)) / d;
  var r = Math.hypot(x1 - ux, y1 - uy);
  if (!isFinite(ux) || !isFinite(uy) || !isFinite(r) || !(r > 0)) return null;
  return { center: { x: ux, y: uy }, radius: r };
}
function doorDefFitCircleLeastSquares(points) {
  if (!points || points.length < 3) return null;
  var n = 0;
  var sxx = 0, sxy = 0, syy = 0, sx = 0, sy = 0;
  var sxz = 0, syz = 0, sz = 0;
  for (var i = 0; i < points.length; i++) {
    var p = points[i];
    if (!p) continue;
    var x = Number(p.x);
    var y = Number(p.y);
    if (!isFinite(x) || !isFinite(y)) continue;
    var z = (x * x) + (y * y);
    n += 1;
    sxx += x * x;
    sxy += x * y;
    syy += y * y;
    sx += x;
    sy += y;
    sxz += x * z;
    syz += y * z;
    sz += z;
  }
  if (n < 3) return null;
  var a11 = sxx, a12 = sxy, a13 = sx;
  var a21 = sxy, a22 = syy, a23 = sy;
  var a31 = sx,  a32 = sy,  a33 = n;
  var b1 = -sxz, b2 = -syz, b3 = -sz;
  var det =
    a11 * (a22 * a33 - a23 * a32) -
    a12 * (a21 * a33 - a23 * a31) +
    a13 * (a21 * a32 - a22 * a31);
  if (!isFinite(det) || Math.abs(det) < 1e-9) return null;
  function det3(
    m11, m12, m13,
    m21, m22, m23,
    m31, m32, m33
  ) {
    return (
      m11 * (m22 * m33 - m23 * m32) -
      m12 * (m21 * m33 - m23 * m31) +
      m13 * (m21 * m32 - m22 * m31)
    );
  }
  var d = det3(b1, a12, a13, b2, a22, a23, b3, a32, a33) / det;
  var e = det3(a11, b1, a13, a21, b2, a23, a31, b3, a33) / det;
  var f = det3(a11, a12, b1, a21, a22, b2, a31, a32, b3) / det;
  var cx = -d / 2;
  var cy = -e / 2;
  var rr = (cx * cx) + (cy * cy) - f;
  if (!isFinite(cx) || !isFinite(cy) || !isFinite(rr) || !(rr > 0)) return null;
  var radius = Math.sqrt(rr);
  if (!(radius > 0) || !isFinite(radius)) return null;
  return { center: { x: cx, y: cy }, radius: radius };
}
function doorDefArcCenterFromProps(ent) {
  var props = ent && ent.props ? ent.props : {};
  var cands = [
    ['center_x', 'center_y'],
    ['cx', 'cy'],
    ['origin_x', 'origin_y']
  ];
  for (var i = 0; i < cands.length; i++) {
    var x = parseFloatOrNull(props[cands[i][0]]);
    var y = parseFloatOrNull(props[cands[i][1]]);
    if (x != null && y != null && isFinite(x) && isFinite(y)) return { x: x, y: y };
  }
  if (props.center && typeof props.center === 'object') {
    var ox = parseFloatOrNull(props.center.x);
    var oy = parseFloatOrNull(props.center.y);
    if (ox != null && oy != null && isFinite(ox) && isFinite(oy)) return { x: ox, y: oy };
  }
  if (typeof props.center === 'string') {
    var m = props.center.match(/(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)/);
    if (m) {
      var sx = parseFloat(m[1]);
      var sy = parseFloat(m[2]);
      if (isFinite(sx) && isFinite(sy)) return { x: sx, y: sy };
    }
  }
  if (ent && ent.point && isFinite(ent.point.x) && isFinite(ent.point.y)) {
    return { x: Number(ent.point.x) || 0, y: Number(ent.point.y) || 0 };
  }
  return null;
}
function doorDefEstimateArcGeometryFromProps(ent, points) {
  if (!ent || String(ent.entity_type || '').toUpperCase() !== 'ARC') return null;
  var props = ent.props || {};
  var r = parseFloatOrNull(props.radius);
  var sa = parseFloatOrNull(props.start_angle);
  var ea = parseFloatOrNull(props.end_angle);
  if (!(r > 0) || sa == null || ea == null) return null;
  var center = doorDefArcCenterFromProps(ent);
  if (!center) return null;
  var saN = doorDefNormalizeDeg360(sa);
  var eaN = doorDefNormalizeDeg360(ea);
  var ccwDeg = (eaN - saN + 360) % 360;
  if (ccwDeg === 0) ccwDeg = 360;
  var cwDeg = 360 - ccwDeg;
  var useCcw = ccwDeg <= cwDeg;
  var spanDeg = useCcw ? ccwDeg : cwDeg;
  if (spanDeg > 180) {
    useCcw = !useCcw;
    spanDeg = 360 - spanDeg;
  }
  var midDeg = useCcw ? (saN + (spanDeg * 0.5)) : (saN - (spanDeg * 0.5));
  var saRad = saN * Math.PI / 180;
  var eaRad = eaN * Math.PI / 180;
  var maRad = doorDefNormalizeDeg360(midDeg) * Math.PI / 180;
  var start = { x: center.x + r * Math.cos(saRad), y: center.y + r * Math.sin(saRad) };
  var mid = { x: center.x + r * Math.cos(maRad), y: center.y + r * Math.sin(maRad) };
  var end = { x: center.x + r * Math.cos(eaRad), y: center.y + r * Math.sin(eaRad) };
  if (points && points.length >= 2) {
    var p0 = points[0];
    var p1 = points[points.length - 1];
    if (p0 && p1) {
      var dss = pointDist(p0, start) + pointDist(p1, end);
      var dse = pointDist(p0, end) + pointDist(p1, start);
      if (dse + 1e-6 < dss) {
        var tmp = start;
        start = end;
        end = tmp;
      }
    }
  }
  return {
    center: center,
    radius: r,
    start: start,
    mid: mid,
    end: end,
    sweep: spanDeg
  };
}
function doorDefEstimateArcGeometry(points) {
  if (!points || points.length < 3) return null;
  var start = points[0];
  var end = points[points.length - 1];
  var mid = points[Math.floor(points.length / 2)];
  var fit = doorDefFitCircleLeastSquares(points) || doorDefFitCircleBy3Points(start, mid, end);
  if (!fit) return null;
  var center = fit.center;
  var r = fit.radius;
  var sa = Math.atan2(start.y - center.y, start.x - center.x);
  var ma = Math.atan2(mid.y - center.y, mid.x - center.x);
  var ea = Math.atan2(end.y - center.y, end.x - center.x);
  function norm(a) {
    while (a < 0) a += Math.PI * 2;
    while (a >= Math.PI * 2) a -= Math.PI * 2;
    return a;
  }
  var saN = norm(sa), maN = norm(ma), eaN = norm(ea);
  var ccw = (eaN - saN + Math.PI * 2) % (Math.PI * 2);
  var cw = (saN - eaN + Math.PI * 2) % (Math.PI * 2);
  var viaCcw = (maN - saN + Math.PI * 2) % (Math.PI * 2);
  var sweepRad = (viaCcw <= ccw + 1e-6) ? ccw : cw;
  var sweepDeg = sweepRad * 180 / Math.PI;
  if (!isFinite(sweepDeg) || sweepDeg <= 0) sweepDeg = null;
  return {
    center: center,
    radius: r,
    start: { x: start.x, y: start.y },
    mid: { x: mid.x, y: mid.y },
    end: { x: end.x, y: end.y },
    sweep: sweepDeg
  };
}
function doorDefEntityDescriptor(ent) {
  if (!ent || ent.isBlockInsert || ent.id == null) return null;
  var type = String(ent.entity_type || '').toUpperCase();
  var points = [];
  if (Array.isArray(ent.points) && ent.points.length) {
    for (var i = 0; i < ent.points.length; i++) points.push({ x: Number(ent.points[i].x) || 0, y: Number(ent.points[i].y) || 0 });
  } else if (ent.point) {
    points.push({ x: Number(ent.point.x) || 0, y: Number(ent.point.y) || 0 });
  }
  var fallbackPoint = ent.point ? { x: Number(ent.point.x) || 0, y: Number(ent.point.y) || 0 } : null;
  var arcGeom = null;
  if (type === 'ARC') {
    arcGeom = doorDefEstimateArcGeometryFromProps(ent, points);
    if (!arcGeom) arcGeom = doorDefEstimateArcGeometry(points);
  }
  var centroid = arcGeom ? { x: arcGeom.center.x, y: arcGeom.center.y } : pointListCentroid(points, fallbackPoint);
  if (!centroid) return null;
  var radius = arcGeom ? arcGeom.radius : doorDefComputeRadius(ent, points, centroid);
  var sweep = doorDefSweepFromProps(ent.props || {}, type);
  if (sweep == null && arcGeom && arcGeom.sweep != null) sweep = arcGeom.sweep;
  var length = doorDefComputeLength(ent, points, type, radius, sweep);
  var area = doorDefComputeArea(ent, points, type);
  var orientation = doorDefComputeOrientation(ent, points, centroid);
  return {
    id: Number(ent.id),
    ent: ent,
    type: type,
    layer: ent.layer || '',
    points: points,
    centroid: centroid,
    length: isFinite(length) ? Number(length) : 0,
    area: isFinite(area) ? Number(area) : 0,
    radius: isFinite(radius) ? Number(radius) : 0,
    sweep: sweep != null && isFinite(sweep) ? Number(sweep) : null,
    orientation: orientation != null && isFinite(orientation) ? Number(orientation) : null,
    arc_center: arcGeom ? { x: arcGeom.center.x, y: arcGeom.center.y } : null,
    arc_start: arcGeom ? { x: arcGeom.start.x, y: arcGeom.start.y } : (points[0] ? { x: points[0].x, y: points[0].y } : null),
    arc_end: arcGeom ? { x: arcGeom.end.x, y: arcGeom.end.y } : (points.length ? { x: points[points.length - 1].x, y: points[points.length - 1].y } : null),
    arc_mid: arcGeom ? { x: arcGeom.mid.x, y: arcGeom.mid.y } : null
  };
}
function doorDefDescriptorIndex() {
  var cid = doorDefCurrentCommitId();
  var firstId = allEntities.length && allEntities[0] && allEntities[0].id != null ? allEntities[0].id : '';
  var lastId = allEntities.length && allEntities[allEntities.length - 1] && allEntities[allEntities.length - 1].id != null ? allEntities[allEntities.length - 1].id : '';
  var sampleSig = 0;
  if (allEntities.length > 0) {
    var step = Math.max(1, Math.floor(allEntities.length / 16));
    for (var si = 0; si < allEntities.length; si += step) {
      var se = allEntities[si];
      if (!se) continue;
      var sx = 0, sy = 0;
      if (se.point) {
        sx = Number(se.point.x) || 0;
        sy = Number(se.point.y) || 0;
      } else if (se.points && se.points.length) {
        var sp = se.points[0];
        sx = Number(sp.x) || 0;
        sy = Number(sp.y) || 0;
      }
      sampleSig += ((Number(se.id) || 0) * 0.17) + (sx * 0.003) + (sy * 0.0021);
    }
  }
  var cacheKey = [cid, allEntities.length, firstId, lastId, Math.round(sampleSig)].join('|');
  if (doorDefDescriptorCache.key === cacheKey && doorDefDescriptorCache.index) return doorDefDescriptorCache.index;
  var byId = {};
  var byType = {};
  var byTypeGrid = {};
  var list = [];
  for (var i = 0; i < allEntities.length; i++) {
    var d = doorDefEntityDescriptor(allEntities[i]);
    if (!d) continue;
    byId[String(d.id)] = d;
    if (!byType[d.type]) byType[d.type] = [];
    byType[d.type].push(d);
    list.push(d);
  }
  var typeKeys = Object.keys(byType);
  for (var t = 0; t < typeKeys.length; t++) {
    var type = typeKeys[t];
    byTypeGrid[type] = doorDefBuildTypeGrid(byType[type], DOOR_DEF_GRID_CELL_MM);
  }
  var built = { byId: byId, byType: byType, byTypeGrid: byTypeGrid, list: list };
  doorDefDescriptorCache.key = cacheKey;
  doorDefDescriptorCache.index = built;
  return built;
}
function doorDefSeedCenter(seedList) {
  if (!seedList || seedList.length === 0) return { x: 0, y: 0 };
  var sx = 0, sy = 0;
  for (var i = 0; i < seedList.length; i++) {
    sx += seedList[i].centroid.x;
    sy += seedList[i].centroid.y;
  }
  return { x: sx / seedList.length, y: sy / seedList.length };
}
function doorDefRepPriority(type) {
  if (type === 'ARC') return 0;
  if (type === 'LINE' || type === 'LWPOLYLINE' || type === 'POLYLINE') return 1;
  return 2;
}
function doorDefPickRepresentative(seedList) {
  if (!seedList || seedList.length === 0) return null;
  var sorted = seedList.slice().sort(function(a, b) {
    var pa = doorDefRepPriority(a.type);
    var pb = doorDefRepPriority(b.type);
    if (pa !== pb) return pa - pb;
    var ma = Math.max(a.length || 0, a.radius || 0);
    var mb = Math.max(b.length || 0, b.radius || 0);
    if (Math.abs(mb - ma) > 1e-9) return mb - ma;
    return a.id - b.id;
  });
  return sorted[0] || null;
}
function doorDefBuildSeedSignature(seedList) {
  var center = doorDefSeedCenter(seedList);
  var rep = doorDefPickRepresentative(seedList);
  if (!rep) return null;
  var members = [];
  var memberById = {};
  for (var i = 0; i < seedList.length; i++) {
    var s = seedList[i];
    var m = {
      id: s.id,
      type: s.type,
      layer: s.layer || '',
      centroid: { x: s.centroid.x, y: s.centroid.y },
      rel: { x: s.centroid.x - center.x, y: s.centroid.y - center.y },
      length: s.length || 0,
      area: s.area || 0,
      radius: s.radius || 0,
      sweep: s.sweep,
      orientation: s.orientation
    };
    members.push(m);
    memberById[String(m.id)] = m;
  }
  var repMember = memberById[String(rep.id)] || null;
  if (!repMember) return null;
  var typeCounts = doorDefBuildTypeCounts(members);
  var coreTypes = Object.keys(typeCounts).sort(function(a, b) {
    var ca = typeCounts[a] || 0;
    var cb = typeCounts[b] || 0;
    if (cb !== ca) return cb - ca;
    return doorDefRepPriority(a) - doorDefRepPriority(b);
  });
  var maxMetric = 0;
  for (var j = 0; j < members.length; j++) {
    var mm = doorDefPrimaryMetric(members[j]);
    if (mm > maxMetric) maxMetric = mm;
  }
  var range = doorDefBuildRangeFromMembers(members);
  var repCenter = repMember.centroid || { x: 0, y: 0 };
  for (var k = 0; k < members.length; k++) {
    var it = members[k];
    it.rel_to_rep = { x: it.centroid.x - repCenter.x, y: it.centroid.y - repCenter.y };
    it.radial = Math.hypot(it.rel.x || 0, it.rel.y || 0);
    var typeRare = 1 / Math.max(1, typeCounts[it.type] || 1);
    var metricNorm = maxMetric > 0 ? (doorDefPrimaryMetric(it) / maxMetric) : 0;
    var distNorm = (range.diag > 0) ? Math.min(1, it.radial / range.diag) : 0;
    var typePriority = 2 - doorDefRepPriority(it.type);
    it.feature_score = (typeRare * 2.2) + (metricNorm * 1.6) + (distNorm * 0.6) + (typePriority * 0.4);
  }
  var featureMemberIds = members.slice().sort(function(a, b) {
    if (Math.abs((b.feature_score || 0) - (a.feature_score || 0)) > 1e-9) return (b.feature_score || 0) - (a.feature_score || 0);
    return a.id - b.id;
  }).slice(0, Math.min(5, members.length)).map(function(m) { return m.id; });
  if (featureMemberIds.indexOf(rep.id) < 0) featureMemberIds.unshift(rep.id);
  featureMemberIds = featureMemberIds.slice(0, Math.min(5, members.length));
  var supportMemberIds = members.filter(function(m) { return m.id !== rep.id; }).sort(function(a, b) {
    var da = Math.hypot(a.rel_to_rep.x || 0, a.rel_to_rep.y || 0);
    var db = Math.hypot(b.rel_to_rep.x || 0, b.rel_to_rep.y || 0);
    if (Math.abs(db - da) > 1e-9) return db - da;
    if (Math.abs((b.feature_score || 0) - (a.feature_score || 0)) > 1e-9) return (b.feature_score || 0) - (a.feature_score || 0);
    return a.id - b.id;
  }).map(function(m) { return m.id; }).slice(0, Math.min(8, Math.max(0, members.length - 1)));
  var matchMembers = members.slice().sort(function(a, b) {
    if (a.id === rep.id) return -1;
    if (b.id === rep.id) return 1;
    var ra = 1 / Math.max(1, typeCounts[a.type] || 1);
    var rb = 1 / Math.max(1, typeCounts[b.type] || 1);
    if (Math.abs(rb - ra) > 1e-9) return rb - ra;
    if (Math.abs((b.feature_score || 0) - (a.feature_score || 0)) > 1e-9) return (b.feature_score || 0) - (a.feature_score || 0);
    var da = Math.hypot(a.rel_to_rep.x || 0, a.rel_to_rep.y || 0);
    var db = Math.hypot(b.rel_to_rep.x || 0, b.rel_to_rep.y || 0);
    if (Math.abs(db - da) > 1e-9) return db - da;
    return a.id - b.id;
  });
  return {
    count: members.length,
    center: center,
    representative_id: rep.id,
    representative_type: rep.type,
    representative_member: repMember,
    members: members,
    match_members: matchMembers,
    member_by_id: memberById,
    type_counts: typeCounts,
    core_types: coreTypes,
    feature_member_ids: featureMemberIds,
    support_member_ids: supportMemberIds,
    range: range
  };
}
function doorDefMetricCompatible(seedItem, candItem, tol, opts) {
  if (!seedItem || !candItem) return false;
  if (seedItem.type !== candItem.type) return false;
  var t = tol > 0 ? tol : DOOR_DEF_MATCH_TOL_MM;
  var relativeTol = (opts && opts.relativeTol > 0) ? opts.relativeTol : 0.18;
  var metricTol = (opts && opts.metricTol > 0) ? opts.metricTol : t;
  function metricWithin(a, b, ratio) {
    var x = Number(a) || 0;
    var y = Number(b) || 0;
    if (!(x > 0) || !(y > 0)) return true;
    var rel = ratio > 0 ? ratio : relativeTol;
    var lim = Math.max(metricTol, Math.max(x, y) * rel);
    return Math.abs(x - y) <= lim;
  }
  var sr = seedItem.radius || 0;
  var cr = candItem.radius || 0;
  var sl = seedItem.length || 0;
  var cl = candItem.length || 0;
  if (sr > 0 && cr > 0) {
    if (!metricWithin(sr, cr, relativeTol * 0.8)) return false;
  } else if (sl > 0 && cl > 0) {
    if (!metricWithin(sl, cl, relativeTol)) return false;
  } else {
    var sm = doorDefPrimaryMetric(seedItem);
    var cm = doorDefPrimaryMetric(candItem);
    if (sm > 0 && cm > 0 && !metricWithin(sm, cm, relativeTol * 1.2)) return false;
  }
  if (seedItem.sweep != null && candItem.sweep != null) {
    var sweepTol = (opts && opts.sweepTol > 0) ? opts.sweepTol : 18;
    if (Math.abs((seedItem.sweep || 0) - (candItem.sweep || 0)) > sweepTol) return false;
  }
  if ((seedItem.area || 0) > 0 && (candItem.area || 0) > 0) {
    var sa = seedItem.area || 0;
    var ca = candItem.area || 0;
    var areaTol = Math.max(metricTol * metricTol * 2.5, Math.max(sa, ca) * 0.38);
    if (Math.abs(sa - ca) > areaTol) return false;
  }
  return true;
}
function doorDefCandidateCenter(matchedList) {
  if (!matchedList || matchedList.length === 0) return { x: 0, y: 0 };
  var sx = 0, sy = 0;
  for (var i = 0; i < matchedList.length; i++) {
    sx += matchedList[i].centroid.x;
    sy += matchedList[i].centroid.y;
  }
  return { x: sx / matchedList.length, y: sy / matchedList.length };
}
function doorDefTypeSummary(descs) {
  var counts = {};
  for (var i = 0; i < descs.length; i++) {
    var t = descs[i].type || '?';
    counts[t] = (counts[t] || 0) + 1;
  }
  var keys = Object.keys(counts).sort();
  return keys.map(function(k) { return k + ' ' + counts[k]; }).join(', ');
}
function doorDefEntityById(id) {
  var key = String(id == null ? '' : id);
  if (!key) return null;
  var ent = entityById[key];
  if (ent) return ent;
  for (var i = 0; i < allEntities.length; i++) {
    if (String(allEntities[i].id) === key) return allEntities[i];
  }
  return null;
}
function doorDefEntityCenter(ent) {
  if (!ent) return null;
  if (ent.point) return { x: Number(ent.point.x) || 0, y: Number(ent.point.y) || 0 };
  if (ent.points && ent.points.length > 0) return pointListCentroid(ent.points, ent.points[0] || null);
  return null;
}
function doorDefUniqueEntityIds(ids) {
  var out = [];
  var seen = {};
  for (var i = 0; i < (ids || []).length; i++) {
    var n = parseInt(ids[i], 10);
    if (!(n > 0) || seen[n]) continue;
    if (!doorDefEntityById(n)) continue;
    seen[n] = true;
    out.push(n);
  }
  return out;
}
function doorDefNormalizeHexColor(c) {
  var s = String(c == null ? '' : c).trim().toLowerCase();
  if (!s) return '';
  if (s.indexOf('rgb') === 0) {
    var m = s.match(/rgba?\s*\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)/i);
    if (m) {
      var r = Math.max(0, Math.min(255, Math.round(Number(m[1]) || 0)));
      var g = Math.max(0, Math.min(255, Math.round(Number(m[2]) || 0)));
      var b = Math.max(0, Math.min(255, Math.round(Number(m[3]) || 0)));
      return '#' + [r, g, b].map(function(v) { return v.toString(16).padStart(2, '0'); }).join('');
    }
    return '';
  }
  if (s[0] !== '#') return '';
  if (s.length === 4) {
    return '#' + s[1] + s[1] + s[2] + s[2] + s[3] + s[3];
  }
  if (s.length !== 7) return '';
  return s;
}
function doorDefHexToRgb(hex) {
  var h = doorDefNormalizeHexColor(hex);
  if (!h) return null;
  var r = parseInt(h.slice(1, 3), 16);
  var g = parseInt(h.slice(3, 5), 16);
  var b = parseInt(h.slice(5, 7), 16);
  if (!isFinite(r) || !isFinite(g) || !isFinite(b)) return null;
  return { r: r, g: g, b: b };
}
function doorDefEntityDisplayColorHex(ent) {
  if (!ent) return '';
  try {
    if (typeof displayColor === 'function') {
      var dc = doorDefNormalizeHexColor(displayColor(ent));
      if (dc) return dc;
    }
  } catch (_) {}
  var useLayer = (ent.props == null || ent.props.color_bylayer !== false) &&
    (typeof layerColors !== 'undefined') &&
    layerColors && ent.layer != null && layerColors[ent.layer] != null;
  var aci = useLayer ? layerColors[ent.layer] : (ent.color != null ? ent.color : null);
  if (typeof getColor === 'function') return doorDefNormalizeHexColor(getColor(aci));
  return '';
}
function doorDefEntityDisplayAci(ent) {
  if (!ent) return null;
  var useLayer = (ent.props == null || ent.props.color_bylayer !== false) &&
    (typeof layerColors !== 'undefined') &&
    layerColors && ent.layer != null && layerColors[ent.layer] != null;
  var raw = useLayer ? layerColors[ent.layer] : (ent.color != null ? ent.color : null);
  var n = Number(raw);
  if (!isFinite(n)) return null;
  return Math.round(n);
}
function doorDefIsDoorGray(hex) {
  var rgb = doorDefHexToRgb(hex);
  if (!rgb) return false;
  var r = rgb.r, g = rgb.g, b = rgb.b;
  var drg = Math.abs(r - g);
  var dgb = Math.abs(g - b);
  var drb = Math.abs(r - b);
  return drg <= 24 && dgb <= 24 && drb <= 24;
}
function doorDefIsDoorColorAllowed(ent, hex) {
  var aci = doorDefEntityDisplayAci(ent);
  if (aci === 4) return true; // ACI4(청록)만 허용
  return doorDefIsDoorGray(hex);
}
function doorDefFilterEntityIdsByDoorColors(entityIds, idx, arcIds) {
  var ids = doorDefUniqueEntityIds(entityIds || []);
  if (!ids.length) return ids;
  var arcKeep = {};
  for (var i = 0; i < (arcIds || []).length; i++) {
    var aid = parseInt(arcIds[i], 10);
    if (aid > 0) arcKeep[aid] = true;
  }
  var out = [];
  for (var k = 0; k < ids.length; k++) {
    var id = parseInt(ids[k], 10);
    if (!(id > 0)) continue;
    if (arcKeep[id]) {
      out.push(id);
      continue;
    }
    var d = idx && idx.byId ? idx.byId[String(id)] : null;
    var ent = d && d.ent ? d.ent : doorDefEntityById(id);
    if (!ent && d) ent = { id: d.id, color: d.ent ? d.ent.color : null, layer: d.layer, props: d.ent ? d.ent.props : null };
    var hex = doorDefEntityDisplayColorHex(ent);
    if (doorDefIsDoorColorAllowed(ent, hex)) out.push(id);
  }
  if (!out.length) {
    var arcOnly = [];
    for (var ai = 0; ai < (arcIds || []).length; ai++) {
      var aid = parseInt(arcIds[ai], 10);
      if (aid > 0) arcOnly.push(aid);
    }
    if (arcOnly.length) return doorDefUniqueEntityIds(arcOnly);
    return ids;
  }
  return doorDefUniqueEntityIds(out);
}
function doorDefDoorLineLenMm(desc, id) {
  var d = desc || null;
  var type = d && d.type ? String(d.type).toUpperCase() : '';
  var pts = d && d.points && d.points.length ? d.points : null;
  if ((!pts || pts.length < 2) && id > 0) {
    var ent = doorDefEntityById(id);
    if (ent && ent.points && ent.points.length >= 2) pts = ent.points;
  }
  var len = Number(d && d.length) || 0;
  if (type === 'LINE') {
    if (len > 0) return len;
    if (pts && pts.length >= 2) return pointDist(pts[0], pts[pts.length - 1]) || 0;
    return 0;
  }
  if (type === 'LWPOLYLINE' || type === 'POLYLINE') {
    if (pts && pts.length >= 2) {
      var segMax = 0;
      for (var si = 1; si < pts.length; si++) {
        var seg = pointDist(pts[si - 1], pts[si]) || 0;
        if (seg > segMax) segMax = seg;
      }
      var bb = pointListBBox(pts, pts[0]);
      var span = Math.max(bb.w || 0, bb.h || 0);
      var endDist = pointDist(pts[0], pts[pts.length - 1]) || 0;
      var closeTol = Math.max(1, span * 0.02);
      var closedLike = endDist <= closeTol;
      if (closedLike) {
        var closedLen = len > 0 ? len : Math.max(span, segMax);
        return Math.max(closedLen, span, segMax);
      }
      // 열린 폴리라인은 "세그먼트 기준 최소 길이"를 같이 적용해 70mm 이하 쪼개진 선을 제거한다.
      if (segMax > 0 && segMax <= DOOR_DEF_MIN_LINEAR_LEN_MM) return segMax;
      return Math.max(span, endDist, segMax);
    }
    return len;
  }
  if (len > 0) return len;
  if (pts && pts.length >= 2) {
    var bb2 = pointListBBox(pts, pts[0]);
    return Math.max(bb2.w || 0, bb2.h || 0);
  }
  return 0;
}
function doorDefGetEntityTypeByDescOrId(desc, id) {
  var d = desc || null;
  var type = d && d.type ? String(d.type).toUpperCase() : '';
  if (type) return type;
  if (id > 0) {
    var ent = doorDefEntityById(id);
    if (ent && ent.entity_type) return String(ent.entity_type).toUpperCase();
  }
  return '';
}
function doorDefGetEntityPointsByDescOrId(desc, id) {
  var d = desc || null;
  var pts = d && d.points && d.points.length ? d.points : null;
  if ((!pts || pts.length < 2) && id > 0) {
    var ent = doorDefEntityById(id);
    if (ent && ent.points && ent.points.length >= 2) pts = ent.points;
  }
  return pts && pts.length ? pts : null;
}
function doorDefIsClosedPolylineLike(desc, id) {
  var type = doorDefGetEntityTypeByDescOrId(desc, id);
  if (!(type === 'LWPOLYLINE' || type === 'POLYLINE')) return false;
  var pts = doorDefGetEntityPointsByDescOrId(desc, id);
  if (!pts || pts.length < 3) return false;
  var p0 = pts[0];
  var p1 = pts[pts.length - 1];
  if (!p0 || !p1) return false;
  var bb = pointListBBox(pts, pts[0]);
  var span = Math.max(bb.w || 0, bb.h || 0);
  var closeTol = Math.max(1, span * 0.03);
  return pointDist(p0, p1) <= closeTol;
}
function doorDefIsLinearLikeEntity(desc, id) {
  var type = doorDefGetEntityTypeByDescOrId(desc, id);
  if (type === 'ARC') return false;
  if (type === 'LINE' || type === 'LWPOLYLINE' || type === 'POLYLINE' || type === 'SPLINE') return true;
  var pts = doorDefGetEntityPointsByDescOrId(desc, id);
  return !!(pts && pts.length >= 2);
}
function doorDefFilterOpeningEntityIdsByLinearMinLen(entityIds, idx, arcIds) {
  var ids = doorDefUniqueEntityIds(entityIds || []);
  if (!ids.length) return ids;
  var arcKeep = {};
  for (var i = 0; i < (arcIds || []).length; i++) {
    var aid = parseInt(arcIds[i], 10);
    if (aid > 0) arcKeep[aid] = true;
  }
  var out = [];
  for (var k = 0; k < ids.length; k++) {
    var id = parseInt(ids[k], 10);
    if (!(id > 0)) continue;
    if (arcKeep[id]) {
      out.push(id);
      continue;
    }
    var d = idx && idx.byId ? idx.byId[String(id)] : null;
    if (doorDefIsLinearLikeEntity(d, id)) {
      var len = doorDefDoorLineLenMm(d, id);
      if (len <= (DOOR_DEF_MIN_LINEAR_LEN_MM + 1e-6)) continue;
    }
    out.push(id);
  }
  if (!out.length) {
    var arcOnly = [];
    for (var ai = 0; ai < (arcIds || []).length; ai++) {
      var aid2 = parseInt(arcIds[ai], 10);
      if (aid2 > 0) arcOnly.push(aid2);
    }
    if (arcOnly.length) return doorDefUniqueEntityIds(arcOnly);
  }
  return doorDefUniqueEntityIds(out);
}
function doorDefExpandDoorEntityIds(entityIds, idx, widthMm, opts) {
  var cfg = opts || {};
  var allowedIdSet = cfg.allowedIdSet || null;
  var relaxed = !!cfg.relaxed;
  var ids = doorDefUniqueEntityIds(entityIds || []);
  if (!ids.length || !idx) return ids;
  var idSet = {};
  for (var i = 0; i < ids.length; i++) idSet[ids[i]] = true;
  var ext = doorDefGroupRangeByIds(ids);
  var center = ext && ext.center ? ext.center : null;
  if (!center) {
    center = { x: 0, y: 0 };
    for (var ci = 0; ci < ids.length; ci++) {
      var cd = idx.byId ? idx.byId[String(ids[ci])] : null;
      if (!cd || !cd.centroid) continue;
      center.x += cd.centroid.x;
      center.y += cd.centroid.y;
    }
    center.x /= Math.max(1, ids.length);
    center.y /= Math.max(1, ids.length);
  }
  var w = Number(widthMm) || 0;
  var includeT = doorDefIncludeExtentRatio();
  var nearT = doorDefArcNearTightRatio();
  var strictScale = doorDefStrictTightnessScale(includeT, nearT);
  var nearTolScale = doorDefLerp(1.24, 0.34, nearT) * strictScale;
  var baseW = (w > 0 ? w : 900);
  var linkTolMul = relaxed ? doorDefLerp(0.08, 0.24, includeT) : doorDefLerp(0.06, 0.14, includeT);
  var linkTol = Math.max(5, Math.min(180, baseW * linkTolMul * nearTolScale));
  var maxLenMul = relaxed ? doorDefLerp(0.95, 1.82, includeT) : doorDefLerp(0.84, 1.38, includeT);
  var maxLen = Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM + 10, (w > 0 ? w : 1200) * maxLenMul * doorDefLerp(1.02, 0.72, nearT) * strictScale);
  var searchR = Math.max(
    ((ext && ext.radius ? ext.radius : 0) + linkTol + (w > 0 ? (w * doorDefLerp(0.20, 0.68, includeT) * doorDefLerp(1.00, 0.70, nearT)) : doorDefLerp(90, 280, includeT) * doorDefLerp(0.98, 0.66, nearT))) * strictScale,
    w * doorDefLerp(0.96, 1.65, includeT) * doorDefLerp(1.0, 0.62, nearT) * strictScale,
    95
  );
  var maxAdds = Math.max(2, Math.round((relaxed ? doorDefLerp(8, 46, includeT) : doorDefLerp(4, 22, includeT)) * doorDefLerp(1.02, 0.56, nearT) * doorDefLerp(1.0, 0.72, strictScale)));
  var maxPass = Math.max(1, Math.round((relaxed ? doorDefLerp(2, 4, includeT) : doorDefLerp(1, 3, includeT)) * doorDefLerp(0.98, 0.72, nearT) * doorDefLerp(1.0, 0.84, strictScale)));
  var seedPts = [];
  function pushSeed(pt) {
    if (!pt) return;
    seedPts.push({ x: Number(pt.x) || 0, y: Number(pt.y) || 0 });
  }
  function collectDescEndpoints(desc) {
    if (!desc) return;
    if (desc.type === 'ARC') {
      if (desc.arc_start) pushSeed(desc.arc_start);
      if (desc.arc_end) pushSeed(desc.arc_end);
      return;
    }
    var pts = desc.points && desc.points.length ? desc.points : null;
    if (pts && pts.length) {
      pushSeed(pts[0]);
      pushSeed(pts[pts.length - 1]);
    }
  }
  for (var si = 0; si < ids.length; si++) {
    var sd = idx.byId ? idx.byId[String(ids[si])] : null;
    collectDescEndpoints(sd);
  }
  if (!seedPts.length && ext && ext.center) pushSeed(ext.center);
  var pool = []
    .concat(doorDefSpatialPool(idx, 'LINE', center, searchR))
    .concat(doorDefSpatialPool(idx, 'LWPOLYLINE', center, searchR))
    .concat(doorDefSpatialPool(idx, 'POLYLINE', center, searchR));
  var addCnt = 0;
  for (var pass = 0; pass < maxPass && addCnt < maxAdds; pass++) {
    var addedThisPass = 0;
    for (var pi = 0; pi < pool.length && addCnt < maxAdds; pi++) {
      var d = pool[pi];
      if (!d || d.id == null) continue;
      var id = Number(d.id);
      if (!(id > 0) || idSet[id]) continue;
      if (allowedIdSet && !allowedIdSet[id]) continue;
      var len = doorDefDoorLineLenMm(d, id);
      if (len <= DOOR_DEF_MIN_LINEAR_LEN_MM) continue;
      if (len > maxLen) continue;
      var pts = d.points && d.points.length ? d.points : null;
      if (!pts || !pts.length) continue;
      var p0 = pts[0];
      var p1 = pts[pts.length - 1];
      var near = false;
      for (var sp = 0; sp < seedPts.length; sp++) {
        var spt = seedPts[sp];
        if ((p0 && pointDist(p0, spt) <= linkTol) || (p1 && pointDist(p1, spt) <= linkTol)) {
          near = true;
          break;
        }
      }
      if (!near) continue;
      if (d.centroid && pointDist(d.centroid, center) > (searchR + linkTol)) continue;
      idSet[id] = true;
      ids.push(id);
      collectDescEndpoints(d);
      addCnt += 1;
      addedThisPass += 1;
    }
    if (addedThisPass <= 0) break;
  }
  return doorDefUniqueEntityIds(ids);
}
function doorDefGroupRangeByIds(entityIds) {
  var ids = doorDefUniqueEntityIds(entityIds || []);
  if (!ids.length) return null;
  var pts = [];
  for (var i = 0; i < ids.length; i++) {
    var ent = doorDefEntityById(ids[i]);
    if (!ent) continue;
    if (ent.point) pts.push({ x: Number(ent.point.x) || 0, y: Number(ent.point.y) || 0 });
    if (ent.points && ent.points.length) {
      for (var p = 0; p < ent.points.length; p++) {
        var pt = ent.points[p];
        if (!pt) continue;
        pts.push({ x: Number(pt.x) || 0, y: Number(pt.y) || 0 });
      }
    }
  }
  if (!pts.length) return null;
  var bbox = pointListBBox(pts, pts[0]);
  var center = pointListCentroid(pts, pts[0]);
  var radius = 0;
  for (var j = 0; j < pts.length; j++) {
    var d = pointDist(center, pts[j]);
    if (isFinite(d) && d > radius) radius = d;
  }
  return { bbox: bbox, center: center, radius: radius };
}
function doorDefSetSelectedEntities(ids) {
  selectedEntityIds = doorDefUniqueEntityIds(ids || []);
  resetBlockPathSelection();
  if (typeof updateRightDetail === 'function') updateRightDetail();
  draw();
}
function doorDefCollectCheckedCandidateEntityIds(includeSeed) {
  var ids = [];
  if (includeSeed && doorDefState.seedIds && doorDefState.seedIds.length) {
    for (var si = 0; si < doorDefState.seedIds.length; si++) ids.push(doorDefState.seedIds[si]);
  }
  for (var i = 0; i < (doorDefState.candidates || []).length; i++) {
    var c = doorDefState.candidates[i];
    if (!c || doorDefState.checkedCandidateIds[c.candidate_id] === false) continue;
    var arr = c.entity_ids || [];
    for (var j = 0; j < arr.length; j++) ids.push(arr[j]);
  }
  return doorDefUniqueEntityIds(ids);
}
function doorDefSyncSelectionFromCandidates() {
  var ids = doorDefCollectCheckedCandidateEntityIds(true);
  if (!ids.length && doorDefState.seedIds && doorDefState.seedIds.length) ids = doorDefUniqueEntityIds(doorDefState.seedIds);
  doorDefSetSelectedEntities(ids);
}
function doorDefGetCandidateById(cid) {
  var id = String(cid || '').trim();
  if (!id) return null;
  if (id === 'origin') {
    return {
      candidate_id: 'origin',
      entity_ids: (doorDefState.seedIds || []).slice(),
      kind: 'origin',
      label: '원본'
    };
  }
  for (var i = 0; i < (doorDefState.candidates || []).length; i++) {
    if (String(doorDefState.candidates[i].candidate_id) === id) return doorDefState.candidates[i];
  }
  return null;
}
function doorDefSetActiveCandidate(cid, opts) {
  var id = String(cid || '').trim();
  var cand = doorDefGetCandidateById(id);
  if (!cand) return false;
  doorDefState.activeCandidateId = id;
  if (!(opts && opts.keepDefined)) doorDefState.selectedDefinedGroupId = '';
  if (!(opts && opts.skipSelect)) doorDefSetSelectedEntities(cand.entity_ids || []);
  if (!(opts && opts.skipRender)) doorDefRenderCandidateList();
  return true;
}
function doorDefGroupNoInfo(rawNo, gid) {
  var n = parseInt(rawNo, 10);
  if (!(n > 0)) {
    var m = String(gid || '').match(/-(\d+)$/);
    if (m) n = parseInt(m[1], 10);
  }
  if (!(n > 0)) n = 0;
  return { noNum: n, noStr: n > 0 ? doorDefPadNo(n) : String(rawNo || '') };
}
function doorDefNormalizeDetectGauge(v) {
  var n = parseInt(v, 10);
  if (!isFinite(n)) n = 80;
  if (n < 0) n = 0;
  if (n > 100) n = 100;
  return n;
}
function doorDefDetectGaugeFromIncludeExtent(includeExtent) {
  var inc = doorDefNormalizeIncludeExtent(includeExtent);
  var minI = DOOR_DEF_INCLUDE_EXTENT_MIN;
  var maxI = DOOR_DEF_INCLUDE_EXTENT_MAX;
  var t = (maxI > minI) ? ((inc - minI) / (maxI - minI)) : 0;
  if (!isFinite(t)) t = 0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  // 탐지민감도는 포함정도에 통합: 기본(0%)은 90, 최대(100%)는 100으로 연동.
  var gauge = Math.round(doorDefLerp(90, 100, t));
  return doorDefNormalizeDetectGauge(gauge);
}
function doorDefIncludeExtentFromDetectGauge(gauge) {
  var g = doorDefNormalizeDetectGauge(gauge);
  var minG = 90;
  var maxG = 100;
  var t = (maxG > minG) ? ((g - minG) / (maxG - minG)) : 0;
  if (!isFinite(t)) t = 0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  var inc = Math.round(doorDefLerp(DOOR_DEF_INCLUDE_EXTENT_MIN, DOOR_DEF_INCLUDE_EXTENT_MAX, t));
  return doorDefNormalizeIncludeExtent(inc);
}
function doorDefGetDetectGauge() {
  var includeExtent = doorDefGetIncludeExtent();
  var g = doorDefDetectGaugeFromIncludeExtent(includeExtent);
  if (doorDefState && typeof doorDefState === 'object') doorDefState.detectGauge = g;
  return g;
}
function doorDefSetDetectGauge(v) {
  var includeExtent = doorDefIncludeExtentFromDetectGauge(v);
  doorDefSetIncludeExtent(includeExtent);
  return doorDefGetDetectGauge();
}
function doorDefNormalizeIncludeExtent(v) {
  var n = parseInt(v, 10);
  if (!isFinite(n)) n = DOOR_DEF_INCLUDE_EXTENT_DEFAULT;
  if (n < DOOR_DEF_INCLUDE_EXTENT_MIN) n = DOOR_DEF_INCLUDE_EXTENT_MIN;
  if (n > DOOR_DEF_INCLUDE_EXTENT_MAX) n = DOOR_DEF_INCLUDE_EXTENT_MAX;
  return n;
}
function doorDefGetIncludeExtent() {
  if (!doorDefState || typeof doorDefState !== 'object') return DOOR_DEF_INCLUDE_EXTENT_DEFAULT;
  var v = doorDefNormalizeIncludeExtent(doorDefState.includeExtent);
  doorDefState.includeExtent = v;
  return v;
}
function doorDefSetIncludeExtent(v) {
  var n = doorDefNormalizeIncludeExtent(v);
  if (doorDefState && typeof doorDefState === 'object') {
    doorDefState.includeExtent = n;
    doorDefState.arcNearGauge = doorDefArcNearGaugeFromIncludeExtent(n);
  }
  return n;
}
function doorDefArcNearGaugeFromIncludeExtent(includeExtent) {
  var inc = doorDefNormalizeIncludeExtent(includeExtent);
  var minI = DOOR_DEF_INCLUDE_EXTENT_MIN;
  var maxI = DOOR_DEF_INCLUDE_EXTENT_MAX;
  var t = (maxI > minI) ? ((inc - minI) / (maxI - minI)) : 0;
  if (!isFinite(t)) t = 0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  var gauge = Math.round(doorDefLerp(DOOR_DEF_ARC_NEAR_GAUGE_DEFAULT, DOOR_DEF_ARC_NEAR_GAUGE_MIN, t));
  return doorDefNormalizeArcNearGauge(gauge);
}
function doorDefIncludeExtentFromArcNearGauge(gauge) {
  var g = doorDefNormalizeArcNearGauge(gauge);
  var high = DOOR_DEF_ARC_NEAR_GAUGE_DEFAULT;
  var low = DOOR_DEF_ARC_NEAR_GAUGE_MIN;
  var t = (high > low) ? ((high - g) / (high - low)) : 0;
  if (!isFinite(t)) t = 0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  var inc = Math.round(doorDefLerp(DOOR_DEF_INCLUDE_EXTENT_MIN, DOOR_DEF_INCLUDE_EXTENT_MAX, t));
  return doorDefNormalizeIncludeExtent(inc);
}
function doorDefNormalizeArcNearGauge(v) {
  var n = parseInt(v, 10);
  if (!isFinite(n)) n = DOOR_DEF_ARC_NEAR_GAUGE_DEFAULT;
  if (n < DOOR_DEF_ARC_NEAR_GAUGE_MIN) n = DOOR_DEF_ARC_NEAR_GAUGE_MIN;
  if (n > DOOR_DEF_ARC_NEAR_GAUGE_MAX) n = DOOR_DEF_ARC_NEAR_GAUGE_MAX;
  return n;
}
function doorDefGetArcNearGauge() {
  var includeExtent = doorDefGetIncludeExtent();
  var v = doorDefArcNearGaugeFromIncludeExtent(includeExtent);
  if (doorDefState && typeof doorDefState === 'object') doorDefState.arcNearGauge = v;
  return v;
}
function doorDefSetArcNearGauge(v) {
  var includeExtent = doorDefIncludeExtentFromArcNearGauge(v);
  doorDefSetIncludeExtent(includeExtent);
  return doorDefGetArcNearGauge();
}
function doorDefIncludeExtentRatio() {
  var raw = doorDefGetIncludeExtent();
  var minV = DOOR_DEF_INCLUDE_EXTENT_MIN;
  var maxV = DOOR_DEF_INCLUDE_EXTENT_MAX;
  if (!(maxV > minV)) return 0;
  var t = (raw - minV) / (maxV - minV);
  if (!isFinite(t)) t = 0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  return t;
}
function doorDefArcNearTightRatio() {
  var gauge = doorDefGetArcNearGauge();
  var maxV = DOOR_DEF_ARC_NEAR_GAUGE_MAX > 0 ? DOOR_DEF_ARC_NEAR_GAUGE_MAX : 100;
  if (gauge <= 100 || !(maxV > 100)) return Math.max(0, gauge / 100);
  var extra = (gauge - 100) / (maxV - 100);
  if (!isFinite(extra)) extra = 0;
  if (extra < 0) extra = 0;
  if (extra > 1) extra = 1;
  return 1 + (extra * 0.5);
}
function doorDefStrictTightnessScale(includeT, nearT) {
  var it = Number(includeT);
  if (!isFinite(it)) it = 0;
  if (it < 0) it = 0;
  if (it > 1) it = 1;
  var nt = Number(nearT);
  if (!isFinite(nt)) nt = 0;
  if (nt < 0) nt = 0;
  var nearBase = nt > 1 ? 1 : nt;
  var strictT = (1 - it) * nearBase;
  var scale = doorDefLerp(1.0, 0.50, strictT);
  if (nt > 1) {
    var extra = nt - 1;
    scale *= Math.max(0.55, 1 - extra * 0.6);
  }
  if (scale < 0.30) scale = 0.30;
  if (scale > 1.0) scale = 1.0;
  return scale;
}
function doorDefLerp(a, b, t) {
  var aa = Number(a) || 0;
  var bb = Number(b) || 0;
  var tt = Number(t);
  if (!isFinite(tt)) tt = 0;
  if (tt < 0) tt = 0;
  if (tt > 1) tt = 1;
  return aa + ((bb - aa) * tt);
}
function doorDefNormalizeMinArcWidthMm(v) {
  var n = parseInt(v, 10);
  if (!isFinite(n)) n = DOOR_DEF_MIN_ARC_WIDTH_MM_DEFAULT;
  n = Math.round(n / 10) * 10;
  if (n < DOOR_DEF_MIN_ARC_WIDTH_MM_MIN) n = DOOR_DEF_MIN_ARC_WIDTH_MM_MIN;
  if (n > DOOR_DEF_MIN_ARC_WIDTH_MM_MAX) n = DOOR_DEF_MIN_ARC_WIDTH_MM_MAX;
  return n;
}
function doorDefGetMinArcWidthMm() {
  if (!doorDefState || typeof doorDefState !== 'object') return DOOR_DEF_MIN_ARC_WIDTH_MM_DEFAULT;
  var w = doorDefNormalizeMinArcWidthMm(doorDefState.minArcWidthMm);
  doorDefState.minArcWidthMm = w;
  return w;
}
function doorDefSetMinArcWidthMm(v) {
  var w = doorDefNormalizeMinArcWidthMm(v);
  if (doorDefState && typeof doorDefState === 'object') doorDefState.minArcWidthMm = w;
  return w;
}
function doorDefNormalizeMaxArcWidthMm(v) {
  var n = parseInt(v, 10);
  if (!isFinite(n)) n = DOOR_DEF_MAX_ARC_WIDTH_MM_DEFAULT;
  n = Math.round(n / 10) * 10;
  if (n < DOOR_DEF_MAX_ARC_WIDTH_MM_MIN) n = DOOR_DEF_MAX_ARC_WIDTH_MM_MIN;
  if (n > DOOR_DEF_MAX_ARC_WIDTH_MM_MAX) n = DOOR_DEF_MAX_ARC_WIDTH_MM_MAX;
  return n;
}
function doorDefGetMaxArcWidthMm() {
  if (!doorDefState || typeof doorDefState !== 'object') return DOOR_DEF_MAX_ARC_WIDTH_MM_DEFAULT;
  var w = doorDefNormalizeMaxArcWidthMm(doorDefState.maxArcWidthMm);
  doorDefState.maxArcWidthMm = w;
  return w;
}
function doorDefSetMaxArcWidthMm(v) {
  var w = doorDefNormalizeMaxArcWidthMm(v);
  if (doorDefState && typeof doorDefState === 'object') doorDefState.maxArcWidthMm = w;
  return w;
}
function doorDefGetArcWidthRangeMm() {
  var minW = doorDefGetMinArcWidthMm();
  var maxW = doorDefGetMaxArcWidthMm();
  if (maxW < minW) {
    maxW = minW;
    if (doorDefState && typeof doorDefState === 'object') doorDefState.maxArcWidthMm = maxW;
  }
  return { min: minW, max: maxW };
}
function doorDefArcLikeDescriptor(desc) {
  if (!desc) return null;
  if (desc.type !== 'ARC') return null;
  if (doorDefArcLikelyNonDoorContext(desc)) return null;
  return desc;
}
function doorDefArcContextText(desc) {
  var ent = desc && desc.ent ? desc.ent : null;
  if (!ent) return '';
  var parts = [];
  if (ent.layer != null) parts.push(String(ent.layer));
  if (ent.blockName != null) parts.push(String(ent.blockName));
  if (Array.isArray(ent.__bhLabels)) parts = parts.concat(ent.__bhLabels.map(function(v) { return String(v || ''); }));
  var path = doorDefParseHierarchyPath(ent.props && ent.props.block_hierarchy_path);
  for (var i = 0; i < path.length; i++) {
    var seg = path[i];
    if (!seg) continue;
    if (typeof seg === 'object') {
      if (seg.name != null) parts.push(String(seg.name));
      if (seg.instance_key != null) parts.push(String(seg.instance_key));
      if (seg.key != null) parts.push(String(seg.key));
    } else {
      parts.push(String(seg));
    }
  }
  return parts.join(' | ');
}
function doorDefTextHasAnyKeyword(text, keywords) {
  var s = String(text || '');
  if (!s) return false;
  var up = s.toUpperCase();
  for (var i = 0; i < (keywords || []).length; i++) {
    var k = String(keywords[i] || '');
    if (!k) continue;
    var ku = k.toUpperCase();
    if (up.indexOf(ku) >= 0 || s.indexOf(k) >= 0) return true;
  }
  return false;
}
function doorDefLayerLooksDoor(layerText) {
  var raw = String(layerText || '');
  if (!raw) return false;
  var up = raw.toUpperCase();
  if (up.indexOf('A-FLOR-STRA') >= 0) return false;
  if (up.indexOf('DOOR') >= 0) return true;
  return raw.indexOf('문') >= 0;
}
function doorDefArcLikelyNonDoorContext(desc) {
  var text = doorDefArcContextText(desc);
  if (!text) return false;
  var doorHints = ['A-DOOR', 'DOOR', 'SWNG', '문', '출입문', '개구부', '창호'];
  if (doorDefTextHasAnyKeyword(text, doorHints)) return false;
  var badHints = [
    'I-F-',
    '설비',
    '설비관련',
    'BATH',
    '욕실',
    '수전',
    '위생',
    'PLUMB',
    'SANIT',
    'LAV',
    'FURN',
    '가구',
    'BF90'
  ];
  return doorDefTextHasAnyKeyword(text, badHints);
}
function doorDefArcLikelyPartialDoorContext(desc) {
  var text = doorDefArcContextText(desc);
  if (!text) return false;
  if (doorDefTextHasAnyKeyword(text, ['만능문'])) return true;
  if (doorDefTextHasAnyKeyword(text, ['실외기실']) && doorDefTextHasAnyKeyword(text, ['A-DOOR', 'DOOR', 'SWNG', '문'])) return true;
  return false;
}
function doorDefIsPartialOpenDoorArcCandidate(desc, gauge) {
  if (!desc || desc.type !== 'ARC') return false;
  if (doorDefArcLikelyNonDoorContext(desc)) return false;
  if (!doorDefArcLikelyPartialDoorContext(desc)) return false;
  var g = Number(gauge);
  if (!isFinite(g)) g = doorDefGetDetectGauge();
  var radius = Math.abs(Number(desc.radius) || 0);
  if (!(radius >= 350 && radius <= 2600)) return false;
  var sweep = desc.sweep != null ? Math.abs(Number(desc.sweep)) : NaN;
  if (!isFinite(sweep)) return false;
  var minSweep = Math.max(4, 14 - (g * 0.08));
  var maxSweep = Math.min(70, 44 + (g * 0.08));
  if (sweep < minSweep || sweep > maxSweep) return false;
  if (desc.arc_start && desc.arc_end) {
    var chord = pointDist(desc.arc_start, desc.arc_end);
    if (isFinite(chord) && chord > 0) {
      if (chord < Math.max(30, radius * 0.08)) return false;
      if (chord > radius * 1.05) return false;
    }
  }
  return true;
}
function doorDefIsOpeningArcCandidate(desc, idx, blockEntityCount) {
  if (!desc || desc.type !== 'ARC') return false;
  if (doorDefArcLikelyNonDoorContext(desc)) return false;
  var gauge = doorDefGetDetectGauge();
  var radius = Number(desc.radius) || 0;
  var radiusMin = Math.max(40, 200 - gauge * 1.5);
  var radiusMax = 3000 + gauge * 60;
  if (!(radius > radiusMin && radius < radiusMax)) return false;
  var sweep = desc.sweep;
  if (sweep != null && isFinite(sweep)) {
    var sweepMin = Math.max(5, 35 - gauge * 0.28);
    var sweepMax = Math.min(360, 220 + gauge * 1.25);
    if (sweep < sweepMin || sweep > sweepMax) return false;
  }
  var center = desc.arc_center || desc.centroid;
  if (!center) return false;
  var bid = desc.ent && desc.ent.block_insert_id != null ? String(desc.ent.block_insert_id) : '';
  var groupKey = doorDefEntityBlockGroupKey(desc.ent);
  if (groupKey && (blockEntityCount[groupKey] || 0) >= 2) return true;
  if (bid && (blockEntityCount[bid] || 0) >= 2) return true;
  var a0 = desc.arc_start;
  var a1 = desc.arc_end;
  var neighborR = Math.max(120, radius * (1.45 + gauge / 110));
  var neighborTol = Math.max(70, radius * (0.32 + gauge / 700));
  var arcPool = doorDefSpatialPool(idx, 'ARC', center, neighborR);
  for (var i = 0; i < arcPool.length; i++) {
    var cand = arcPool[i];
    if (!cand || cand.id === desc.id) continue;
    var cr = Number(cand.radius) || 0;
    if (!(cr > 0)) continue;
    var ccenter = cand.arc_center || cand.centroid;
    if (!ccenter) continue;
    var cd = pointDist(center, ccenter);
    var radiusNear = Math.abs(cr - radius) <= neighborTol;
    var spanNear = isFinite(cd) && Math.abs(cd - (cr + radius)) <= Math.max(90, radius * 0.48);
    if (!(radiusNear || spanNear)) continue;
    if (doorDefArcPairLikelyDouble(desc, cand)) return true;
    if (cd <= Math.max(160, radius * 0.52)) return true;
  }
  if (a0 && a1) {
    var chord = pointDist(a0, a1);
    if (isFinite(chord) && chord >= Math.max(40, radius * 0.22)) return true;
  }
  if (sweep != null && isFinite(sweep) && sweep >= Math.max(18, 30 - gauge * 0.12)) return true;
  return gauge >= 92;
}
function doorDefIsOpeningArcCandidateRelaxed(desc) {
  if (!desc || desc.type !== 'ARC') return false;
  if (doorDefArcLikelyNonDoorContext(desc)) return false;
  var gauge = doorDefGetDetectGauge();
  if (gauge < 20) return false;
  var radius = Number(desc.radius) || 0;
  var radiusMin = Math.max(10, 140 - gauge * 1.1);
  var radiusMax = 5200 + gauge * 70;
  if (!(radius > radiusMin && radius < radiusMax)) return false;
  var sweep = desc.sweep;
  if (sweep != null && isFinite(sweep)) {
    var sweepMin = Math.max(2, 20 - gauge * 0.22);
    var sweepMax = Math.min(360, 300 + gauge * 0.6);
    if (sweep < sweepMin || sweep > sweepMax) return false;
  }
  return true;
}
function doorDefIsDoorSwingArc(desc, gauge) {
  if (!desc || desc.type !== 'ARC') return false;
  var g = Number(gauge);
  if (!isFinite(g)) g = doorDefGetDetectGauge();
  var radius = Number(desc.radius) || 0;
  if (!(radius > 0)) return false;
  var sweep = desc.sweep != null ? Math.abs(Number(desc.sweep)) : NaN;
  var minSweep = Math.max(45, 72 - (g * 0.25));
  var maxSweep = 190;
  if (isFinite(sweep)) {
    if (sweep < minSweep || sweep > maxSweep) return false;
  }
  if (desc.arc_start && desc.arc_end) {
    var chord = pointDist(desc.arc_start, desc.arc_end);
    if (isFinite(chord) && chord > 0) {
      var minChord = radius * 0.75;
      if (chord < minChord) return false;
    }
  }
  return true;
}
function doorDefNormalizeDoorArcGroup(arcs, gauge) {
  var raw = doorDefDedupArcList(arcs || []);
  var pair = doorDefFindLikelyDoubleArcPair(raw);
  if (pair.length === 2) {
    pair.sort(function(a, b) {
      return (Number(b.radius) || 0) - (Number(a.radius) || 0);
    });
    return pair;
  }
  var list = raw.filter(function(a) {
    return doorDefIsDoorSwingArc(a, gauge);
  });
  if (!list.length) return [];
  list.sort(function(a, b) {
    return (Number(b.radius) || 0) - (Number(a.radius) || 0);
  });
  var mainR = Number(list[0].radius) || 0;
  if (mainR > 0) {
    list = list.filter(function(a) {
      var r = Number(a.radius) || 0;
      if (!(r > 0)) return false;
      return r >= (mainR * 0.62) && r <= (mainR * 1.45);
    });
  }
  if (list.length > 2) list = list.slice(0, 2);
  return list;
}
function doorDefFindPartialOpenArcInGroup(arcs, gauge) {
  var raw = doorDefDedupArcList(arcs || []);
  if (!raw.length) return null;
  var list = raw.filter(function(a) { return doorDefIsPartialOpenDoorArcCandidate(a, gauge); });
  if (!list.length) return null;
  list.sort(function(a, b) {
    var rb = Math.abs(Number(b && b.radius) || 0);
    var ra = Math.abs(Number(a && a.radius) || 0);
    if (rb !== ra) return rb - ra;
    var sb = Math.abs(Number(b && b.sweep) || 0);
    var sa = Math.abs(Number(a && a.sweep) || 0);
    return sb - sa;
  });
  return list[0] || null;
}
function doorDefDedupArcList(arcs) {
  var out = [];
  for (var i = 0; i < (arcs || []).length; i++) {
    var a = arcs[i];
    if (!a) continue;
    var dup = false;
    for (var j = 0; j < out.length; j++) {
      var b = out[j];
      var cd = pointDist(a.centroid, b.centroid);
      var rd = Math.abs((a.radius || 0) - (b.radius || 0));
      var sd = (a.sweep != null && b.sweep != null) ? Math.abs((a.sweep || 0) - (b.sweep || 0)) : 0;
      if (cd <= 25 && rd <= 25 && sd <= 12) { dup = true; break; }
    }
    if (!dup) out.push(a);
  }
  return out;
}
function doorDefArcPairLikelyDouble(a, b) {
  if (!a || !b) return false;
  if (doorDefArcLikelyNonDoorContext(a) || doorDefArcLikelyNonDoorContext(b)) return false;
  var r1 = a.radius || 0;
  var r2 = b.radius || 0;
  if (!(r1 > 120) || !(r2 > 120)) return false;
  var sw1 = a.sweep != null ? Math.abs(Number(a.sweep)) : NaN;
  var sw2 = b.sweep != null ? Math.abs(Number(b.sweep)) : NaN;
  if (isFinite(sw1) && sw1 < 30) return false;
  if (isFinite(sw2) && sw2 < 30) return false;
  var ratio = Math.min(r1, r2) / Math.max(r1, r2);
  if (!isFinite(ratio) || ratio < 0.55) return false;
  var maxR = Math.max(r1, r2);
  var cd = pointDist(a.centroid, b.centroid);
  var nearSpan = isFinite(cd) && Math.abs(cd - (r1 + r2)) <= Math.max(80, maxR * 0.22);
  var endpointTol = Math.max(30, maxR * 0.10);
  var aa = [a.arc_start, a.arc_end];
  var bb = [b.arc_start, b.arc_end];
  var endpointTouch = false;
  for (var i = 0; i < aa.length; i++) {
    for (var j = 0; j < bb.length; j++) {
      if (!aa[i] || !bb[j]) continue;
      if (pointDist(aa[i], bb[j]) <= endpointTol) {
        endpointTouch = true;
        break;
      }
    }
    if (endpointTouch) break;
  }
  return endpointTouch || nearSpan;
}
function doorDefFindLikelyDoubleArcPair(arcs) {
  var list = doorDefDedupArcList(arcs || []).filter(function(a) {
    return a && (Number(a.radius) || 0) > 0;
  });
  if (list.length < 2) return [];
  var best = null;
  var bestScore = -Infinity;
  for (var i = 0; i < list.length; i++) {
    for (var j = i + 1; j < list.length; j++) {
      var a = list[i], b = list[j];
      if (!doorDefArcPairLikelyDouble(a, b)) continue;
      var score = (Number(a.radius) || 0) + (Number(b.radius) || 0);
      if (score > bestScore) {
        bestScore = score;
        best = [a, b];
      }
    }
  }
  return best || [];
}
function doorDefArcGroupLikelyDouble(arcs) {
  return doorDefFindLikelyDoubleArcPair(arcs).length === 2;
}
function doorDefEstimateOpeningWidthFromArcs(arcs) {
  var list = doorDefDedupArcList(arcs || []).filter(function(a) { return (a.radius || 0) > 0; });
  if (!list.length) return 0;
  if (list.length === 1) {
    var single = list[0].radius || 0;
    if (!(single > 0)) return 0;
    return single + Math.max(20, single * 0.04);
  }
  var best = 0;
  for (var i = 0; i < list.length; i++) {
    var baseSingle = (list[i].radius || 0) + Math.max(20, (list[i].radius || 0) * 0.04);
    if (baseSingle > best) best = baseSingle;
    for (var j = i + 1; j < list.length; j++) {
      if (!doorDefArcPairLikelyDouble(list[i], list[j])) continue;
      var sumR = (list[i].radius || 0) + (list[j].radius || 0);
      var w = sumR + Math.max(30, sumR * 0.03);
      if (w > best) best = w;
    }
  }
  return best;
}
function doorDefWidthClassMm(v) {
  var n = Number(v) || 0;
  if (!(n > 0)) return 0;
  return Math.max(1, Math.round(n / 10) * 10);
}
function doorDefOpeningKindLabel(kind) {
  var k = String(kind || '').toLowerCase();
  if (k === 'double') return '양개문';
  if (k === 'partial') return '부분개방문';
  return '문';
}
function doorDefOpeningClassKey(kind, widthClassMm) {
  return String(kind || 'single') + '|' + String(widthClassMm || 0);
}
function doorDefNormalizeWidthAdjustMm(v) {
  var n = Number(v) || 0;
  return Math.round(n / 10) * 10;
}
function doorDefGetClassWidthAdjustMm(classKey) {
  var key = String(classKey || '').trim();
  var map = (doorDefState && doorDefState.autoClassWidthAdjust && typeof doorDefState.autoClassWidthAdjust === 'object')
    ? doorDefState.autoClassWidthAdjust
    : {};
  if (!key) return 0;
  return doorDefNormalizeWidthAdjustMm(map[key] || 0);
}
function doorDefSetClassWidthAdjustMm(classKey, valueMm) {
  if (!doorDefState) return 0;
  if (!doorDefState.autoClassWidthAdjust || typeof doorDefState.autoClassWidthAdjust !== 'object') {
    doorDefState.autoClassWidthAdjust = {};
  }
  var key = String(classKey || '').trim();
  if (!key) return 0;
  var v = doorDefNormalizeWidthAdjustMm(valueMm);
  if (v > 400) v = 400;
  if (v < -400) v = -400;
  doorDefState.autoClassWidthAdjust[key] = v;
  return v;
}
function doorDefAdjustedWidthMm(baseWidthMm, classKey) {
  var base = doorDefWidthClassMm(baseWidthMm);
  if (!(base > 0)) return 0;
  var adj = doorDefGetClassWidthAdjustMm(classKey);
  return Math.max(10, doorDefWidthClassMm(base + adj));
}
function doorDefAdjustAutoClassWidth(classKey, deltaMm, silent) {
  var key = String(classKey || '').trim();
  if (!key) return false;
  var cur = doorDefGetClassWidthAdjustMm(key);
  var next = doorDefSetClassWidthAdjustMm(key, cur + (Number(deltaMm) || 0));
  doorDefRenderAutoClassList();
  if (!silent) {
    var sign = next >= 0 ? '+' : '';
    showMsg('msg', '폭 보정: ' + sign + next + 'mm', 'info');
  }
  return true;
}
function doorDefParseHierarchyPath(rawPath) {
  if (!rawPath) return [];
  if (Array.isArray(rawPath)) return rawPath.slice();
  if (typeof rawPath === 'string') {
    var s = rawPath.trim();
    if (!s) return [];
    try {
      var j = JSON.parse(s);
      if (Array.isArray(j)) return j;
    } catch (_) {}
    return [];
  }
  return [];
}
function doorDefEntityHierarchyKeys(ent) {
  var out = [];
  var seen = {};
  function pushKey(raw) {
    var k = String(raw || '').trim();
    if (!k || seen[k]) return;
    seen[k] = true;
    out.push(k);
  }
  if (!ent || ent.isBlockInsert) return out;
  var bid = (ent.block_insert_id != null) ? parseInt(ent.block_insert_id, 10) : NaN;
  var rootKey = isFinite(bid) ? ('bi:' + String(bid)) : '';
  if (rootKey) {
    pushKey(rootKey);
    pushKey(String(bid));
  }
  if (Array.isArray(ent.__bhKeys) && ent.__bhKeys.length) {
    for (var bi = 0; bi < ent.__bhKeys.length; bi++) {
      var bk = String(ent.__bhKeys[bi] || '').trim();
      if (!bk) continue;
      pushKey(bk);
      if (bk.indexOf('bh:') === 0) pushKey(bk.slice(3));
      else pushKey('bh:' + bk);
    }
  }
  var path = doorDefParseHierarchyPath(ent.props && ent.props.block_hierarchy_path);
  if (path.length) {
    var chain = rootKey;
    for (var i = 0; i < path.length; i++) {
      var seg = path[i];
      var segKey = '';
      if (seg && typeof seg === 'object') segKey = String(seg.instance_key || seg.key || '').trim();
      else segKey = String(seg || '').trim();
      if (!segKey) continue;
      pushKey(segKey);
      pushKey('bh:' + segKey);
      chain = chain ? (chain + '/' + segKey) : segKey;
      pushKey(chain);
      if (chain.indexOf('bh:') === 0) pushKey(chain.slice(3));
      else pushKey('bh:' + chain);
    }
  }
  return out;
}
function doorDefEntityHierarchyChain(ent) {
  if (!ent || ent.isBlockInsert) return [];
  if (Array.isArray(ent.__bhKeys) && ent.__bhKeys.length) return ent.__bhKeys.slice();
  var out = [];
  var bid = (ent.block_insert_id != null) ? parseInt(ent.block_insert_id, 10) : NaN;
  var rootKey = isFinite(bid) ? ('bi:' + String(bid)) : '';
  if (rootKey) out.push(rootKey);
  var path = doorDefParseHierarchyPath(ent.props && ent.props.block_hierarchy_path);
  var chain = rootKey;
  for (var i = 0; i < path.length; i++) {
    var seg = path[i];
    var segKey = '';
    if (seg && typeof seg === 'object') segKey = String(seg.instance_key || seg.key || '').trim();
    else segKey = String(seg || '').trim();
    if (!segKey) continue;
    chain = chain ? (chain + '/' + segKey) : segKey;
    out.push(chain);
  }
  return out;
}
function doorDefArcGroupCommonScopeKey(arcs) {
  var list = doorDefDedupArcList(arcs || []);
  var chains = [];
  for (var i = 0; i < list.length; i++) {
    var ent = list[i] && list[i].ent ? list[i].ent : null;
    if (!ent) continue;
    var chain = doorDefEntityHierarchyChain(ent);
    if (chain.length) chains.push(chain);
  }
  if (!chains.length) return '';
  var minLen = chains[0].length;
  for (var ci = 1; ci < chains.length; ci++) minLen = Math.min(minLen, chains[ci].length);
  if (!(minLen > 0)) return '';
  var common = '';
  for (var di = 0; di < minLen; di++) {
    var key = String(chains[0][di] || '');
    if (!key) break;
    var ok = true;
    for (var cj = 1; cj < chains.length; cj++) {
      if (String(chains[cj][di] || '') !== key) { ok = false; break; }
    }
    if (!ok) break;
    common = key;
  }
  return String(common || '').trim();
}
function doorDefEntityHasScopeKey(ent, scopeKey) {
  var sk = String(scopeKey || '').trim();
  if (!sk) return true;
  if (!ent) return false;
  var chain = doorDefEntityHierarchyChain(ent);
  for (var i = 0; i < chain.length; i++) {
    if (String(chain[i] || '').trim() === sk) return true;
  }
  return false;
}
function doorDefFilterEntityIdsByScopeKey(entityIds, idx, arcIds, scopeKey) {
  var sk = String(scopeKey || '').trim();
  var ids = doorDefUniqueEntityIds(entityIds || []);
  if (!ids.length || !sk) return ids;
  var arcKeep = {};
  for (var i = 0; i < (arcIds || []).length; i++) {
    var aid = parseInt(arcIds[i], 10);
    if (aid > 0) arcKeep[aid] = true;
  }
  var out = [];
  for (var k = 0; k < ids.length; k++) {
    var id = parseInt(ids[k], 10);
    if (!(id > 0)) continue;
    if (arcKeep[id]) { out.push(id); continue; }
    var d = idx && idx.byId ? idx.byId[String(id)] : null;
    var ent = d && d.ent ? d.ent : doorDefEntityById(id);
    if (doorDefEntityHasScopeKey(ent, sk)) out.push(id);
  }
  if (!out.length) {
    var arcOnly = [];
    for (var ai = 0; ai < (arcIds || []).length; ai++) {
      var aid2 = parseInt(arcIds[ai], 10);
      if (aid2 > 0) arcOnly.push(aid2);
    }
    return doorDefUniqueEntityIds(arcOnly);
  }
  return doorDefUniqueEntityIds(out);
}
function doorDefAugmentEntityIdsByScopeDoorLayer(entityIds, idx, arcs, widthMm, scopeKey) {
  var sk = String(scopeKey || '').trim();
  var ids = doorDefUniqueEntityIds(entityIds || []);
  if (!idx) return ids;
  var arcList = doorDefDedupArcList(arcs || []).filter(function(a) { return a && (a.id > 0); });
  if (!arcList.length) return ids;
  var idSet = {};
  for (var i = 0; i < ids.length; i++) idSet[ids[i]] = true;
  var cx = 0, cy = 0;
  for (var ai = 0; ai < arcList.length; ai++) {
    var ac = arcList[ai].arc_center || arcList[ai].centroid || { x: 0, y: 0 };
    cx += Number(ac.x) || 0;
    cy += Number(ac.y) || 0;
  }
  var center = { x: cx / Math.max(1, arcList.length), y: cy / Math.max(1, arcList.length) };
  var width = Number(widthMm) || doorDefEstimateOpeningWidthFromArcs(arcList);
  if (!(width > 0)) width = 1000;
  var includeT = doorDefIncludeExtentRatio();
  var searchR = Math.max(width * doorDefLerp(1.9, 2.8, includeT), 850);
  var maxLenOpen = Math.max(width * doorDefLerp(1.6, 3.4, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 24);
  var pool = []
    .concat(doorDefSpatialPool(idx, 'LINE', center, searchR))
    .concat(doorDefSpatialPool(idx, 'LWPOLYLINE', center, searchR))
    .concat(doorDefSpatialPool(idx, 'POLYLINE', center, searchR));
  for (var pi = 0; pi < pool.length; pi++) {
    var d = pool[pi];
    if (!d || d.id == null) continue;
    var id = Number(d.id);
    if (!(id > 0) || idSet[id]) continue;
    var ent = d.ent ? d.ent : doorDefEntityById(id);
    if (sk && !doorDefEntityHasScopeKey(ent, sk)) continue;
    var layer = String((d && d.layer) || (ent && ent.layer) || '').toUpperCase();
    if (!doorDefLayerLooksDoor(layer)) continue;
    var hex = doorDefEntityDisplayColorHex(ent);
    if (!doorDefIsDoorColorAllowed(ent, hex)) continue;
    var len = doorDefDoorLineLenMm(d, id);
    if (len <= DOOR_DEF_MIN_LINEAR_LEN_MM) continue;
    var closedLinear = doorDefIsClosedPolylineLike(d, id);
    if (!closedLinear && len > maxLenOpen) continue;
    var cc = d.centroid || null;
    if (cc && pointDist(cc, center) > searchR) continue;
    ids.push(id);
    idSet[id] = true;
  }
  return doorDefUniqueEntityIds(ids);
}
function doorDefEntityBlockGroupKey(ent) {
  if (!ent || ent.isBlockInsert) return '';
  if (ent.block_insert_id != null) return 'bi:' + String(ent.block_insert_id);
  if (Array.isArray(ent.__bhKeys) && ent.__bhKeys.length) {
    var k0 = String(ent.__bhKeys[0] || '').trim();
    if (k0) return k0.indexOf('bi:') === 0 ? k0 : ('bh:' + k0);
  }
  var path = doorDefParseHierarchyPath(ent.props && ent.props.block_hierarchy_path);
  if (!path.length) return '';
  var seg0 = path[0];
  if (seg0 && typeof seg0 === 'object') {
    var ik = String(seg0.instance_key || seg0.key || '').trim();
    if (ik) return 'bh:' + ik;
  } else {
    var sk = String(seg0 || '').trim();
    if (sk) return 'bh:' + sk;
  }
  return '';
}
function doorDefBlockInsertIdFromGroupKey(groupKey) {
  var m = String(groupKey || '').match(/^bi:(\d+)$/);
  return m ? parseInt(m[1], 10) : null;
}
function doorDefBuildBlockEntityMap() {
  var map = {};
  var cnt = {};
  function put(key, idNum) {
    var k = String(key || '').trim();
    if (!k) return;
    if (!map[k]) map[k] = [];
    map[k].push(idNum);
    cnt[k] = (cnt[k] || 0) + 1;
  }
  for (var i = 0; i < allEntities.length; i++) {
    var e = allEntities[i];
    if (!e || e.isBlockInsert || e.id == null) continue;
    var idNum = Number(e.id);
    var keys = doorDefEntityHierarchyKeys(e);
    for (var ki = 0; ki < keys.length; ki++) put(keys[ki], idNum);
    var k = doorDefEntityBlockGroupKey(e);
    if (k) put(k, idNum);
    if (e.block_insert_id != null) put(String(e.block_insert_id), idNum);
  }
  return { idsByBlock: map, countByBlock: cnt };
}
function doorDefBuildAllowedIdSet(ids) {
  var set = {};
  for (var i = 0; i < (ids || []).length; i++) {
    var n = parseInt(ids[i], 10);
    if (n > 0) set[n] = true;
  }
  return set;
}
function doorDefCollectArcGroupScopeKeys(arcs) {
  var out = [];
  var seen = {};
  function pushKey(raw) {
    var k = String(raw || '').trim();
    if (!k || seen[k]) return;
    seen[k] = true;
    out.push(k);
  }
  var list = doorDefDedupArcList(arcs || []);
  for (var i = 0; i < list.length; i++) {
    var ent = list[i] && list[i].ent ? list[i].ent : null;
    if (!ent) continue;
    var keys = doorDefEntityHierarchyKeys(ent);
    for (var k = 0; k < keys.length; k++) pushKey(keys[k]);
    var gk = doorDefEntityBlockGroupKey(ent);
    if (gk) pushKey(gk);
    if (ent.block_insert_id != null) {
      pushKey(String(ent.block_insert_id));
      pushKey('bi:' + String(ent.block_insert_id));
    }
  }
  return out;
}
function doorDefEndpointLinkCount(arcs, idx, allowedIdSet) {
  var list = doorDefDedupArcList(arcs || []);
  if (!list.length) return 0;
  var hit = 0;
  for (var i = 0; i < list.length; i++) {
    var arc = list[i];
    var radius = arc.radius || 0;
    var center = arc.arc_center || arc.centroid;
    var searchR = Math.max(80, radius * 1.05);
    var endpointTol = Math.max(20, radius * 0.08);
    var pool = []
      .concat(doorDefSpatialPool(idx, 'LINE', center, searchR))
      .concat(doorDefSpatialPool(idx, 'LWPOLYLINE', center, searchR))
      .concat(doorDefSpatialPool(idx, 'POLYLINE', center, searchR));
    var pts = [arc.arc_start, arc.arc_end];
    for (var p = 0; p < pts.length; p++) {
      var ep = pts[p];
      if (!ep) continue;
      var linked = false;
      for (var k = 0; k < pool.length; k++) {
        var cand = pool[k];
        if (!cand || cand.id === arc.id) continue;
        if (allowedIdSet && !allowedIdSet[cand.id]) continue;
        if (!cand.points || cand.points.length < 1) continue;
        var c0 = cand.points[0];
        var c1 = cand.points[cand.points.length - 1];
        if (pointDist(ep, c0) <= endpointTol || pointDist(ep, c1) <= endpointTol) {
          linked = true;
          break;
        }
      }
      if (linked) hit += 1;
    }
  }
  return hit;
}
function doorDefGatherNearbyEntityIdsForArcGroup(arcs, idx, opts) {
  var cfg = opts || {};
  var ids = {};
  var allowedIdSet = cfg.allowedIdSet || null;
  var maxCount = cfg.maxCount > 0 ? cfg.maxCount : 10;
  var widthLimitMm = Number(cfg.widthLimitMm) || 0;
  var relaxed = !!cfg.relaxed;
  var includeT = doorDefIncludeExtentRatio();
  var nearT = doorDefArcNearTightRatio();
  var strictScale = doorDefStrictTightnessScale(includeT, nearT);
  var nearTolScale = doorDefLerp(1.22, 0.40, nearT) * strictScale;
  var list = doorDefDedupArcList(arcs || []);
  var centers = [];
  var radii = [];
  var arcEndpoints = [];
  for (var i = 0; i < list.length; i++) {
    var a = list[i];
    if (!a) continue;
    ids[a.id] = true;
    centers.push(a.arc_center || a.centroid);
    if ((a.radius || 0) > 0) radii.push(a.radius || 0);
    if (a.arc_start) arcEndpoints.push(a.arc_start);
    if (a.arc_end) arcEndpoints.push(a.arc_end);
  }
  if (!centers.length) return [];
  var cx = 0, cy = 0;
  for (var c = 0; c < centers.length; c++) { cx += centers[c].x; cy += centers[c].y; }
  var center = { x: cx / centers.length, y: cy / centers.length };
  var maxR = 0;
  for (var r = 0; r < radii.length; r++) if (radii[r] > maxR) maxR = radii[r];
  if (!(maxR > 0)) maxR = 900;
  var arcInfos = [];
  for (var ai0 = 0; ai0 < list.length; ai0++) {
    var info0 = doorDefBuildArcSweepInfo(list[ai0]);
    if (info0) arcInfos.push(info0);
  }
  var gatherR = Math.max(24, (maxR * doorDefLerp(0.58, 1.18, includeT) + doorDefLerp(2, 30, includeT)) * doorDefLerp(1.02, 0.56, nearT) * strictScale);
  var endpointTol = Math.max(4, maxR * (relaxed ? doorDefLerp(0.022, 0.11, includeT) : doorDefLerp(0.010, 0.06, includeT)) * nearTolScale);
  var hubTol = Math.max(5, maxR * (relaxed ? doorDefLerp(0.05, 0.20, includeT) : doorDefLerp(0.03, 0.13, includeT)) * nearTolScale);
  var bandTol = Math.max(6, maxR * (relaxed ? doorDefLerp(0.045, 0.16, includeT) : doorDefLerp(0.03, 0.09, includeT)) * nearTolScale);
  var adjTol = Math.max(5, Math.min(95, (widthLimitMm > 0 ? widthLimitMm : maxR) * (relaxed ? doorDefLerp(0.06, 0.21, includeT) : doorDefLerp(0.045, 0.13, includeT)) * nearTolScale));
  var supportEndpoints = arcEndpoints.slice();
  var types = ['LINE', 'LWPOLYLINE', 'POLYLINE'];
  function inAnyArcSector(pt) {
    if (!pt) return false;
    if (!arcInfos.length) return true;
    var opts = relaxed
      ? {
          radialTolOut: Math.max(7, maxR * doorDefLerp(0.07, 0.28, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 18, Math.PI / 6, includeT) * doorDefLerp(1.0, 0.72, nearT)
        }
      : {
          radialTolOut: Math.max(3, maxR * doorDefLerp(0.02, 0.10, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 34, Math.PI / 16, includeT) * doorDefLerp(1.0, 0.74, nearT)
        };
    for (var si = 0; si < arcInfos.length; si++) {
      if (doorDefPointInArcSweep(pt, arcInfos[si], opts)) return true;
    }
    return false;
  }
  function inAnyArcSectorStrict(pt) {
    if (!pt) return false;
    if (!arcInfos.length) return true;
    var opts = relaxed
      ? {
          radialTolOut: Math.max(4, maxR * doorDefLerp(0.03, 0.18, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 26, Math.PI / 10, includeT) * doorDefLerp(1.0, 0.72, nearT)
        }
      : {
          radialTolOut: Math.max(1.5, maxR * doorDefLerp(0.008, 0.04, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 60, Math.PI / 24, includeT) * doorDefLerp(1.0, 0.72, nearT)
        };
    for (var si = 0; si < arcInfos.length; si++) {
      if (doorDefPointInArcSweep(pt, arcInfos[si], opts)) return true;
    }
    return false;
  }
  function endpointNearAny(pt) {
    if (!pt || !arcEndpoints.length) return false;
    for (var ep = 0; ep < arcEndpoints.length; ep++) {
      var aep = arcEndpoints[ep];
      if (pointDist(aep, pt) <= endpointTol) return true;
    }
    return false;
  }
  function nearAnyArcBand(pt) {
    if (!pt || !list.length) return false;
    for (var ai = 0; ai < list.length; ai++) {
      var a = list[ai];
      var ac = a.arc_center || a.centroid;
      var ar = a.radius || 0;
      if (!(ar > 0)) continue;
      var d = pointDist(ac, pt);
      if (isFinite(d) && Math.abs(d - ar) <= bandTol) return true;
    }
    return false;
  }
  function nearAnyArcCenter(pt) {
    if (!pt || !list.length) return false;
    for (var ai = 0; ai < list.length; ai++) {
      var a = list[ai];
      var cc = a.arc_center || a.centroid;
      if (!cc) continue;
      if (pointDist(cc, pt) <= hubTol) return true;
    }
    return false;
  }
  function nearSupportEndpoint(pt) {
    if (!pt || !supportEndpoints.length) return false;
    for (var i = 0; i < supportEndpoints.length; i++) {
      if (pointDist(supportEndpoints[i], pt) <= adjTol) return true;
    }
    return false;
  }
  function pushSupportPoint(pt) {
    if (!pt) return;
    supportEndpoints.push(pt);
  }
  function polylineSampleInStrictSector(desc) {
    var pts = desc && desc.points && desc.points.length ? desc.points : null;
    if (!pts || pts.length <= 2) return true;
    var n = pts.length;
    var step = Math.max(1, Math.floor((n - 1) / 8));
    var hit = 0;
    var total = 0;
    for (var i = 0; i < n; i += step) {
      total += 1;
      if (inAnyArcSectorStrict(pts[i])) hit += 1;
    }
    total += 1;
    if (inAnyArcSectorStrict(pts[n - 1])) hit += 1;
    if (!relaxed) return hit === total;
    var keepRatio = Math.min(1, doorDefLerp(0.88, 0.24, includeT) + (Math.min(1, nearT) * 0.22));
    return hit >= Math.max(1, Math.ceil(total * keepRatio));
  }
  function filterLenMm(desc) {
    return doorDefDoorLineLenMm(desc, desc && desc.id != null ? Number(desc.id) : 0);
  }
  for (var ti = 0; ti < types.length; ti++) {
    var pool = doorDefSpatialPool(idx, types[ti], center, gatherR);
    for (var pi = 0; pi < pool.length; pi++) {
      var d = pool[pi];
      if (!d || d.id == null) continue;
      if (allowedIdSet && !allowedIdSet[d.id]) continue;
      var dist = pointDist(center, d.centroid);
      if (!isFinite(dist) || dist > gatherR) continue;
      if (!d.points || d.points.length < 1) continue;
      var p0 = d.points[0];
      var p1 = d.points[d.points.length - 1];
      var closedLinear = doorDefIsClosedPolylineLike(d, d.id);
      var pm = (p0 && p1) ? { x: ((Number(p0.x) || 0) + (Number(p1.x) || 0)) * 0.5, y: ((Number(p0.y) || 0) + (Number(p1.y) || 0)) * 0.5 } : null;
      var p0Strict = p0 ? inAnyArcSectorStrict(p0) : false;
      var p1Strict = p1 ? inAnyArcSectorStrict(p1) : false;
      if (!relaxed) {
        if (p0 && !p0Strict) continue;
        if (p1 && !p1Strict) continue;
      } else {
        if (p0 && p1 && !p0Strict && !p1Strict) {
          var cIn = inAnyArcSector(d.centroid);
          var mIn = inAnyArcSector(pm);
          if (!cIn && !mIn) {
            var endpointHint = endpointNearAny(p0) || endpointNearAny(p1);
            var bandHint = nearAnyArcBand(p0) || nearAnyArcBand(p1) || nearAnyArcBand(pm);
            if (!(includeT >= 0.40 && endpointHint && (bandHint || closedLinear || includeT >= 0.62))) continue;
          }
        }
      }
      if (!polylineSampleInStrictSector(d)) {
        if (!(relaxed && includeT >= 0.45 && closedLinear)) continue;
      }
      var len = filterLenMm(d);
      if (len <= DOOR_DEF_MIN_LINEAR_LEN_MM) continue;
      var supportLenMax = Math.max(
        DOOR_DEF_MIN_LINEAR_LEN_MM + 18,
        (widthLimitMm > 0 ? widthLimitMm : maxR) * (relaxed ? 0.72 : 0.58)
      );
      var lenLimitMul = (relaxed ? doorDefLerp(0.96, 1.48, includeT) : doorDefLerp(0.72, 0.98, includeT)) * doorDefLerp(0.98, 0.74, nearT) * strictScale;
      var lenLimit = widthLimitMm > 0 ? (widthLimitMm * lenLimitMul) : 0;
      if (!closedLinear && lenLimit > 0 && len > lenLimit) continue;
      if (!closedLinear && len > Math.max(doorDefLerp(1100, 3000, includeT) * doorDefLerp(1.00, 0.74, nearT) * strictScale, maxR * doorDefLerp(1.10, 1.95, includeT) * doorDefLerp(0.98, 0.76, nearT) * strictScale)) continue;
      var nearEndpoint = endpointNearAny(p0) || endpointNearAny(p1);
      var nearBand = nearAnyArcBand(p0) || nearAnyArcBand(p1) || nearAnyArcBand(d.centroid);
      var nearCenterEnd = nearAnyArcCenter(p0) || nearAnyArcCenter(p1);
      var nearSupportRaw = nearSupportEndpoint(p0) || nearSupportEndpoint(p1);
      var nearSupport = nearSupportRaw && (closedLinear || (len <= supportLenMax));
      var endpointSector = inAnyArcSector(p0) || inAnyArcSector(p1);
      var centroidSector = inAnyArcSector(d.centroid);
      var midSector = inAnyArcSector(pm);
      if (!(endpointSector || centroidSector || midSector)) {
        if (!(relaxed && (nearEndpoint || nearSupport))) continue;
      }
      var bodySector = centroidSector || midSector;
      var primaryGate = nearEndpoint || (nearBand && (nearCenterEnd || nearSupport));
      if (relaxed && !primaryGate) {
        if (includeT >= 0.55 && nearT <= 0.65) primaryGate = nearBand && (bodySector || nearSupport);
        else primaryGate = nearBand && bodySector && (nearSupport || nearCenterEnd);
      }
      if (!primaryGate) continue;
      var keepByEndpoint = nearEndpoint && endpointSector && bodySector;
      var keepByBand = nearBand && nearCenterEnd && bodySector;
      var keepByAdj = nearBand && nearSupport && bodySector;
      if (relaxed && includeT >= 0.55 && nearT <= 0.65 && !keepByEndpoint && nearEndpoint && (endpointSector || bodySector)) keepByEndpoint = true;
      var keep = keepByEndpoint || keepByBand || keepByAdj;
      if (keep) {
        ids[d.id] = true;
        pushSupportPoint(p0);
        pushSupportPoint(p1);
      }
    }
  }
  var arcIds = [];
  var arcSet = {};
  for (var ati = 0; ati < list.length; ati++) {
    var arcSelf = list[ati];
    if (!arcSelf || arcSelf.id == null) continue;
    ids[arcSelf.id] = true;
    arcSet[arcSelf.id] = true;
    arcIds.push(arcSelf.id);
  }
  arcIds = doorDefUniqueEntityIds(arcIds);
  var arr = Object.keys(ids).map(function(k) { return parseInt(k, 10); }).filter(function(n) { return n > 0 && !arcSet[n]; });
  arr.sort(function(a, b) {
    var ea = doorDefEntityById(a);
    var eb = doorDefEntityById(b);
    var da = ea ? pointDist(center, doorDefEntityCenter(ea)) : Infinity;
    var db = eb ? pointDist(center, doorDefEntityCenter(eb)) : Infinity;
    return da - db;
  });
  var remain = Math.max(0, maxCount - arcIds.length);
  return doorDefUniqueEntityIds(arcIds.concat(arr.slice(0, remain)));
}
function doorDefPruneOpeningEntityIdsByWidth(entityIds, widthLimitMm, idx, arcIds, opts) {
  var cfg = opts || {};
  var relaxed = !!cfg.relaxed;
  var includeT = doorDefIncludeExtentRatio();
  var nearT = doorDefArcNearTightRatio();
  var strictScale = doorDefStrictTightnessScale(includeT, nearT);
  var nearTolScale = doorDefLerp(1.20, 0.40, nearT) * strictScale;
  var ids = doorDefUniqueEntityIds(entityIds || []);
  var limit = Number(widthLimitMm) || 0;
  if (!ids.length || !(limit > 0)) return ids;
  var maxLen = limit * (relaxed ? doorDefLerp(0.94, 1.44, includeT) : doorDefLerp(0.72, 0.98, includeT)) * doorDefLerp(0.98, 0.74, nearT) * strictScale;
  var hubTol = Math.max(5, limit * (relaxed ? doorDefLerp(0.05, 0.19, includeT) : doorDefLerp(0.03, 0.12, includeT)) * nearTolScale);
  var adjTol = Math.max(5, Math.min(relaxed ? 95 : 75, limit * (relaxed ? doorDefLerp(0.06, 0.21, includeT) : doorDefLerp(0.045, 0.13, includeT)) * nearTolScale));
  var arcInfos = [];
  var arcEndpoints = [];
  for (var ai = 0; ai < (arcIds || []).length; ai++) {
    var aid0 = parseInt(arcIds[ai], 10);
    if (!(aid0 > 0)) continue;
    var ad0 = idx && idx.byId ? idx.byId[String(aid0)] : null;
    if (!ad0 || ad0.type !== 'ARC') continue;
    var info0 = doorDefBuildArcSweepInfo(ad0);
    if (info0) arcInfos.push(info0);
    if (ad0.arc_start) arcEndpoints.push(ad0.arc_start);
    if (ad0.arc_end) arcEndpoints.push(ad0.arc_end);
  }
  var supportEndpoints = arcEndpoints.slice();
  function inAnyArcSector(pt) {
    if (!pt) return false;
    if (!arcInfos.length) return true;
    var opts = relaxed
      ? {
          radialTolOut: Math.max(7, limit * doorDefLerp(0.07, 0.26, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 18, Math.PI / 6, includeT) * doorDefLerp(1.0, 0.72, nearT)
        }
      : {
          radialTolOut: Math.max(3, limit * doorDefLerp(0.015, 0.09, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 34, Math.PI / 16, includeT) * doorDefLerp(1.0, 0.74, nearT)
        };
    for (var si = 0; si < arcInfos.length; si++) {
      if (doorDefPointInArcSweep(pt, arcInfos[si], opts)) return true;
    }
    return false;
  }
  function inAnyArcSectorStrict(pt) {
    if (!pt) return false;
    if (!arcInfos.length) return true;
    var opts = relaxed
      ? {
          radialTolOut: Math.max(4, limit * doorDefLerp(0.03, 0.17, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 26, Math.PI / 10, includeT) * doorDefLerp(1.0, 0.72, nearT)
        }
      : {
          radialTolOut: Math.max(1.5, limit * doorDefLerp(0.008, 0.04, includeT) * nearTolScale),
          angleTolRad: doorDefLerp(Math.PI / 60, Math.PI / 24, includeT) * doorDefLerp(1.0, 0.72, nearT)
        };
    for (var si = 0; si < arcInfos.length; si++) {
      if (doorDefPointInArcSweep(pt, arcInfos[si], opts)) return true;
    }
    return false;
  }
  function endpointNearAny(pt) {
    if (!pt || !arcEndpoints.length) return false;
    var tol = Math.max(4, limit * doorDefLerp(0.015, 0.08, includeT) * nearTolScale);
    for (var i = 0; i < arcEndpoints.length; i++) {
      var ep = arcEndpoints[i];
      if (pointDist(ep, pt) <= tol) return true;
    }
    return false;
  }
  function nearAnyArcCenter(pt) {
    if (!pt || !arcInfos.length) return false;
    for (var i = 0; i < arcInfos.length; i++) {
      var cc = arcInfos[i].center;
      if (!cc) continue;
      if (pointDist(cc, pt) <= hubTol) return true;
    }
    return false;
  }
  function nearAnyArcBand(pt) {
    if (!pt || !arcInfos.length) return false;
    var bandTol = Math.max(5, limit * doorDefLerp(0.025, 0.11, includeT) * nearTolScale);
    for (var i = 0; i < arcInfos.length; i++) {
      var ai = arcInfos[i];
      var c = ai.center;
      var r = Number(ai.radius) || 0;
      if (!(r > 0)) continue;
      var d = pointDist(c, pt);
      if (isFinite(d) && Math.abs(d - r) <= bandTol) return true;
    }
    return false;
  }
  function nearSupportEndpoint(pt) {
    if (!pt || !supportEndpoints.length) return false;
    for (var i = 0; i < supportEndpoints.length; i++) {
      if (pointDist(supportEndpoints[i], pt) <= adjTol) return true;
    }
    return false;
  }
  function pushSupportPoint(pt) {
    if (!pt) return;
    supportEndpoints.push(pt);
  }
  function polylineSampleInStrictSector(desc) {
    var pts = desc && desc.points && desc.points.length ? desc.points : null;
    if (!pts || pts.length <= 2) return true;
    var n = pts.length;
    var step = Math.max(1, Math.floor((n - 1) / 8));
    var hit = 0;
    var total = 0;
    for (var i = 0; i < n; i += step) {
      total += 1;
      if (inAnyArcSectorStrict(pts[i])) hit += 1;
    }
    total += 1;
    if (inAnyArcSectorStrict(pts[n - 1])) hit += 1;
    if (!relaxed) return hit === total;
    var keepRatio = Math.min(1, doorDefLerp(0.86, 0.24, includeT) + (Math.min(1, nearT) * 0.22));
    return hit >= Math.max(1, Math.ceil(total * keepRatio));
  }
  function filterLenMm(d, id) {
    return doorDefDoorLineLenMm(d, id);
  }
  var arcKeepSet = {};
  for (var i = 0; i < (arcIds || []).length; i++) {
    var aid = parseInt(arcIds[i], 10);
    if (aid > 0) arcKeepSet[aid] = true;
  }
  var out = [];
  for (var k = 0; k < ids.length; k++) {
    var id = parseInt(ids[k], 10);
    if (!(id > 0)) continue;
    if (arcKeepSet[id]) {
      out.push(id);
      continue;
    }
    var d = idx && idx.byId ? idx.byId[String(id)] : null;
    if (!d) {
      out.push(id);
      continue;
    }
    if (d.type === 'ARC') {
      out.push(id);
      continue;
    }
    var pts = d.points && d.points.length ? d.points : null;
    if ((!pts || pts.length < 1) && id > 0) {
      var ent0 = doorDefEntityById(id);
      if (ent0 && ent0.points && ent0.points.length) pts = ent0.points;
    }
    var p0 = (pts && pts.length) ? pts[0] : null;
    var p1 = (pts && pts.length) ? pts[pts.length - 1] : null;
    var closedLinear = doorDefIsClosedPolylineLike(d, id);
    var pm = (p0 && p1) ? { x: ((Number(p0.x) || 0) + (Number(p1.x) || 0)) * 0.5, y: ((Number(p0.y) || 0) + (Number(p1.y) || 0)) * 0.5 } : null;
    var p0Strict = p0 ? inAnyArcSectorStrict(p0) : false;
    var p1Strict = p1 ? inAnyArcSectorStrict(p1) : false;
    if (!relaxed) {
      if (p0 && !p0Strict) continue;
      if (p1 && !p1Strict) continue;
    } else {
      if (p0 && p1 && !p0Strict && !p1Strict) {
        var cIn = inAnyArcSector(d.centroid);
        var mIn = inAnyArcSector(pm);
        if (!cIn && !mIn) {
          var endpointHint2 = endpointNearAny(p0) || endpointNearAny(p1);
          var bandHint2 = nearAnyArcBand(p0) || nearAnyArcBand(p1) || nearAnyArcBand(pm);
          if (!(includeT >= 0.40 && endpointHint2 && (bandHint2 || closedLinear || includeT >= 0.62))) continue;
        }
      }
    }
    if (!polylineSampleInStrictSector(d)) {
      if (!(relaxed && includeT >= 0.45 && closedLinear)) continue;
    }
    var endpointSector = inAnyArcSector(p0) || inAnyArcSector(p1);
    var centroidSector = inAnyArcSector(d.centroid);
    var midSector = inAnyArcSector(pm);
    var len = filterLenMm(d, id);
    if (len <= DOOR_DEF_MIN_LINEAR_LEN_MM) continue;
    var supportLenMax = Math.max(
      DOOR_DEF_MIN_LINEAR_LEN_MM + 18,
      limit * (relaxed ? 0.72 : 0.58)
    );
    var nearEndpoint = endpointNearAny(p0) || endpointNearAny(p1);
    var nearCenterEnd = nearAnyArcCenter(p0) || nearAnyArcCenter(p1);
    var nearBand = nearAnyArcBand(p0) || nearAnyArcBand(p1) || nearAnyArcBand(d.centroid);
    var nearSupportRaw = nearSupportEndpoint(p0) || nearSupportEndpoint(p1);
    var nearSupport = nearSupportRaw && (closedLinear || (len <= supportLenMax));
    if (!(endpointSector || centroidSector || midSector)) {
      if (!(relaxed && (nearEndpoint || nearSupport))) continue;
    }
    var primaryGate = nearEndpoint || (nearBand && (nearCenterEnd || nearSupport));
    if (relaxed && !primaryGate) {
      if (includeT >= 0.55 && nearT <= 0.65) primaryGate = nearBand && (centroidSector || midSector || nearSupport);
      else primaryGate = nearBand && (centroidSector || midSector) && (nearSupport || nearCenterEnd);
    }
    if (!primaryGate) continue;
    if (!closedLinear && len > 0 && len > maxLen) continue;
    out.push(id);
    pushSupportPoint(p0);
    pushSupportPoint(p1);
  }
  return doorDefUniqueEntityIds(out);
}
function doorDefCountLinearSupportEntities(entityIds, idx, minLengthMm, maxLengthMm) {
  var ids = doorDefUniqueEntityIds(entityIds || []);
  var minLen = Number(minLengthMm) || 0;
  var maxLen = Number(maxLengthMm) || 0;
  if (minLen < 0) minLen = 0;
  if (maxLen > 0 && maxLen < minLen) maxLen = minLen;
  function filterLenMm(d, id) {
    return doorDefDoorLineLenMm(d, id);
  }
  var cnt = 0;
  for (var i = 0; i < ids.length; i++) {
    var id = parseInt(ids[i], 10);
    if (!(id > 0)) continue;
    var d = idx && idx.byId ? idx.byId[String(id)] : null;
    if (!doorDefIsLinearLikeEntity(d, id)) continue;
    var len = filterLenMm(d, id);
    var closedLinear = doorDefIsClosedPolylineLike(d, id);
    if (len <= (DOOR_DEF_MIN_LINEAR_LEN_MM + 1e-6)) continue;
    if (minLen > 0 && !(len >= minLen)) continue;
    if (maxLen > 0 && !closedLinear && len > maxLen) continue;
    cnt += 1;
  }
  return cnt;
}
function doorDefRefineOpeningEntityIdsByArcRelation(entityIds, idx, arcs, kind, widthMm) {
  var ids = doorDefUniqueEntityIds(entityIds || []);
  var arcList = doorDefDedupArcList(arcs || []).filter(function(a) { return a && (a.id > 0); });
  if (!ids.length || !arcList.length) return ids;
  var kindRaw = String(kind || 'single').toLowerCase();
  var kindHint = kindRaw === 'double' ? 'double' : (kindRaw === 'partial' ? 'partial' : 'single');
  var width = Number(widthMm) || doorDefEstimateOpeningWidthFromArcs(arcList);
  if (!(width > 0)) width = 1000;
  var includeT = doorDefIncludeExtentRatio();
  var nearT = doorDefArcNearTightRatio();
  var scopeKeyRef = doorDefArcGroupCommonScopeKey(arcList);
  var arcInfos = [];
  var arcEndpoints = [];
  var cx = 0, cy = 0;
  for (var i = 0; i < arcList.length; i++) {
    var a = arcList[i];
    cx += Number(a.centroid && a.centroid.x) || 0;
    cy += Number(a.centroid && a.centroid.y) || 0;
    var info = doorDefBuildArcSweepInfo(a);
    if (info) arcInfos.push(info);
    if (a.arc_start) arcEndpoints.push(a.arc_start);
    if (a.arc_end) arcEndpoints.push(a.arc_end);
  }
  var arcCenter = { x: cx / Math.max(1, arcList.length), y: cy / Math.max(1, arcList.length) };
  var mainArc = null;
  for (var mi = 0; mi < arcList.length; mi++) {
    if (!mainArc || (Number(arcList[mi].radius) || 0) > (Number(mainArc.radius) || 0)) mainArc = arcList[mi];
  }
  var mainCenter = mainArc ? (mainArc.arc_center || mainArc.centroid || null) : null;
  var singleForward = null;
  if (mainArc && mainCenter) {
    var ms = mainArc.arc_start || null;
    var me = mainArc.arc_end || null;
    var mm = mainArc.arc_mid || null;
    if (ms && me) mm = { x: (ms.x + me.x) * 0.5, y: (ms.y + me.y) * 0.5 };
    if (mm) singleForward = { x: (mm.x - mainCenter.x), y: (mm.y - mainCenter.y) };
  }
  var pair = doorDefFindLikelyDoubleArcPair(arcList);
  var meet = null;
  if (pair.length === 2) {
    var aPts = [pair[0].arc_start, pair[0].arc_end];
    var bPts = [pair[1].arc_start, pair[1].arc_end];
    var bestD = Infinity;
    for (var ai = 0; ai < aPts.length; ai++) {
      for (var bi = 0; bi < bPts.length; bi++) {
        var ap = aPts[ai], bp = bPts[bi];
        if (!ap || !bp) continue;
        var dd = pointDist(ap, bp);
        if (dd < bestD) {
          bestD = dd;
          meet = { x: (ap.x + bp.x) * 0.5, y: (ap.y + bp.y) * 0.5 };
        }
      }
    }
  }
  if (!meet) meet = (kindHint !== 'double' && mainCenter) ? { x: mainCenter.x, y: mainCenter.y } : arcCenter;
  var axis = { x: meet.x - arcCenter.x, y: meet.y - arcCenter.y };
  if (kindHint !== 'double' && singleForward) axis = { x: singleForward.x, y: singleForward.y };
  var axisLen = Math.hypot(axis.x, axis.y);
  if (!(axisLen > 1e-9)) axis = { x: 1, y: 0 };
  else axis = { x: axis.x / axisLen, y: axis.y / axisLen };
  function inStrictSector(pt) {
    if (!pt || !arcInfos.length) return false;
    for (var s = 0; s < arcInfos.length; s++) {
      if (doorDefPointInArcSweep(pt, arcInfos[s], {
        radialTolOut: Math.max(1.5, width * 0.015),
        angleTolRad: Math.PI / 42
      })) return true;
    }
    return false;
  }
  function nearArcEndpoint(pt) {
    if (!pt) return false;
    var tol = Math.max(8, width * doorDefLerp(0.09, 0.16, includeT) * doorDefLerp(1.0, 0.84, nearT));
    for (var e = 0; e < arcEndpoints.length; e++) {
      if (pointDist(pt, arcEndpoints[e]) <= tol) return true;
    }
    return false;
  }
  function nearArcBand(pt) {
    if (!pt || !arcInfos.length) return false;
    for (var s = 0; s < arcInfos.length; s++) {
      if (doorDefPointInArcSweep(pt, arcInfos[s], {
        radialTolOut: Math.max(6, width * doorDefLerp(0.07, 0.16, includeT) * doorDefLerp(1.0, 0.86, nearT)),
        angleTolRad: doorDefLerp(Math.PI / 32, Math.PI / 20, includeT)
      })) return true;
    }
    return false;
  }
  function directionalOk(pt) {
    if (!pt) return false;
    var vx = pt.x - meet.x;
    var vy = pt.y - meet.y;
    var proj = vx * axis.x + vy * axis.y;
    var lat = Math.abs(vx * (-axis.y) + vy * axis.x);
    var projMin = -width * doorDefLerp(0.42, 0.56, includeT);
    var projMax = width * doorDefLerp(1.08, 1.30, includeT);
    var latMax = width * doorDefLerp(0.72, 0.98, includeT);
    return proj >= projMin && proj <= projMax && lat <= latMax;
  }
  function directionalOkSingle(pt) {
    if (!pt) return false;
    var vx = pt.x - meet.x;
    var vy = pt.y - meet.y;
    var proj = vx * axis.x + vy * axis.y;
    var lat = Math.abs(vx * (-axis.y) + vy * axis.x);
    var projMin = -width * doorDefLerp(0.08, 0.20, includeT);
    var projMax = width * doorDefLerp(1.25, 1.55, includeT);
    var latMax = width * doorDefLerp(0.92, 1.20, includeT);
    return proj >= projMin && proj <= projMax && lat <= latMax;
  }
  var arcKeep = {};
  for (var aidx = 0; aidx < arcList.length; aidx++) arcKeep[arcList[aidx].id] = true;
  var out = [];
  for (var k = 0; k < ids.length; k++) {
    var id = parseInt(ids[k], 10);
    if (!(id > 0)) continue;
    if (arcKeep[id]) { out.push(id); continue; }
    var d = idx && idx.byId ? idx.byId[String(id)] : null;
    if (!doorDefIsLinearLikeEntity(d, id)) { out.push(id); continue; }
    var entRef = d && d.ent ? d.ent : doorDefEntityById(id);
    var sameScopeRef = doorDefEntityHasScopeKey(entRef, scopeKeyRef);
    var layerRef = String((d && d.layer) || (entRef && entRef.layer) || '').toUpperCase();
    var isDoorLayerRef = doorDefLayerLooksDoor(layerRef);
    var isFloorStraRef = layerRef.indexOf('A-FLOR-STRA') >= 0;
    var len = doorDefDoorLineLenMm(d, id);
    if (len <= (DOOR_DEF_MIN_LINEAR_LEN_MM + 1e-6)) continue;
    var pts = doorDefGetEntityPointsByDescOrId(d, id);
    var p0 = pts && pts.length ? pts[0] : null;
    var p1 = pts && pts.length ? pts[pts.length - 1] : null;
    var type = doorDefGetEntityTypeByDescOrId(d, id);
    var closedLike = false;
    if ((type === 'LWPOLYLINE' || type === 'POLYLINE') && pts && pts.length >= 3 && p0 && p1) {
      var bbP = pointListBBox(pts, pts[0]);
      var spanP = Math.max(bbP.w || 0, bbP.h || 0);
      var closeTolP = Math.max(1, spanP * 0.03);
      closedLike = pointDist(p0, p1) <= closeTolP;
    }
    var pc = (p0 && p1) ? { x: (p0.x + p1.x) * 0.5, y: (p0.y + p1.y) * 0.5 } : (d && d.centroid ? d.centroid : null);
    var strictHit = (inStrictSector(p0) ? 1 : 0) + (inStrictSector(p1) ? 1 : 0) + (inStrictSector(pc) ? 1 : 0);
    var bandHit = nearArcBand(p0) || nearArcBand(p1) || nearArcBand(pc);
    var nearEnd = nearArcEndpoint(p0) || nearArcEndpoint(p1);
    if (kindHint === 'double') {
      var dirKeep = directionalOk(pc) || directionalOk(p0) || directionalOk(p1);
      if (strictHit > 0 || nearEnd || dirKeep || bandHit) {
        if (len <= Math.max(width * doorDefLerp(0.94, 1.20, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 24)) out.push(id);
      }
    } else if (kindHint === 'partial') {
      var dirKeepP = directionalOkSingle(pc) || directionalOkSingle(p0) || directionalOkSingle(p1);
      if (isFloorStraRef) continue;
      if (sameScopeRef && isDoorLayerRef && (nearEnd || bandHit || dirKeepP || strictHit >= 1)) {
        if (closedLike || len <= Math.max(width * doorDefLerp(2.6, 5.8, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 24)) {
          out.push(id);
          continue;
        }
      }
      if (strictHit >= 1) {
        if (len <= Math.max(width * doorDefLerp(1.10, 2.40, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 20)) out.push(id);
      } else if (nearEnd && (bandHit || dirKeepP) && len <= Math.max(width * doorDefLerp(1.25, 3.10, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 22)) {
        out.push(id);
      } else if (nearEnd && len <= Math.max(width * doorDefLerp(0.40, 0.88, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 20)) {
        out.push(id);
      }
    } else {
      var dirKeepS = directionalOkSingle(pc) || directionalOkSingle(p0) || directionalOkSingle(p1);
      if (isFloorStraRef) continue;
      if (sameScopeRef && isDoorLayerRef && (nearEnd || bandHit || dirKeepS)) {
        if (closedLike || len <= Math.max(width * doorDefLerp(1.35, 3.8, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 20)) {
          out.push(id);
          continue;
        }
      }
      // 일반문은 ARC 안쪽(스윙 내부) 위주, 바깥쪽 긴 선은 최소화.
      if (strictHit >= 1) {
        if (len <= Math.max(width * doorDefLerp(0.78, 1.02, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 18)) out.push(id);
      } else if (nearEnd && (bandHit || dirKeepS) && len <= Math.max(width * doorDefLerp(0.95, 1.45, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 20)) {
        out.push(id);
      } else if (nearEnd && len <= Math.max(width * doorDefLerp(0.28, 0.46, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 18)) {
        out.push(id);
      } else if (closedLike && (bandHit || dirKeepS) && len <= Math.max(width * doorDefLerp(3.2, 5.6, includeT), DOOR_DEF_MIN_LINEAR_LEN_MM + 20)) {
        out.push(id);
      }
    }
  }
  if (!out.length) {
    var onlyArc = [];
    for (var x = 0; x < arcList.length; x++) onlyArc.push(arcList[x].id);
    return doorDefUniqueEntityIds(onlyArc);
  }
  return doorDefUniqueEntityIds(out);
}
function doorDefBuildArcEndpointBuckets(arcs, grid) {
  var g = grid > 0 ? grid : 80;
  var map = {};
  function pushPoint(pt, arcId) {
    if (!pt) return;
    var ix = Math.floor((Number(pt.x) || 0) / g);
    var iy = Math.floor((Number(pt.y) || 0) / g);
    var key = ix + '|' + iy;
    if (!map[key]) map[key] = [];
    map[key].push(arcId);
  }
  for (var i = 0; i < arcs.length; i++) {
    pushPoint(arcs[i].arc_start, arcs[i].id);
    pushPoint(arcs[i].arc_end, arcs[i].id);
  }
  return { grid: g, map: map };
}
function doorDefConnectedArcIds(target, endpointBuckets, byId) {
  var out = {};
  if (!target || !endpointBuckets || !endpointBuckets.map) return out;
  var g = endpointBuckets.grid || 80;
  function hit(pt) {
    if (!pt) return;
    var ix = Math.floor((Number(pt.x) || 0) / g);
    var iy = Math.floor((Number(pt.y) || 0) / g);
    for (var dx = -1; dx <= 1; dx++) {
      for (var dy = -1; dy <= 1; dy++) {
        var key = (ix + dx) + '|' + (iy + dy);
        var arr = endpointBuckets.map[key] || [];
        for (var i = 0; i < arr.length; i++) {
          var id = arr[i];
          if (id === target.id) continue;
          var other = byId[id];
          if (!other) continue;
          if (doorDefArcPairLikelyDouble(target, other)) out[id] = true;
        }
      }
    }
  }
  hit(target.arc_start);
  hit(target.arc_end);
  return out;
}
function doorDefExtractArcGroups(arcs) {
  var list = doorDefDedupArcList(arcs || []);
  if (!list.length) return [];
  var byId = {};
  for (var i = 0; i < list.length; i++) byId[list[i].id] = list[i];
  var buckets = doorDefBuildArcEndpointBuckets(list, 80);
  var used = {};
  var groups = [];
  for (var a = 0; a < list.length; a++) {
    var base = list[a];
    if (!base || used[base.id]) continue;
    var group = [];
    var queue = [base];
    used[base.id] = true;
    while (queue.length > 0) {
      var cur = queue.shift();
      group.push(cur);
      if (group.length >= 3) continue;
      var linked = doorDefConnectedArcIds(cur, buckets, byId);
      var keys = Object.keys(linked);
      for (var k = 0; k < keys.length; k++) {
        var nid = parseInt(keys[k], 10);
        if (!(nid > 0) || used[nid] || !byId[nid]) continue;
        used[nid] = true;
        queue.push(byId[nid]);
      }
    }
    groups.push(group);
  }
  return groups;
}
function doorDefClassifyOpeningKind(widthMm, arcs, endpointLinks) {
  var list = doorDefDedupArcList(arcs || []).filter(function(a) {
    return a && (Number(a.radius) || 0) > 0;
  });
  if (!list.length) return 'single';
  list.sort(function(a, b) {
    return (Number(b.radius) || 0) - (Number(a.radius) || 0);
  });
  var mainR = Number(list[0].radius) || 0;
  var significant = [];
  for (var i = 0; i < list.length; i++) {
    var r = Number(list[i].radius) || 0;
    if (!(r > 0)) continue;
    var sweep = list[i].sweep != null ? Number(list[i].sweep) : NaN;
    if (isFinite(sweep) && sweep < 10) continue;
    if (mainR > 0 && r < (mainR * 0.6)) continue;
    significant.push(list[i]);
  }
  var arcCount = significant.length || list.length;
  return arcCount === 2 ? 'double' : 'single';
}
function doorDefBuildAutoClasses(openings, kind) {
  var map = {};
  for (var i = 0; i < (openings || []).length; i++) {
    var d = openings[i];
    if (!d || d.kind !== kind || !(d.width_class_mm > 0)) continue;
    var key = String(d.kind) + '|' + String(d.width_class_mm);
    if (!map[key]) map[key] = { key: key, kind: d.kind, width_mm: d.width_class_mm, count: 0, opening_ids: [] };
    map[key].count += 1;
    map[key].opening_ids.push(d.opening_id);
  }
  var out = Object.keys(map).map(function(k) { return map[k]; });
  out.sort(function(a, b) { return (a.width_mm || 0) - (b.width_mm || 0); });
  return out;
}
function doorDefRenderAutoClassList() {
  var doorBoxEl = document.getElementById('doorDefAutoDoorClassList');
  var winBoxEl = document.getElementById('doorDefAutoWindowClassList');
  var partialBoxEl = document.getElementById('doorDefAutoPartialClassList');
  var summaryEl = document.getElementById('doorDefAutoSummary');
  if (!doorBoxEl && !winBoxEl && !partialBoxEl) return;
  var doors = (doorDefState.autoOpenings || []).filter(function(o) { return o.kind === 'single'; });
  var wins = (doorDefState.autoOpenings || []).filter(function(o) { return o.kind === 'double'; });
  var partials = (doorDefState.autoOpenings || []).filter(function(o) { return o.kind === 'partial'; });
  var doorClasses = doorDefState.autoDoorClasses || [];
  var winClasses = doorDefState.autoWindowClasses || [];
  var partialClasses = doorDefState.autoPartialClasses || [];
  if (!doorClasses.length && !winClasses.length && !partialClasses.length) {
    if (doorBoxEl) doorBoxEl.innerHTML = '<div style="color:#57606a;">ARC 자동탐지를 실행하세요.</div>';
    if (winBoxEl) winBoxEl.innerHTML = '<div style="color:#57606a;">ARC 자동탐지를 실행하세요.</div>';
    if (partialBoxEl) partialBoxEl.innerHTML = '<div style="color:#57606a;">ARC 자동탐지를 실행하세요.</div>';
    if (summaryEl) summaryEl.innerHTML = '<div style="color:#57606a;">자동 탐지 결과가 없습니다.</div>';
    return;
  }
  function buildClassHtml(list) {
    var activeKey = String(doorDefState.autoActiveClassKey || '').trim();
    var activeAll = String(doorDefState.autoActiveKindAll || '').trim();
    if (!list.length) return '<div style="color:#57606a;">해당 결과 없음</div>';
    var html = [];
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var on = activeKey === c.key || activeAll === c.kind || activeAll === 'all';
      var border = on ? '#0969da' : '#d0d7de';
      var bg = on ? '#ddf4ff' : '#fff';
      var adj = doorDefGetClassWidthAdjustMm(c.key);
      var adjSign = adj >= 0 ? '+' : '';
      var finalW = doorDefAdjustedWidthMm(c.width_mm, c.key);
      html.push(
        '<div data-door-auto-class="' + escapeHtml(c.key) + '" data-door-auto-kind="' + escapeHtml(c.kind) + '" style="padding:6px; border:1px solid ' + border + '; border-radius:6px; background:' + bg + '; margin-bottom:6px; cursor:pointer;">' +
        '<div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">' +
        '<strong>정의 폭 ' + escapeHtml(String(finalW)) + 'mm</strong>' +
        '<span style="font-size:0.74rem; color:#57606a;">탐지 ' + escapeHtml(String(c.width_mm)) + ' / 보정 ' + adjSign + escapeHtml(String(adj)) + '</span>' +
        '</div>' +
        '<div style="margin-top:5px; display:flex; justify-content:flex-end; gap:6px;">' +
        '<button type="button" data-door-auto-adjust="-10" data-door-auto-class="' + escapeHtml(c.key) + '" style="padding:3px 8px; font-size:0.74rem; font-weight:700; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:5px;">폭 -10</button>' +
        '<button type="button" data-door-auto-adjust="10" data-door-auto-class="' + escapeHtml(c.key) + '" style="padding:3px 8px; font-size:0.74rem; font-weight:700; color:#1e3a8a; background:#dbeafe; border:1px solid #93c5fd; border-radius:5px;">폭 +10</button>' +
        '</div>' +
        '<div style="margin-top:3px; color:#57606a; font-size:0.78rem;">' + doorDefOpeningKindLabel(c.kind) + ' ' + escapeHtml(String(c.count)) + '개</div>' +
        '</div>'
      );
    }
    return html.join('');
  }
  if (doorBoxEl) doorBoxEl.innerHTML = buildClassHtml(doorClasses);
  if (winBoxEl) winBoxEl.innerHTML = buildClassHtml(winClasses);
  if (partialBoxEl) partialBoxEl.innerHTML = buildClassHtml(partialClasses);
  if (summaryEl) {
    var range = doorDefGetArcWidthRangeMm();
    var includeExtent = doorDefGetIncludeExtent();
    var arcNear = doorDefGetArcNearGauge();
    var totalCnt = doors.length + wins.length + partials.length;
    summaryEl.innerHTML =
      '<div style="display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:6px; margin-bottom:6px;">' +
      '<div style="border:1px solid #d0d7de; border-radius:6px; background:#fff; padding:6px 8px;"><div style="font-size:0.70rem; color:#57606a;">전체</div><div style="font-size:0.92rem; color:#24292f; font-weight:700;">' + totalCnt + '개</div></div>' +
      '<div style="border:1px solid #d0d7de; border-radius:6px; background:#fff; padding:6px 8px;"><div style="font-size:0.70rem; color:#57606a;">문</div><div style="font-size:0.92rem; color:#24292f; font-weight:700;">' + doors.length + '개</div></div>' +
      '<div style="border:1px solid #d0d7de; border-radius:6px; background:#fff; padding:6px 8px;"><div style="font-size:0.70rem; color:#57606a;">양개문</div><div style="font-size:0.92rem; color:#24292f; font-weight:700;">' + wins.length + '개</div></div>' +
      '<div style="border:1px solid #d0d7de; border-radius:6px; background:#fff; padding:6px 8px;"><div style="font-size:0.70rem; color:#57606a;">부분개방</div><div style="font-size:0.92rem; color:#24292f; font-weight:700;">' + partials.length + '개</div></div>' +
      '</div>' +
      '<div style="display:flex; flex-wrap:wrap; gap:10px; font-size:0.74rem; color:#57606a;">' +
      '<span>폭범위 <strong style="color:#24292f;">' + range.min + '~' + range.max + 'mm</strong></span>' +
      '<span>포함정도 <strong style="color:#24292f;">' + includeExtent + '%</strong></span>' +
      '<span>ARC근접도 <strong style="color:#24292f;">자동연동(' + arcNear + ')</strong></span>' +
      '<span>선형근거 <strong style="color:#24292f;">ARC폭 50~100% / 선분 70mm 초과</strong></span>' +
      '</div>';
  }
}
function doorDefSelectAutoClass(classKey, silent) {
  var key = String(classKey || '').trim();
  if (!key) return false;
  var classes = (doorDefState.autoDoorClasses || [])
    .concat(doorDefState.autoWindowClasses || [])
    .concat(doorDefState.autoPartialClasses || []);
  var openings = doorDefState.autoOpenings || [];
  var found = null;
  for (var i = 0; i < classes.length; i++) {
    if (String(classes[i].key) === key) { found = classes[i]; break; }
  }
  if (!found) return false;
  var openingSet = {};
  for (var j = 0; j < found.opening_ids.length; j++) openingSet[String(found.opening_ids[j])] = true;
  var ids = [];
  for (var d = 0; d < openings.length; d++) {
    var door = openings[d];
    if (!door || !openingSet[String(door.opening_id)]) continue;
    var eids = door.entity_ids || [];
    for (var ei = 0; ei < eids.length; ei++) ids.push(eids[ei]);
  }
  ids = doorDefUniqueEntityIds(ids);
  if (!ids.length) return false;
  doorDefState.autoActiveClassKey = key;
  doorDefState.autoActiveKindAll = '';
  doorDefState.seedIds = [];
  doorDefState.seedEntities = [];
  doorDefState.seedSignature = null;
  doorDefState.candidates = [];
  doorDefState.checkedCandidateIds = {};
  doorDefState.activeCandidateId = '';
  doorDefState.selectedDefinedGroupId = '';
  doorDefSetSelectedEntities(ids);
  doorDefRenderCandidateList();
  doorDefRenderAutoClassList();
  if (!silent) {
    var finalW = doorDefAdjustedWidthMm(found.width_mm, found.key);
    showMsg('msg', doorDefOpeningKindLabel(found.kind) + ' 분류 선택: 정의 폭 ' + finalW + 'mm (' + found.count + '개)', 'info');
  }
  return true;
}
function doorDefSelectAllAutoKind(kind, silent) {
  var k = String(kind || '').trim().toLowerCase();
  if (k !== 'single' && k !== 'double' && k !== 'partial') return false;
  var openings = doorDefState.autoOpenings || [];
  var ids = [];
  var cnt = 0;
  for (var i = 0; i < openings.length; i++) {
    var o = openings[i];
    if (!o || o.kind !== k) continue;
    cnt += 1;
    var eids = o.entity_ids || [];
    for (var ei = 0; ei < eids.length; ei++) ids.push(eids[ei]);
  }
  ids = doorDefUniqueEntityIds(ids);
  if (!ids.length) return false;
  doorDefState.autoActiveClassKey = '';
  doorDefState.autoActiveKindAll = k;
  doorDefState.seedIds = [];
  doorDefState.seedEntities = [];
  doorDefState.seedSignature = null;
  doorDefState.candidates = [];
  doorDefState.checkedCandidateIds = {};
  doorDefState.activeCandidateId = '';
  doorDefState.selectedDefinedGroupId = '';
  doorDefSetSelectedEntities(ids);
  doorDefRenderCandidateList();
  doorDefRenderAutoClassList();
  if (!silent) showMsg('msg', doorDefOpeningKindLabel(k) + ' 전체 선택: ' + cnt + '개', 'info');
  return true;
}
function doorDefSelectAllAuto(silent) {
  var openings = doorDefState.autoOpenings || [];
  var ids = [];
  var cnt = 0;
  for (var i = 0; i < openings.length; i++) {
    var o = openings[i];
    if (!o) continue;
    cnt += 1;
    var eids = o.entity_ids || [];
    for (var ei = 0; ei < eids.length; ei++) ids.push(eids[ei]);
  }
  ids = doorDefUniqueEntityIds(ids);
  if (!ids.length) return false;
  doorDefState.autoActiveClassKey = '';
  doorDefState.autoActiveKindAll = 'all';
  doorDefState.seedIds = [];
  doorDefState.seedEntities = [];
  doorDefState.seedSignature = null;
  doorDefState.candidates = [];
  doorDefState.checkedCandidateIds = {};
  doorDefState.activeCandidateId = '';
  doorDefState.selectedDefinedGroupId = '';
  doorDefSetSelectedEntities(ids);
  doorDefRenderCandidateList();
  doorDefRenderAutoClassList();
  if (!silent) showMsg('msg', '전체 선택: 문/양개문/부분개방문 ' + cnt + '개', 'info');
  return true;
}
function doorDefAutoDetectDoors() {
  if (viewMode !== 'single') {
    showMsg('msg', '개구부 자동탐지는 일반 보기에서만 사용할 수 있습니다.', 'error');
    return [];
  }
  var cid = doorDefCurrentCommitId();
  if (!cid) {
    showMsg('msg', '버전을 선택하세요.', 'error');
    return [];
  }
  var idx = doorDefDescriptorIndex();
  var gauge = doorDefGetDetectGauge();
  var includeT = doorDefIncludeExtentRatio();
  var nearT = doorDefArcNearTightRatio();
  var strictScale = doorDefStrictTightnessScale(includeT, nearT);
  var nearCountScale = doorDefLerp(1.08, 0.56, nearT) * doorDefLerp(1.0, 0.76, strictScale);
  var strictCountB = Math.max(4, Math.round(doorDefLerp(6, 15, includeT) * nearCountScale));
  var relaxedCountB = Math.max(strictCountB + 2, Math.round(doorDefLerp(12, 30, includeT) * nearCountScale));
  var retryCountB = Math.max(relaxedCountB, Math.round(doorDefLerp(14, 36, includeT) * nearCountScale));
  var strictCountL = Math.max(5, strictCountB - 1);
  var relaxedCountL = Math.max(strictCountL + 2, Math.round(doorDefLerp(10, 26, includeT) * nearCountScale));
  var retryCountL = Math.max(relaxedCountL, Math.round(doorDefLerp(12, 32, includeT) * nearCountScale));
  var widthRange = doorDefGetArcWidthRangeMm();
  var minArcWidthMm = widthRange.min;
  var maxArcWidthMm = widthRange.max;
  var blockMap = doorDefBuildBlockEntityMap();
  var blockArcs = {};
  var looseArcs = [];
  var arcList = (idx.byType && idx.byType.ARC) ? idx.byType.ARC : [];
  for (var i = 0; i < arcList.length; i++) {
    var d = doorDefArcLikeDescriptor(arcList[i]);
    if (!d) continue;
    var strictOk = doorDefIsOpeningArcCandidate(d, idx, blockMap.countByBlock || {});
    var relaxedOk = doorDefIsOpeningArcCandidateRelaxed(d);
    if (!strictOk && !relaxedOk && gauge < 90) continue;
    var groupKey = doorDefEntityBlockGroupKey(d.ent);
    if (groupKey) {
      if (!blockArcs[groupKey]) blockArcs[groupKey] = [];
      blockArcs[groupKey].push(d);
    } else {
      looseArcs.push(d);
    }
  }
  var openings = [];
  var seq = 0;
  var blockKeys = Object.keys(blockArcs);
  for (var bi = 0; bi < blockKeys.length; bi++) {
    var blockKey = blockKeys[bi];
    var groupsB = doorDefExtractArcGroups(blockArcs[blockKey] || []);
    var bid = doorDefBlockInsertIdFromGroupKey(blockKey);
    var baseAllowIds = []
      .concat(blockMap.idsByBlock[blockKey] || [])
      .concat((bid != null ? (blockMap.idsByBlock[String(bid)] || []) : []));
    for (var gb = 0; gb < groupsB.length; gb++) {
      var rawGroupB = groupsB[gb] || [];
      var partialModeB = false;
      var arcsB = doorDefNormalizeDoorArcGroup(rawGroupB, gauge);
      if (!arcsB.length) {
        var partialArcB = doorDefFindPartialOpenArcInGroup(rawGroupB, gauge);
        if (partialArcB) {
          arcsB = [partialArcB];
          partialModeB = true;
        }
      }
      if (!arcsB.length) continue;
      var scopeKeyB = doorDefArcGroupCommonScopeKey(arcsB);
      var allowIds = [];
      if (scopeKeyB) allowIds = allowIds.concat(blockMap.idsByBlock[scopeKeyB] || []);
      if (!allowIds.length) {
        allowIds = baseAllowIds.slice();
        var scopeKeysB = doorDefCollectArcGroupScopeKeys(arcsB);
        for (var ski = 0; ski < scopeKeysB.length; ski++) {
          allowIds = allowIds.concat(blockMap.idsByBlock[scopeKeysB[ski]] || []);
        }
      }
      var allowSet = doorDefBuildAllowedIdSet(allowIds);
      var isPairDoubleB = doorDefArcGroupLikelyDouble(arcsB);
      var widthB = doorDefEstimateOpeningWidthFromArcs(arcsB);
      if (!(widthB > 0)) continue;
      if (widthB < minArcWidthMm || widthB > maxArcWidthMm) continue;
      var widthClassB = doorDefWidthClassMm(widthB);
      var endpointLinksB = doorDefEndpointLinkCount(arcsB, idx, allowSet);
      var arcIdsB = arcsB.map(function(a) { return a.id; });
      var strictIdsB = doorDefGatherNearbyEntityIdsForArcGroup(arcsB, idx, { allowedIdSet: allowSet, maxCount: strictCountB, widthLimitMm: widthB });
      strictIdsB = doorDefPruneOpeningEntityIdsByWidth(strictIdsB, widthB, idx, arcIdsB);
      var relaxedIdsB = doorDefGatherNearbyEntityIdsForArcGroup(arcsB, idx, { allowedIdSet: allowSet, maxCount: relaxedCountB, widthLimitMm: widthB, relaxed: true });
      relaxedIdsB = doorDefPruneOpeningEntityIdsByWidth(relaxedIdsB, widthB, idx, arcIdsB, { relaxed: true });
      var entityIdsBAll = doorDefUniqueEntityIds((strictIdsB || []).concat(relaxedIdsB || []));
      if (!entityIdsBAll.length) entityIdsBAll = arcIdsB.slice();
      var linearMinLenB = Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM, widthB * 0.5);
      var linearMaxLenB = Math.max(linearMinLenB, widthB);
      var linearCntB = doorDefCountLinearSupportEntities(entityIdsBAll, idx, linearMinLenB, linearMaxLenB);
      if (linearCntB < 1) {
        var retryIdsB = doorDefGatherNearbyEntityIdsForArcGroup(arcsB, idx, { allowedIdSet: allowSet, maxCount: retryCountB, widthLimitMm: widthB, relaxed: true });
        retryIdsB = doorDefPruneOpeningEntityIdsByWidth(retryIdsB, widthB, idx, arcIdsB, { relaxed: true });
        var retryLinearCntB = doorDefCountLinearSupportEntities(retryIdsB, idx, linearMinLenB, linearMaxLenB);
        if (retryLinearCntB < 1) {
          retryLinearCntB = doorDefCountLinearSupportEntities(retryIdsB, idx, Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM, widthB * 0.35), Math.max(widthB, widthB * 1.2));
        }
        if (retryLinearCntB > linearCntB) {
          entityIdsBAll = retryIdsB;
          linearCntB = retryLinearCntB;
        }
      }
      if (linearCntB < 1) {
        linearCntB = doorDefCountLinearSupportEntities(entityIdsBAll, idx, Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM, widthB * 0.20), Math.max(widthB * 1.4, widthB + 220));
      }
      if (linearCntB < 1) {
        if (isPairDoubleB || partialModeB) {
          // ARC 쌍/부분개방 ARC는 선형근거가 부족해도 후보를 유지한다.
          linearCntB = 1;
          entityIdsBAll = arcIdsB.slice();
        } else {
          continue;
        }
      }
      if (scopeKeyB) entityIdsBAll = doorDefFilterEntityIdsByScopeKey(entityIdsBAll, idx, arcIdsB, scopeKeyB);
      entityIdsBAll = doorDefExpandDoorEntityIds(entityIdsBAll, idx, widthB, { allowedIdSet: allowSet, relaxed: true });
      if (scopeKeyB) entityIdsBAll = doorDefFilterEntityIdsByScopeKey(entityIdsBAll, idx, arcIdsB, scopeKeyB);
      if (scopeKeyB) entityIdsBAll = doorDefAugmentEntityIdsByScopeDoorLayer(entityIdsBAll, idx, arcsB, widthB, scopeKeyB);
      var entityIdsB = doorDefFilterEntityIdsByDoorColors(entityIdsBAll, idx, arcIdsB);
      entityIdsB = doorDefFilterOpeningEntityIdsByLinearMinLen(entityIdsB, idx, arcIdsB);
      if (entityIdsB.length < arcIdsB.length) entityIdsB = arcIdsB.slice();
      var kindB = partialModeB ? 'partial' : (isPairDoubleB ? 'double' : doorDefClassifyOpeningKind(widthB, arcsB, endpointLinksB));
      entityIdsB = doorDefRefineOpeningEntityIdsByArcRelation(entityIdsB, idx, arcsB, kindB, widthB);
      if (entityIdsB.length < arcIdsB.length) entityIdsB = arcIdsB.slice();
      var cxB = 0, cyB = 0;
      for (var aiB = 0; aiB < arcsB.length; aiB++) { cxB += arcsB[aiB].centroid.x; cyB += arcsB[aiB].centroid.y; }
      var centerB = { x: cxB / arcsB.length, y: cyB / arcsB.length };
      seq += 1;
      openings.push({
        opening_id: 'auto-' + seq,
        kind: kindB,
        source: 'block',
        block_group_key: blockKey,
        block_insert_id: bid,
        arc_ids: arcIdsB,
        entity_ids: doorDefUniqueEntityIds(entityIdsB),
        width_mm: widthB,
        width_class_mm: widthClassB,
        linear_count: linearCntB,
        linear_min_len_mm: linearMinLenB,
        linear_max_len_mm: linearMaxLenB,
        center: centerB
      });
    }
  }
  var groupsL = doorDefExtractArcGroups(looseArcs || []);
  for (var gl = 0; gl < groupsL.length; gl++) {
    var rawGroupL = groupsL[gl] || [];
    var partialModeL = false;
    var gArcs = doorDefNormalizeDoorArcGroup(rawGroupL, gauge);
    if (!gArcs.length) {
      var partialArcL = doorDefFindPartialOpenArcInGroup(rawGroupL, gauge);
      if (partialArcL) {
        gArcs = [partialArcL];
        partialModeL = true;
      }
    }
    if (!gArcs.length) continue;
    var isPairDoubleL = doorDefArcGroupLikelyDouble(gArcs);
    var scopeKeyL = doorDefArcGroupCommonScopeKey(gArcs);
    var widthL = doorDefEstimateOpeningWidthFromArcs(gArcs);
    if (!(widthL > 0)) continue;
    if (widthL < minArcWidthMm || widthL > maxArcWidthMm) continue;
    var widthClassL = doorDefWidthClassMm(widthL);
    var endpointLinksL = doorDefEndpointLinkCount(gArcs, idx, null);
    var arcIdsL = gArcs.map(function(a) { return a.id; });
    var strictIdsL = doorDefGatherNearbyEntityIdsForArcGroup(gArcs, idx, { maxCount: strictCountL, widthLimitMm: widthL });
    strictIdsL = doorDefPruneOpeningEntityIdsByWidth(strictIdsL, widthL, idx, arcIdsL);
    var relaxedIdsL = doorDefGatherNearbyEntityIdsForArcGroup(gArcs, idx, { maxCount: relaxedCountL, widthLimitMm: widthL, relaxed: true });
    relaxedIdsL = doorDefPruneOpeningEntityIdsByWidth(relaxedIdsL, widthL, idx, arcIdsL, { relaxed: true });
    var idsLAll = doorDefUniqueEntityIds((strictIdsL || []).concat(relaxedIdsL || []));
    if (!idsLAll.length) idsLAll = arcIdsL.slice();
    var linearMinLenL = Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM, widthL * 0.5);
    var linearMaxLenL = Math.max(linearMinLenL, widthL);
    var linearCntL = doorDefCountLinearSupportEntities(idsLAll, idx, linearMinLenL, linearMaxLenL);
    if (linearCntL < 1) {
      var retryIdsL = doorDefGatherNearbyEntityIdsForArcGroup(gArcs, idx, { maxCount: retryCountL, widthLimitMm: widthL, relaxed: true });
      retryIdsL = doorDefPruneOpeningEntityIdsByWidth(retryIdsL, widthL, idx, arcIdsL, { relaxed: true });
      var retryLinearCntL = doorDefCountLinearSupportEntities(retryIdsL, idx, linearMinLenL, linearMaxLenL);
      if (retryLinearCntL < 1) {
        retryLinearCntL = doorDefCountLinearSupportEntities(retryIdsL, idx, Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM, widthL * 0.35), Math.max(widthL, widthL * 1.2));
      }
      if (retryLinearCntL > linearCntL) {
        idsLAll = retryIdsL;
        linearCntL = retryLinearCntL;
      }
    }
    if (linearCntL < 1) {
      linearCntL = doorDefCountLinearSupportEntities(idsLAll, idx, Math.max(DOOR_DEF_MIN_LINEAR_LEN_MM, widthL * 0.20), Math.max(widthL * 1.4, widthL + 220));
    }
    if (linearCntL < 1) {
      if (isPairDoubleL || partialModeL) {
        linearCntL = 1;
        idsLAll = arcIdsL.slice();
      } else {
        continue;
      }
    }
    idsLAll = doorDefExpandDoorEntityIds(idsLAll, idx, widthL, { relaxed: true });
    idsLAll = doorDefAugmentEntityIdsByScopeDoorLayer(idsLAll, idx, gArcs, widthL, scopeKeyL);
    var idsL = doorDefFilterEntityIdsByDoorColors(idsLAll, idx, arcIdsL);
    idsL = doorDefFilterOpeningEntityIdsByLinearMinLen(idsL, idx, arcIdsL);
    if (idsL.length < arcIdsL.length) idsL = arcIdsL.slice();
    var kindL = partialModeL ? 'partial' : (isPairDoubleL ? 'double' : doorDefClassifyOpeningKind(widthL, gArcs, endpointLinksL));
    idsL = doorDefRefineOpeningEntityIdsByArcRelation(idsL, idx, gArcs, kindL, widthL);
    if (idsL.length < arcIdsL.length) idsL = arcIdsL.slice();
    var gx = 0, gy = 0;
    for (var gi = 0; gi < gArcs.length; gi++) { gx += gArcs[gi].centroid.x; gy += gArcs[gi].centroid.y; }
    var gCenter = { x: gx / gArcs.length, y: gy / gArcs.length };
    seq += 1;
    openings.push({
      opening_id: 'auto-' + seq,
      kind: kindL,
      source: 'entity',
      block_insert_id: null,
      arc_ids: arcIdsL,
      entity_ids: doorDefUniqueEntityIds(idsL),
      width_mm: widthL,
      width_class_mm: widthClassL,
      linear_count: linearCntL,
      linear_min_len_mm: linearMinLenL,
      linear_max_len_mm: linearMaxLenL,
      center: gCenter
    });
  }
  var dedupe = {};
  var finalOpenings = [];
  for (var di = 0; di < openings.length; di++) {
    var door = openings[di];
    if (door && door.entity_ids && door.entity_ids.length) {
      door.entity_ids = doorDefFilterOpeningEntityIdsByLinearMinLen(door.entity_ids, idx, door.arc_ids || []);
    }
    if (!door || !door.entity_ids || !door.entity_ids.length || !(door.width_class_mm > 0)) continue;
    var k = door.kind + '|' + door.entity_ids.slice().sort(function(a, b) { return a - b; }).join(',');
    if (!k) continue;
    if (!dedupe[k] || (door.width_mm || 0) > (dedupe[k].width_mm || 0)) dedupe[k] = door;
  }
  finalOpenings = Object.keys(dedupe).map(function(k) { return dedupe[k]; });
  finalOpenings.sort(function(a, b) {
    if ((a.kind || '') !== (b.kind || '')) return (a.kind || '').localeCompare(b.kind || '');
    if ((a.width_class_mm || 0) !== (b.width_class_mm || 0)) return (a.width_class_mm || 0) - (b.width_class_mm || 0);
    var ay = a.center ? a.center.y : 0;
    var by = b.center ? b.center.y : 0;
    if (Math.abs(by - ay) > 1e-9) return by - ay;
    var ax = a.center ? a.center.x : 0;
    var bx = b.center ? b.center.x : 0;
    return ax - bx;
  });
  doorDefState.autoOpenings = finalOpenings;
  doorDefState.autoClassWidthAdjust = {};
  doorDefState.autoDoorClasses = doorDefBuildAutoClasses(finalOpenings, 'single');
  doorDefState.autoWindowClasses = doorDefBuildAutoClasses(finalOpenings, 'double');
  doorDefState.autoPartialClasses = doorDefBuildAutoClasses(finalOpenings, 'partial');
  doorDefState.autoActiveKindAll = 'all';
  doorDefState.lastCommitId = String(cid);
  doorDefState.autoActiveClassKey = '';
  doorDefRenderAutoClassList();
  if (finalOpenings.length) doorDefSelectAllAuto(true);
  return finalOpenings;
}
function doorDefCollectDefinedGroups() {
  var map = {};
  for (var i = 0; i < allEntities.length; i++) {
    var ent = allEntities[i];
    if (!ent || ent.isBlockInsert || ent.id == null) continue;
    var ua = ent.props && ent.props.user_attrs;
    if (!ua || typeof ua !== 'object') continue;
    var gid = String(ua.door_group_id || '').trim();
    if (!gid) continue;
    var g = map[gid];
    if (!g) {
      var noInfo = doorDefGroupNoInfo(ua.door_group_no, gid);
      g = {
        group_id: gid,
        label: doorDefNormalizeLabel(ua.door_definition_label || ''),
        group_no: noInfo.noStr,
        group_no_num: noInfo.noNum,
        role_origin: 0,
        role_similar: 0,
        entity_ids: [],
        sumX: 0,
        sumY: 0,
        count: 0
      };
      map[gid] = g;
    }
    g.entity_ids.push(Number(ent.id));
    var role = String(ua.door_group_role || '').toLowerCase();
    if (role === 'origin') g.role_origin += 1;
    else if (role === 'similar') g.role_similar += 1;
    var c = doorDefEntityCenter(ent);
    if (c) {
      g.sumX += c.x;
      g.sumY += c.y;
      g.count += 1;
    }
  }
  var out = Object.keys(map).map(function(k) {
    var g = map[k];
    g.entity_ids = doorDefUniqueEntityIds(g.entity_ids);
    g.center = g.count > 0 ? { x: g.sumX / g.count, y: g.sumY / g.count } : { x: 0, y: 0 };
    g.object_count = g.entity_ids.length;
    return g;
  }).filter(function(g) { return g.object_count > 0; });
  out.sort(function(a, b) {
    if ((a.label || '') !== (b.label || '')) return (a.label || '').localeCompare(b.label || '');
    if ((a.group_no_num || 0) !== (b.group_no_num || 0)) return (a.group_no_num || 0) - (b.group_no_num || 0);
    return (a.group_id || '').localeCompare(b.group_id || '');
  });
  return out;
}
function doorDefRefreshDefinedGroupList() {
  var selectEl = document.getElementById('doorDefDefinedList');
  var summaryEl = document.getElementById('doorDefDefinedSummary');
  var groups = doorDefCollectDefinedGroups();
  doorDefState.definedGroups = groups;
  var selectedId = String(doorDefState.selectedDefinedGroupId || (selectEl ? (selectEl.value || '') : '')).trim();
  if (groups.length === 0) {
    doorDefState.selectedDefinedGroupId = '';
    if (selectEl) selectEl.innerHTML = '<option value="">(없음)</option>';
    if (summaryEl) summaryEl.textContent = '적용된 문정의 묶음이 없습니다.';
    return;
  }
  var html = ['<option value="">묶음 선택</option>'];
  for (var i = 0; i < groups.length; i++) {
    var g = groups[i];
    var roleText = g.role_origin > 0 ? '원본' : (g.role_similar > 0 ? '유사' : '-');
    var txt = (g.label || '문') + ' / ' + g.group_id + ' / 객체 ' + g.object_count + '개 / ' + roleText;
    html.push('<option value="' + escapeHtml(g.group_id) + '">' + escapeHtml(txt) + '</option>');
  }
  if (selectEl) {
    selectEl.innerHTML = html.join('');
    var exists = groups.some(function(g) { return g.group_id === selectedId; });
    selectEl.value = exists ? selectedId : '';
    doorDefState.selectedDefinedGroupId = exists ? selectedId : '';
  }
  if (summaryEl) {
    var labelMap = {};
    for (var j = 0; j < groups.length; j++) labelMap[groups[j].label || '문'] = true;
    summaryEl.textContent = '총 ' + groups.length + '개 묶음 / 라벨 ' + Object.keys(labelMap).length + '종';
  }
}
function doorDefSelectDefinedGroup(groupId, silent) {
  var gid = String(groupId || '').trim();
  if (!gid) return false;
  var groups = doorDefState.definedGroups || [];
  var found = null;
  for (var i = 0; i < groups.length; i++) {
    if (String(groups[i].group_id) === gid) { found = groups[i]; break; }
  }
  if (!found) {
    if (!silent) showMsg('msg', '선택한 묶음을 찾지 못했습니다.', 'error');
    return false;
  }
  doorDefState.selectedDefinedGroupId = gid;
  doorDefState.autoActiveClassKey = '';
  doorDefState.autoActiveKindAll = '';
  doorDefState.activeCandidateId = '';
  doorDefSetSelectedEntities(found.entity_ids || []);
  doorDefRenderAutoClassList();
  if (!silent) showMsg('msg', '문정의 묶음 선택: ' + found.group_id + ' (' + found.object_count + '개)', 'info');
  return true;
}
function doorDefPreviewGroups() {
  var groups = [];
  var activeAuto = String(doorDefState.autoActiveClassKey || '').trim();
  var activeKindAll = String(doorDefState.autoActiveKindAll || '').trim();
  if (activeAuto || activeKindAll) {
    var autoOpenings = doorDefState.autoOpenings || [];
    var maxAutoOverlay = 120;
    var autoCnt = 0;
    for (var ad = 0; ad < autoOpenings.length; ad++) {
      var door = autoOpenings[ad];
      if (!door) continue;
      var key = doorDefOpeningClassKey(door.kind, door.width_class_mm);
      if (activeAuto && key !== activeAuto) continue;
      if (activeKindAll && activeKindAll !== 'all' && String(door.kind || '') !== activeKindAll) continue;
      var finalW = doorDefAdjustedWidthMm(door.width_class_mm, key);
      groups.push({
        kind: 'auto',
        id: 'auto:' + door.opening_id,
        label: doorDefOpeningKindLabel(door.kind) + ' 폭 ' + finalW + 'mm',
        entity_ids: doorDefUniqueEntityIds(door.entity_ids || []),
        active: true
      });
      autoCnt += 1;
      if (autoCnt >= maxAutoOverlay) break;
    }
  }
  if (doorDefState.seedIds && doorDefState.seedIds.length) {
    groups.push({
      kind: 'origin',
      id: 'origin',
      label: '원본',
      entity_ids: doorDefUniqueEntityIds(doorDefState.seedIds),
      active: String(doorDefState.activeCandidateId || '') === 'origin'
    });
  }
  for (var i = 0; i < (doorDefState.candidates || []).length; i++) {
    var c = doorDefState.candidates[i];
    if (!c || doorDefState.checkedCandidateIds[c.candidate_id] === false) continue;
    groups.push({
      kind: 'similar',
      id: String(c.candidate_id || ''),
      label: '유사 ' + (i + 1),
      entity_ids: doorDefUniqueEntityIds(c.entity_ids || []),
      active: String(doorDefState.activeCandidateId || '') === String(c.candidate_id || '')
    });
  }
  var gid = String(doorDefState.selectedDefinedGroupId || '').trim();
  if (gid) {
    var defs = doorDefState.definedGroups || [];
    for (var di = 0; di < defs.length; di++) {
      if (String(defs[di].group_id) !== gid) continue;
      groups.push({
        kind: 'defined',
        id: 'def:' + defs[di].group_id,
        label: defs[di].group_id,
        entity_ids: doorDefUniqueEntityIds(defs[di].entity_ids || []),
        active: true
      });
      break;
    }
  }
  return groups;
}
function doorDefDrawPreviewOverlays() {
  if (typeof selectedFeatureId !== 'undefined' && selectedFeatureId !== 'door-object-define') return;
  if (doorDefState.previewVisible === false) return;
  var shape = String(doorDefState.previewShape || 'both');
  var groups = doorDefPreviewGroups();
  if (!groups.length) return;
  var rangeX = Math.max(view.maxX - view.minX, 1);
  var rangeY = Math.max(view.maxY - view.minY, 1);
  var scale = ((logicalWidth / rangeX) + (logicalHeight / rangeY)) / 2;
  for (var i = 0; i < groups.length; i++) {
    var g = groups[i];
    if (!g || !g.entity_ids || !g.entity_ids.length) continue;
    var ext = doorDefGroupRangeByIds(g.entity_ids);
    if (!ext || !ext.bbox || !ext.center) continue;
    var color = g.kind === 'origin' ? '#00d4ff' : (g.kind === 'defined' ? '#7ee787' : (g.kind === 'auto' ? '#f59e0b' : '#ffb703'));
    var alpha = g.active ? 0.95 : 0.62;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = g.active ? 2.4 : 1.4;
    ctx.setLineDash(g.active ? [7, 4] : [4, 4]);
    var s1 = toScreen(ext.bbox.minX, ext.bbox.minY);
    var s2 = toScreen(ext.bbox.maxX, ext.bbox.maxY);
    var bx = Math.min(s1.x, s2.x);
    var by = Math.min(s1.y, s2.y);
    var bw = Math.abs(s2.x - s1.x);
    var bh = Math.abs(s2.y - s1.y);
    if (shape === 'bbox' || shape === 'both') {
      ctx.strokeRect(bx, by, Math.max(2, bw), Math.max(2, bh));
    }
    if (shape === 'circle' || shape === 'both') {
      var cp = toScreen(ext.center.x, ext.center.y);
      var rpx = Math.max(7, (ext.radius || 0) * scale);
      ctx.beginPath();
      ctx.arc(cp.x, cp.y, rpx, 0, Math.PI * 2);
      ctx.stroke();
    }
    var label = g.label || '';
    if (label) {
      var tx = bx + 4;
      var ty = Math.max(12, by - 4);
      ctx.font = '11px sans-serif';
      var tw = ctx.measureText(label).width + 8;
      ctx.globalAlpha = 0.78;
      ctx.fillStyle = '#0d0d0d';
      ctx.fillRect(tx - 3, ty - 10, tw, 14);
      ctx.globalAlpha = 1;
      ctx.fillStyle = color;
      ctx.fillText(label, tx, ty);
    }
    ctx.restore();
  }
}
function doorDefCheckedSimilarCount() {
  var cnt = 0;
  for (var i = 0; i < doorDefState.candidates.length; i++) {
    var c = doorDefState.candidates[i];
    if (doorDefState.checkedCandidateIds[c.candidate_id] !== false) cnt += 1;
  }
  return cnt;
}
function doorDefRefreshSummaryText() {
  var seedEl = document.getElementById('doorDefSeedSummary');
  var matchEl = document.getElementById('doorDefMatchSummary');
  if (seedEl) {
    if (!doorDefState.seedEntities || doorDefState.seedEntities.length === 0) {
      seedEl.textContent = '원본 패턴이 없습니다.';
    } else {
      seedEl.textContent = '원본 ' + doorDefState.seedEntities.length + '개 (' + doorDefTypeSummary(doorDefState.seedEntities) + ')';
    }
  }
  if (matchEl) {
    var total = doorDefState.candidates ? doorDefState.candidates.length : 0;
    if (total === 0) {
      matchEl.textContent = '유사 후보가 없습니다.';
    } else {
      matchEl.textContent = '유사 후보 ' + total + '개 / 선택 ' + doorDefCheckedSimilarCount() + '개';
    }
  }
}
function doorDefRefreshSelectAllState() {
  var selectAllEl = document.getElementById('doorDefSelectAllChk');
  if (!selectAllEl) return;
  var total = doorDefState.candidates ? doorDefState.candidates.length : 0;
  if (total <= 0) {
    selectAllEl.disabled = true;
    selectAllEl.checked = false;
    return;
  }
  selectAllEl.disabled = false;
  selectAllEl.checked = doorDefCheckedSimilarCount() === total;
}
function doorDefRenderCandidateList() {
  var listEl = document.getElementById('doorDefCandidateList');
  if (!listEl) return;
  if (!doorDefState.seedEntities || doorDefState.seedEntities.length === 0) {
    listEl.innerHTML = '<div style="color:#57606a;">원본 패턴을 먼저 캡처하세요.</div>';
    doorDefRefreshSelectAllState();
    doorDefRefreshSummaryText();
    return;
  }
  var html = [];
  var seedCnt = doorDefState.seedEntities.length;
  var originActive = String(doorDefState.activeCandidateId || '') === 'origin';
  html.push(
    '<div data-door-candidate="origin" style="padding:6px; border:1px solid ' + (originActive ? '#0969da' : '#d0d7de') + '; border-radius:6px; background:' + (originActive ? '#ddf4ff' : '#f6f8fa') + '; margin-bottom:6px; cursor:pointer;">' +
    '<label style="display:flex; align-items:center; gap:6px; margin:0;">' +
    '<input type="checkbox" checked disabled />' +
    '<span><strong>[원본]</strong> 객체 ' + seedCnt + '개</span>' +
    '</label>' +
    '</div>'
  );
  if (!doorDefState.candidates || doorDefState.candidates.length === 0) {
    html.push('<div style="color:#57606a;">유사 후보가 없습니다.</div>');
    listEl.innerHTML = html.join('');
    doorDefRefreshSelectAllState();
    doorDefRefreshSummaryText();
    return;
  }
  for (var i = 0; i < doorDefState.candidates.length; i++) {
    var c = doorDefState.candidates[i];
    var checked = doorDefState.checkedCandidateIds[c.candidate_id] !== false;
    var active = String(doorDefState.activeCandidateId || '') === String(c.candidate_id || '');
    var ratio = c.total_seed > 0 ? Math.round((c.matched_count / c.total_seed) * 100) : 0;
    var transform = (c.mirrored ? '대칭+' : '') + '회전 ' + fmtNumber(c.rotation_deg || 0, 1) + '°';
    var typeCov = isFinite(c.type_coverage) ? Math.round((c.type_coverage || 0) * 100) : null;
    var extraBits = [];
    if (typeCov != null) extraBits.push('유형커버 ' + typeCov + '%');
    if (isFinite(c.match_tol)) extraBits.push('tol ' + fmtNumber(c.match_tol, 1) + 'mm');
    html.push(
      '<div data-door-candidate="' + escapeHtml(c.candidate_id) + '" style="padding:6px; border:1px solid ' + (active ? '#0969da' : '#d0d7de') + '; border-radius:6px; background:' + (active ? '#ddf4ff' : '#fff') + '; margin-bottom:6px; cursor:pointer;">' +
      '<label style="display:flex; align-items:flex-start; gap:6px; margin:0;">' +
      '<input type="checkbox" data-door-cid="' + escapeHtml(c.candidate_id) + '"' + (checked ? ' checked' : '') + ' />' +
      '<span>' +
      '<strong>[유사 ' + (i + 1) + ']</strong> 객체 ' + c.entity_ids.length + '개 / 일치 ' + c.matched_count + '/' + c.total_seed + ' (' + ratio + '%)' +
      '<div style="color:#57606a; font-size:0.75rem; margin-top:2px;">' + escapeHtml(transform) + ' / 점수 ' + fmtNumber(c.score, 2) + (extraBits.length ? (' / ' + escapeHtml(extraBits.join(' / '))) : '') + '</div>' +
      '</span>' +
      '</label>' +
      '</div>'
    );
  }
  listEl.innerHTML = html.join('');
  doorDefRefreshSelectAllState();
  doorDefRefreshSummaryText();
}
function doorDefRefreshDetailBrief() {
  var briefEl = document.getElementById('doorDefDetailBrief');
  if (!briefEl) return;
  var range = doorDefGetArcWidthRangeMm();
  var includeExtent = doorDefGetIncludeExtent();
  briefEl.textContent = '요약: ARC ' + range.min + '~' + range.max + 'mm / 포함 ' + includeExtent + '%';
}
function doorDefRefreshPanelState() {
  doorDefRenderCandidateList();
  doorDefRefreshDefinedGroupList();
  doorDefRenderAutoClassList();
  var includeExtentEl = document.getElementById('doorDefIncludeExtent');
  var includeExtentValEl = document.getElementById('doorDefIncludeExtentVal');
  var arcNearGaugeEl = document.getElementById('doorDefArcNearGauge');
  var arcNearGaugeValEl = document.getElementById('doorDefArcNearGaugeVal');
  var minArcWidthEl = document.getElementById('doorDefMinArcWidth');
  var minArcWidthValEl = document.getElementById('doorDefMinArcWidthVal');
  var maxArcWidthEl = document.getElementById('doorDefMaxArcWidth');
  var maxArcWidthValEl = document.getElementById('doorDefMaxArcWidthVal');
  var overlayChk = document.getElementById('doorDefPreviewOverlayChk');
  var dimOthersChk = document.getElementById('doorDefDimOthersChk');
  var overlayShapeSel = document.getElementById('doorDefPreviewShapeSel');
  var includeExtent = doorDefGetIncludeExtent();
  var arcNearGauge = doorDefGetArcNearGauge();
  var widthRange = doorDefGetArcWidthRangeMm();
  var minArcWidth = widthRange.min;
  var maxArcWidth = widthRange.max;
  if (includeExtentEl) includeExtentEl.value = String(includeExtent);
  if (includeExtentValEl) includeExtentValEl.textContent = String(includeExtent);
  if (arcNearGaugeEl) arcNearGaugeEl.value = String(arcNearGauge);
  if (arcNearGaugeValEl) arcNearGaugeValEl.textContent = String(arcNearGauge);
  if (minArcWidthEl) minArcWidthEl.value = String(minArcWidth);
  if (minArcWidthValEl) minArcWidthValEl.textContent = String(minArcWidth);
  if (maxArcWidthEl) maxArcWidthEl.value = String(maxArcWidth);
  if (maxArcWidthValEl) maxArcWidthValEl.textContent = String(maxArcWidth);
  doorDefRefreshDetailBrief();
  if (overlayChk) overlayChk.checked = doorDefState.previewVisible !== false;
  if (dimOthersChk) dimOthersChk.checked = doorDefState.dimOthers === true;
  if (overlayShapeSel) {
    var shape = String(doorDefState.previewShape || 'both');
    if (shape !== 'bbox' && shape !== 'circle' && shape !== 'both') shape = 'both';
    overlayShapeSel.value = shape;
  }
}
function doorDefResetState(opts) {
  var keepLabel = !!(opts && opts.keepLabel);
  var keepCommit = !!(opts && opts.keepCommit);
  doorDefState.seedIds = [];
  doorDefState.seedEntities = [];
  doorDefState.seedSignature = null;
  doorDefState.candidates = [];
  doorDefState.checkedCandidateIds = {};
  doorDefState.activeCandidateId = 'origin';
  if (!(opts && opts.keepDefinedSelection)) doorDefState.selectedDefinedGroupId = '';
  if (!(opts && opts.keepAuto)) {
    doorDefState.autoOpenings = [];
    doorDefState.autoDoorClasses = [];
    doorDefState.autoWindowClasses = [];
    doorDefState.autoPartialClasses = [];
    doorDefState.autoClassWidthAdjust = {};
    doorDefState.autoActiveClassKey = '';
    doorDefState.autoActiveKindAll = '';
  }
  if (!keepCommit) doorDefState.lastCommitId = null;
  var labelEl = document.getElementById('doorDefLabelInput');
  if (labelEl && !keepLabel) labelEl.value = '개폐문';
  doorDefRefreshPanelState();
  draw();
}
function doorDefHandleContextChange(commitId) {
  var cid = String(commitId == null ? '' : commitId).trim();
  if (!cid) {
    doorDefResetState({ keepLabel: true });
    return;
  }
  doorDefRefreshDefinedGroupList();
  if (doorDefState.lastCommitId && String(doorDefState.lastCommitId) !== cid) {
    doorDefResetState({ keepLabel: true });
    return;
  }
  if (!doorDefState.seedIds || doorDefState.seedIds.length === 0) return;
  var idx = doorDefDescriptorIndex();
  var restored = [];
  for (var i = 0; i < doorDefState.seedIds.length; i++) {
    var d = idx.byId[String(doorDefState.seedIds[i])];
    if (d) restored.push(d);
  }
  if (restored.length < 2 || restored.length !== doorDefState.seedIds.length) {
    doorDefResetState({ keepLabel: true, keepCommit: true });
    return;
  }
  doorDefState.seedEntities = restored;
  doorDefState.seedSignature = doorDefBuildSeedSignature(restored);
  doorDefRenderCandidateList();
}
function doorDefCaptureSeedFromSelection(silent) {
  if (viewMode !== 'single') {
    if (!silent) showMsg('msg', '문 객체정의는 일반 보기에서만 사용할 수 있습니다.', 'error');
    return false;
  }
  var cid = doorDefCurrentCommitId();
  if (!cid) {
    if (!silent) showMsg('msg', '버전을 선택하세요.', 'error');
    return false;
  }
  var scopeIds = (typeof getSelectedScopeEntityIds === 'function') ? getSelectedScopeEntityIds() : [];
  var uniq = [];
  var seen = {};
  for (var i = 0; i < scopeIds.length; i++) {
    var id = parseInt(scopeIds[i], 10);
    if (!(id > 0) || seen[id]) continue;
    seen[id] = true;
    uniq.push(id);
  }
  if (uniq.length < 2) {
    if (!silent) showMsg('msg', '원본 캡처는 최소 2개 객체를 선택해야 합니다.', 'error');
    return false;
  }
  var idx = doorDefDescriptorIndex();
  var seedDescs = [];
  for (var j = 0; j < uniq.length; j++) {
    var d = idx.byId[String(uniq[j])];
    if (d) seedDescs.push(d);
  }
  if (seedDescs.length < 2) {
    if (!silent) showMsg('msg', '선택 객체에서 원본 패턴을 구성하지 못했습니다.', 'error');
    return false;
  }
  doorDefState.seedIds = seedDescs.map(function(d) { return d.id; });
  doorDefState.seedEntities = seedDescs;
  doorDefState.seedSignature = doorDefBuildSeedSignature(seedDescs);
  doorDefState.candidates = [];
  doorDefState.checkedCandidateIds = {};
  doorDefState.activeCandidateId = 'origin';
  doorDefState.selectedDefinedGroupId = '';
  doorDefState.lastCommitId = cid;
  doorDefSetSelectedEntities(doorDefState.seedIds);
  doorDefRefreshPanelState();
  if (!silent) showMsg('msg', '원본 패턴 ' + seedDescs.length + '개를 캡처했습니다.', 'success');
  return true;
}
function doorDefBuildCandidateByTransform(signature, anchorDesc, angle, mirrored, tol, idx, seedSet, angleWeight, contextScore) {
  if (!signature || !anchorDesc) return null;
  var members = signature.members || [];
  var orderedMembers = signature.match_members || members;
  var repMember = signature.representative_member || doorDefFindMemberById(signature, signature.representative_id);
  if (!repMember) return null;
  if (repMember.type !== anchorDesc.type) return null;
  var posTol = Math.max(tol > 0 ? tol : DOOR_DEF_MATCH_TOL_MM, DOOR_DEF_MATCH_TOL_MM);
  var metricTol = Math.max(DOOR_DEF_MATCH_TOL_MM, posTol * 0.8);
  var minMatched = Math.ceil((signature.count || 0) * DOOR_DEF_MATCH_RATIO);
  var centerRel = doorDefTransformVec(repMember.rel || { x: 0, y: 0 }, angle, mirrored);
  var center = { x: anchorDesc.centroid.x - centerRel.x, y: anchorDesc.centroid.y - centerRel.y };
  var used = {};
  used[anchorDesc.id] = true;
  var matched = [anchorDesc];
  var matchedPairs = [{ seed: repMember, cand: anchorDesc, score: 0 }];
  var matchedByType = {};
  matchedByType[repMember.type] = 1;
  var ids = [anchorDesc.id];
  var totalScore = 0;
  for (var m = 0; m < orderedMembers.length; m++) {
    var s = orderedMembers[m];
    if (s.id === repMember.id) continue;
    var leftAfter = orderedMembers.length - (m + 1);
    if ((matchedPairs.length + 1 + leftAfter) < minMatched) return null;
    var predRel = doorDefTransformVec(s.rel, angle, mirrored);
    var predicted = { x: center.x + predRel.x, y: center.y + predRel.y };
    var predictedOri = null;
    if (s.orientation != null) predictedOri = mirrored ? (-s.orientation + angle) : (s.orientation + angle);
    var searchRadius = Math.max(posTol * 1.8, DOOR_DEF_MATCH_TOL_MM * 2, 20);
    var pool = doorDefSpatialPool(idx, s.type, predicted, searchRadius);
    var best = null;
    var bestScore = Infinity;
    for (var pi = 0; pi < pool.length; pi++) {
      var cand = pool[pi];
      if (!cand || used[cand.id] || seedSet[cand.id]) continue;
      if (!doorDefMetricCompatible(s, cand, metricTol, { relativeTol: 0.24 })) continue;
      var dist = pointDist(predicted, cand.centroid);
      if (!isFinite(dist) || dist > posTol) continue;
      var lenDiff = ((s.length || 0) > 0 && (cand.length || 0) > 0) ? Math.abs((s.length || 0) - (cand.length || 0)) : 0;
      var radiusDiff = ((s.radius || 0) > 0 && (cand.radius || 0) > 0) ? Math.abs((s.radius || 0) - (cand.radius || 0)) : 0;
      var areaDiff = ((s.area || 0) > 0 && (cand.area || 0) > 0) ? Math.abs((s.area || 0) - (cand.area || 0)) : 0;
      var metricDiff = doorDefMetricDistance(s, cand);
      var layerPenalty = (s.layer || '') && (cand.layer || '') && (s.layer || '') !== (cand.layer || '') ? 0.8 : 0;
      var oriPenalty = 0;
      if (predictedOri != null && cand.orientation != null) {
        var axisType = s.type === 'LINE' || s.type === 'LWPOLYLINE' || s.type === 'POLYLINE';
        var od = axisType ? doorDefAxisAngleDiff(predictedOri, cand.orientation) : doorDefAngleDiff(predictedOri, cand.orientation);
        oriPenalty = od > (Math.PI / 3) ? 3.0 : (od * 0.45);
      }
      var score = dist + (lenDiff * 0.12) + (radiusDiff * 0.18) + (areaDiff * 0.01) + (metricDiff * 0.08) + layerPenalty + oriPenalty;
      if (score < bestScore) {
        bestScore = score;
        best = cand;
      }
    }
    if (best) {
      used[best.id] = true;
      matched.push(best);
      matchedPairs.push({ seed: s, cand: best, score: bestScore });
      ids.push(best.id);
      matchedByType[s.type] = (matchedByType[s.type] || 0) + 1;
      totalScore += bestScore;
    } else {
      if ((matchedPairs.length + leftAfter) < minMatched) return null;
    }
  }
  if (ids.length < minMatched) return null;
  ids = ids.filter(function(v, i, arr) { return arr.indexOf(v) === i; }).sort(function(a, b) { return a - b; });
  if (ids.length < 2) return null;
  for (var z = 0; z < ids.length; z++) {
    if (seedSet[ids[z]]) return null;
  }
  var cx = 0, cy = 0;
  for (var c = 0; c < matchedPairs.length; c++) {
    var pair = matchedPairs[c];
    var relBack = doorDefTransformVec(pair.seed.rel || { x: 0, y: 0 }, angle, mirrored);
    cx += pair.cand.centroid.x - relBack.x;
    cy += pair.cand.centroid.y - relBack.y;
  }
  if (matchedPairs.length > 0) center = { x: cx / matchedPairs.length, y: cy / matchedPairs.length };
  var typeCounts = signature.type_counts || {};
  var typeCovSum = 0, typeCovCnt = 0;
  for (var t in typeCounts) {
    if (!Object.prototype.hasOwnProperty.call(typeCounts, t)) continue;
    var need = Math.max(1, typeCounts[t] || 0);
    var got = matchedByType[t] || 0;
    typeCovSum += Math.min(1, got / need);
    typeCovCnt += 1;
  }
  var typeCoverage = typeCovCnt > 0 ? (typeCovSum / typeCovCnt) : 1;
  if (typeCoverage < 0.55) return null;
  var featureIds = signature.feature_member_ids || [];
  var featureHit = 0;
  if (featureIds.length > 0) {
    for (var fi = 0; fi < featureIds.length; fi++) {
      var fid = featureIds[fi];
      for (var fp = 0; fp < matchedPairs.length; fp++) {
        if (matchedPairs[fp].seed.id === fid) {
          featureHit += 1;
          break;
        }
      }
    }
  }
  var featureCoverage = featureIds.length ? (featureHit / featureIds.length) : 1;
  var shapePenalty = doorDefGroupShapePenalty(signature, matchedPairs, center, angle, mirrored, posTol);
  if (!isFinite(shapePenalty)) return null;
  var missing = (signature.count || 0) - ids.length;
  var avgScore = ids.length > 1 ? (totalScore / (ids.length - 1)) : totalScore;
  var context = Math.max(0, Math.min(1, contextScore != null ? contextScore : 0));
  var score = avgScore
    + Math.max(0, missing) * 10.5
    + shapePenalty
    + ((1 - typeCoverage) * 8.0)
    + ((1 - featureCoverage) * 4.5)
    + ((1 - context) * 2.5)
    + ((isFinite(angleWeight) ? angleWeight : 0) * 0.35)
    + (mirrored ? 0.25 : 0);
  return {
    candidate_id: '',
    kind: 'similar',
    entity_ids: ids,
    matched_count: ids.length,
    total_seed: signature.count || 0,
    score: score,
    center: doorDefCandidateCenter(matched),
    mirrored: !!mirrored,
    rotation_deg: doorDefNormalizeRad(angle) * 180 / Math.PI,
    type_coverage: typeCoverage,
    feature_coverage: featureCoverage,
    context_score: context,
    match_tol: posTol
  };
}
function doorDefBuildCandidateFromAnchor(signature, anchorDesc, mirrored, tol, idx, seedSet, fixedContextScore) {
  if (!signature || !anchorDesc) return null;
  var repMember = signature.representative_member || doorDefFindMemberById(signature, signature.representative_id);
  if (!repMember) return null;
  if (repMember.type !== anchorDesc.type) return null;
  if (!doorDefMetricCompatible(repMember, anchorDesc, tol, { relativeTol: 0.24 })) return null;
  var contextScore = fixedContextScore != null ? fixedContextScore : doorDefAnchorContextScore(anchorDesc, signature, idx, tol);
  var angleCandidates = doorDefEstimateAngles(signature, anchorDesc, mirrored, tol, idx, seedSet);
  if (!angleCandidates || angleCandidates.length === 0) return null;
  var best = null;
  for (var i = 0; i < angleCandidates.length; i++) {
    var hyp = angleCandidates[i];
    var cand = doorDefBuildCandidateByTransform(signature, anchorDesc, hyp.angle, mirrored, tol, idx, seedSet, hyp.weight, contextScore);
    if (!cand) continue;
    if (!best || cand.score < best.score) best = cand;
  }
  return best;
}
function doorDefFindSimilarCandidates() {
  var signature = doorDefState.seedSignature;
  if (!signature || !signature.members || signature.members.length < 2) {
    doorDefState.candidates = [];
    doorDefState.checkedCandidateIds = {};
    doorDefRefreshPanelState();
    return [];
  }
  var idx = doorDefDescriptorIndex();
  var seedSet = {};
  for (var i = 0; i < doorDefState.seedIds.length; i++) seedSet[doorDefState.seedIds[i]] = true;
  var repMember = signature.representative_member || doorDefFindMemberById(signature, signature.representative_id);
  if (!repMember) {
    doorDefState.candidates = [];
    doorDefState.checkedCandidateIds = {};
    doorDefRefreshPanelState();
    return [];
  }
  var pool = idx.byType[repMember.type] || [];
  var isArcRep = repMember.type === 'ARC';
  var adaptiveTol = doorDefAdaptiveTol(signature, DOOR_DEF_MATCH_TOL_MM);
  var tolPasses = [DOOR_DEF_MATCH_TOL_MM];
  if (adaptiveTol > DOOR_DEF_MATCH_TOL_MM + 1) {
    if (isArcRep) {
      tolPasses.push(adaptiveTol);
    } else {
      var midTol = Math.max(DOOR_DEF_MATCH_TOL_MM + 2, Math.min(adaptiveTol, DOOR_DEF_MATCH_TOL_MM * 1.8));
      if (midTol > DOOR_DEF_MATCH_TOL_MM + 1) tolPasses.push(midTol);
      if (adaptiveTol > midTol + 1) tolPasses.push(adaptiveTol);
    }
  }
  var anchorInfos = [];
  for (var p = 0; p < pool.length; p++) {
    var anchor = pool[p];
    if (!anchor || seedSet[anchor.id]) continue;
    if (!doorDefMetricCompatible(repMember, anchor, adaptiveTol, { relativeTol: isArcRep ? 0.22 : 0.28 })) continue;
    var contextScore = doorDefAnchorContextScore(anchor, signature, idx, adaptiveTol);
    var arcGate = isArcRep ? doorDefArcAnchorNeighborhoodScore(anchor, signature, idx, adaptiveTol) : 0;
    if (isArcRep && contextScore < 0.08 && arcGate < 0.10) continue;
    anchorInfos.push({
      anchor: anchor,
      context: contextScore,
      arc_gate: arcGate,
      metricGap: doorDefMetricDistance(repMember, anchor)
    });
  }
  anchorInfos.sort(function(a, b) {
    if (isArcRep && Math.abs((b.arc_gate || 0) - (a.arc_gate || 0)) > 1e-9) return (b.arc_gate || 0) - (a.arc_gate || 0);
    if (Math.abs((b.context || 0) - (a.context || 0)) > 1e-9) return (b.context || 0) - (a.context || 0);
    if (Math.abs((a.metricGap || 0) - (b.metricGap || 0)) > 1e-9) return (a.metricGap || 0) - (b.metricGap || 0);
    return (a.anchor.id || 0) - (b.anchor.id || 0);
  });
  var anchorCap = isArcRep ? DOOR_DEF_MAX_ARC_ANCHORS : DOOR_DEF_MAX_GENERIC_ANCHORS;
  if ((signature.count || 0) > 6) anchorCap = Math.max(80, Math.floor(anchorCap * 0.8));
  var anchorLimit = Math.min(anchorInfos.length, anchorCap);
  var dedupe = {};
  var dedupeCount = 0;
  var dedupeLimit = isArcRep ? 90 : 120;
  for (var tp = 0; tp < tolPasses.length; tp++) {
    var passTol = tolPasses[tp];
    for (var ai = 0; ai < anchorLimit; ai++) {
      var info = anchorInfos[ai];
      var anchor = info.anchor;
      if (!anchor) continue;
      if (!doorDefMetricCompatible(repMember, anchor, passTol, { relativeTol: isArcRep ? 0.22 : 0.26 })) continue;
      if (!isArcRep && anchorInfos.length > 280 && tp > 0 && (info.context || 0) < 0.15) continue;
      if (isArcRep && (info.arc_gate || 0) < 0.12 && (info.context || 0) < 0.16) continue;
      var cand0 = doorDefBuildCandidateFromAnchor(signature, anchor, false, passTol, idx, seedSet, info.context);
      if (cand0) {
        var k0 = cand0.entity_ids.join(',');
        if (!dedupe[k0]) {
          dedupe[k0] = cand0;
          dedupeCount += 1;
        } else if (cand0.score < dedupe[k0].score) {
          dedupe[k0] = cand0;
        }
      }
      var cand1 = doorDefBuildCandidateFromAnchor(signature, anchor, true, passTol, idx, seedSet, info.context);
      if (cand1) {
        var k1 = cand1.entity_ids.join(',');
        if (!dedupe[k1]) {
          dedupe[k1] = cand1;
          dedupeCount += 1;
        } else if (cand1.score < dedupe[k1].score) {
          dedupe[k1] = cand1;
        }
      }
      if (tp > 0 && dedupeCount >= dedupeLimit) break;
    }
    if (tp > 0 && dedupeCount >= dedupeLimit) break;
  }
  var out = Object.keys(dedupe).map(function(k) { return dedupe[k]; });
  out.sort(function(a, b) {
    if (Math.abs((a.score || 0) - (b.score || 0)) > 1e-9) return (a.score || 0) - (b.score || 0);
    if ((b.matched_count || 0) !== (a.matched_count || 0)) return (b.matched_count || 0) - (a.matched_count || 0);
    return (a.entity_ids.length || 0) - (b.entity_ids.length || 0);
  });
  doorDefState.candidates = out;
  doorDefState.checkedCandidateIds = {};
  for (var x = 0; x < out.length; x++) {
    out[x].candidate_id = 'sim-' + (x + 1);
    doorDefState.checkedCandidateIds[out[x].candidate_id] = true;
  }
  doorDefState.autoActiveClassKey = '';
  doorDefState.autoActiveKindAll = '';
  doorDefState.activeCandidateId = out.length ? out[0].candidate_id : 'origin';
  doorDefState.selectedDefinedGroupId = '';
  doorDefSyncSelectionFromCandidates();
  doorDefRefreshPanelState();
  return out;
}
async function doorDefRunFindSimilarFromSelection(forceCapture) {
  if (viewMode !== 'single') {
    showMsg('msg', '문 객체정의는 일반 보기에서만 사용할 수 있습니다.', 'error');
    return;
  }
  var cid = doorDefCurrentCommitId();
  if (!cid) {
    showMsg('msg', '버전을 선택하세요.', 'error');
    return;
  }
  var needCapture = !!forceCapture;
  if (!needCapture) {
    if (!doorDefState.seedIds || doorDefState.seedIds.length < 2) needCapture = true;
    else if (!doorDefState.lastCommitId || String(doorDefState.lastCommitId) !== String(cid)) needCapture = true;
  }
  if (needCapture) {
    var ok = doorDefCaptureSeedFromSelection(true);
    if (!ok) {
      showMsg('msg', '유사 찾기 전에 원본 객체를 2개 이상 선택하세요.', 'error');
      return;
    }
  }
  doorDefState.lastCommitId = String(cid);
  var startedAt = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
  var found = doorDefFindSimilarCandidates();
  var endedAt = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
  var elapsedMs = Math.max(0, endedAt - startedAt);
  var elapsedTxt = elapsedMs >= 1000 ? (Math.round(elapsedMs / 10) / 100).toFixed(2) + 's' : Math.round(elapsedMs) + 'ms';
  doorDefState.autoActiveClassKey = '';
  doorDefState.autoActiveKindAll = '';
  if (!found.length) {
    doorDefState.activeCandidateId = 'origin';
    doorDefState.selectedDefinedGroupId = '';
    if (doorDefState.seedIds && doorDefState.seedIds.length) doorDefSetSelectedEntities(doorDefState.seedIds);
    showMsg('msg', '유사 후보를 찾지 못했습니다. (' + elapsedTxt + ')', 'info');
  } else {
    showMsg('msg', '유사 후보 ' + found.length + '개를 찾았습니다. (' + elapsedTxt + ')', 'success');
  }
}
function doorDefCollectMaxGroupNo() {
  var maxNo = 0;
  for (var i = 0; i < allEntities.length; i++) {
    var ent = allEntities[i];
    if (!ent || ent.isBlockInsert || ent.id == null) continue;
    var ua = ent.props && ent.props.user_attrs;
    if (!ua || typeof ua !== 'object') continue;
    var no = parseInt(ua.door_group_no, 10);
    if (!(no > 0)) {
      var gid = String(ua.door_group_id || '');
      var m = gid.match(/-(\d+)$/);
      if (m) no = parseInt(m[1], 10);
    }
    if (no > maxNo) maxNo = no;
  }
  return maxNo;
}
async function doorDefEnsureProjectAttrKeys() {
  var pid = viewProjectSelect ? String(viewProjectSelect.value || '').trim() : '';
  if (!pid) return;
  try {
    var prRes = await fetch('/api/projects/' + pid);
    if (!prRes.ok) return;
    var project = await prRes.json().catch(function() { return {}; });
    var settings = project && project.settings && typeof project.settings === 'object' ? project.settings : {};
    var common = Array.isArray(settings.common_attr_keys) ? settings.common_attr_keys.slice() : [];
    var changed = false;
    for (var i = 0; i < DOOR_DEF_ATTR_KEYS.length; i++) {
      var key = DOOR_DEF_ATTR_KEYS[i];
      if (common.indexOf(key) < 0) { common.push(key); changed = true; }
    }
    if (changed) {
      var patchRes = await fetch('/api/projects/' + pid, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: { common_attr_keys: common } })
      });
      if (patchRes.ok) {
        commitCommonAttrKeys = common.slice();
        if (typeof loadAttrManage === 'function') loadAttrManage();
        if (typeof loadQueryAttrKeys === 'function') loadQueryAttrKeys();
      }
    }
  } catch (e) {}
}
async function doorDefPatchEntityAttrs(commitId, updates) {
  var ids = Object.keys(updates || {});
  if (!ids.length) return { okCount: 0, failed: [] };
  var cursor = 0;
  var okCount = 0;
  var failed = [];
  var workers = [];
  var limit = Math.min(8, ids.length);
  async function worker() {
    while (true) {
      if (cursor >= ids.length) break;
      var idx = cursor;
      cursor += 1;
      var id = ids[idx];
      var attrs = updates[id];
      try {
        var res = await fetch('/api/commits/' + commitId + '/entities/' + id, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_attrs: attrs })
        });
        if (!res.ok) {
          var detail = await res.json().then(function(d) { return d && d.detail ? d.detail : res.statusText; }).catch(function() { return res.statusText; });
          failed.push({ id: Number(id), reason: detail });
          continue;
        }
        okCount += 1;
        var ent = entityById[String(id)];
        if (!ent) ent = allEntities.find(function(e) { return String(e.id) === String(id); });
        if (ent) {
          ent.props = ent.props || {};
          ent.props.user_attrs = JSON.parse(JSON.stringify(attrs));
        }
      } catch (e) {
        failed.push({ id: Number(id), reason: (e && e.message) || '네트워크 오류' });
      }
    }
  }
  for (var i = 0; i < limit; i++) workers.push(worker());
  await Promise.all(workers);
  return { okCount: okCount, failed: failed };
}
function doorDefCollectActiveAutoOpenings() {
  var openings = doorDefState.autoOpenings || [];
  var activeKey = String(doorDefState.autoActiveClassKey || '').trim();
  var activeKindAll = String(doorDefState.autoActiveKindAll || '').trim();
  var selected = [];
  for (var i = 0; i < openings.length; i++) {
    var o = openings[i];
    if (!o || !o.entity_ids || !o.entity_ids.length) continue;
    var k = doorDefOpeningClassKey(o.kind, o.width_class_mm);
    if (activeKey) {
      if (k === activeKey) selected.push(o);
      continue;
    }
    if (activeKindAll) {
      if (activeKindAll === 'all' || String(o.kind || '') === activeKindAll) selected.push(o);
    }
  }
  return selected;
}
async function doorDefApplyAutoSelection() {
  if (viewMode !== 'single') {
    showMsg('msg', '문 객체정의는 일반 보기에서만 적용할 수 있습니다.', 'error');
    return;
  }
  var cid = doorDefCurrentCommitId();
  if (!cid) { showMsg('msg', '버전을 선택하세요.', 'error'); return; }
  if (doorDefState.lastCommitId && String(doorDefState.lastCommitId) !== String(cid)) {
    doorDefResetState({ keepLabel: true });
    showMsg('msg', '버전이 변경되어 자동분류 상태를 초기화했습니다. 다시 탐지하세요.', 'info');
    return;
  }
  var picked = doorDefCollectActiveAutoOpenings();
  if (!picked.length) {
    showMsg('msg', '먼저 문/양개문/부분개방문 분류(또는 전체 선택)를 선택하세요.', 'error');
    return;
  }
  picked.sort(function(a, b) {
    var ay = a && a.center ? a.center.y : 0;
    var by = b && b.center ? b.center.y : 0;
    if (Math.abs(by - ay) > 1e-9) return by - ay;
    var ax = a && a.center ? a.center.x : 0;
    var bx = b && b.center ? b.center.x : 0;
    return ax - bx;
  });
  var startNo = doorDefCollectMaxGroupNo() + 1;
  var updates = {};
  var firstAppliedId = '';
  var groupCount = 0;
  for (var gi = 0; gi < picked.length; gi++) {
    var op = picked[gi];
    if (!op || !op.entity_ids || !op.entity_ids.length) continue;
    var no = startNo + groupCount;
    var noStr = doorDefPadNo(no);
    var kindRaw = String(op.kind || '').toLowerCase();
    var kind = kindRaw === 'double' ? 'double' : (kindRaw === 'partial' ? 'partial' : 'single');
    var label = kind === 'double' ? '양개문' : (kind === 'partial' ? '부분개방문' : '개폐문');
    var gid = label + '-' + noStr;
    var classKey = doorDefOpeningClassKey(kind, op.width_class_mm);
    var definedWidth = doorDefAdjustedWidthMm(op.width_class_mm, classKey);
    if (!firstAppliedId) firstAppliedId = gid;
    groupCount += 1;
    var entityIds = doorDefUniqueEntityIds(op.entity_ids || []);
    for (var ei = 0; ei < entityIds.length; ei++) {
      var eid = Number(entityIds[ei]);
      if (!(eid > 0)) continue;
      var ent = entityById[String(eid)];
      if (!ent) ent = allEntities.find(function(e) { return e.id === eid; });
      var cur = (ent && ent.props && ent.props.user_attrs && typeof ent.props.user_attrs === 'object')
        ? JSON.parse(JSON.stringify(ent.props.user_attrs))
        : {};
      cur.door_definition_label = label;
      cur.door_group_id = gid;
      cur.door_group_no = noStr;
      cur.door_group_role = 'origin';
      cur.door_leaf_type = kind;
      cur.door_defined_width_mm = String(definedWidth);
      updates[eid] = cur;
    }
  }
  var updateIds = Object.keys(updates);
  if (!updateIds.length) {
    showMsg('msg', '적용할 객체가 없습니다.', 'error');
    return;
  }
  await doorDefEnsureProjectAttrKeys();
  var result = await doorDefPatchEntityAttrs(cid, updates);
  doorDefRefreshDefinedGroupList();
  if (result.okCount > 0 && firstAppliedId) {
    var foundApplied = (doorDefState.definedGroups || []).some(function(g) { return String(g.group_id) === String(firstAppliedId); });
    if (foundApplied) doorDefSelectDefinedGroup(firstAppliedId, true);
  }
  if (typeof updateCadPropsPanel === 'function') updateCadPropsPanel();
  if (typeof updateRightDetail === 'function') updateRightDetail();
  draw();
  if (typeof loadAttrManage === 'function') loadAttrManage();
  if (typeof loadQueryAttrKeys === 'function') loadQueryAttrKeys();
  if (!result.failed.length) {
    showMsg('msg', '자동분류 속성 적용 완료: ' + result.okCount + '개 객체 / ' + groupCount + '개 묶음', 'success');
  } else {
    var failIds = result.failed.slice(0, 10).map(function(f) { return '#' + f.id; }).join(', ');
    var suffix = result.failed.length > 10 ? ' 외 ' + (result.failed.length - 10) + '개' : '';
    showMsg('msg', '부분 적용: 성공 ' + result.okCount + ', 실패 ' + result.failed.length + ' (' + failIds + suffix + ')', 'error');
  }
}
async function doorDefApplyCandidates() {
  if (viewMode !== 'single') {
    showMsg('msg', '문 객체정의는 일반 보기에서만 적용할 수 있습니다.', 'error');
    return;
  }
  var cid = doorDefCurrentCommitId();
  if (!cid) { showMsg('msg', '버전을 선택하세요.', 'error'); return; }
  if (!doorDefState.seedSignature || !doorDefState.seedIds || doorDefState.seedIds.length < 2) {
    showMsg('msg', '먼저 원본 캡처 후 유사 찾기를 실행하세요.', 'error');
    return;
  }
  if (doorDefState.lastCommitId && String(doorDefState.lastCommitId) !== String(cid)) {
    doorDefResetState({ keepLabel: true });
    showMsg('msg', '버전이 변경되어 문 객체정의 상태를 초기화했습니다. 다시 캡처하세요.', 'info');
    return;
  }
  var labelEl = document.getElementById('doorDefLabelInput');
  var label = doorDefNormalizeLabel(labelEl ? labelEl.value : '');
  if (labelEl) labelEl.value = label;
  var selectedSimilar = [];
  for (var i = 0; i < doorDefState.candidates.length; i++) {
    var c = doorDefState.candidates[i];
    if (doorDefState.checkedCandidateIds[c.candidate_id] !== false) selectedSimilar.push(c);
  }
  selectedSimilar.sort(function(a, b) {
    var ay = a && a.center ? a.center.y : 0;
    var by = b && b.center ? b.center.y : 0;
    if (Math.abs(by - ay) > 1e-9) return by - ay;
    var ax = a && a.center ? a.center.x : 0;
    var bx = b && b.center ? b.center.x : 0;
    return ax - bx;
  });
  var groups = [{
    kind: 'origin',
    entity_ids: doorDefState.seedIds.slice(),
    center: doorDefState.seedSignature.center || { x: 0, y: 0 }
  }].concat(selectedSimilar.map(function(x) {
    return { kind: 'similar', entity_ids: (x.entity_ids || []).slice(), center: x.center || { x: 0, y: 0 } };
  }));
  var startNo = doorDefCollectMaxGroupNo() + 1;
  var updates = {};
  for (var gi = 0; gi < groups.length; gi++) {
    var group = groups[gi];
    var no = startNo + gi;
    var noStr = doorDefPadNo(no);
    var gid = label + '-' + noStr;
    for (var ei = 0; ei < group.entity_ids.length; ei++) {
      var eid = Number(group.entity_ids[ei]);
      if (!(eid > 0)) continue;
      if (updates[eid]) continue;
      var ent = entityById[String(eid)];
      if (!ent) ent = allEntities.find(function(e) { return e.id === eid; });
      var cur = (ent && ent.props && ent.props.user_attrs && typeof ent.props.user_attrs === 'object')
        ? JSON.parse(JSON.stringify(ent.props.user_attrs))
        : {};
      cur.door_definition_label = label;
      cur.door_group_id = gid;
      cur.door_group_no = noStr;
      cur.door_group_role = group.kind === 'origin' ? 'origin' : 'similar';
      updates[eid] = cur;
    }
  }
  var updateIds = Object.keys(updates);
  if (!updateIds.length) {
    showMsg('msg', '적용할 객체가 없습니다.', 'error');
    return;
  }
  await doorDefEnsureProjectAttrKeys();
  var result = await doorDefPatchEntityAttrs(cid, updates);
  doorDefRefreshDefinedGroupList();
  if (result.okCount > 0 && groups.length > 0) {
    var firstAppliedId = label + '-' + doorDefPadNo(startNo);
    var foundApplied = (doorDefState.definedGroups || []).some(function(g) { return String(g.group_id) === String(firstAppliedId); });
    if (foundApplied) {
      doorDefSelectDefinedGroup(firstAppliedId, true);
    }
  }
  if (typeof updateCadPropsPanel === 'function') updateCadPropsPanel();
  if (typeof updateRightDetail === 'function') updateRightDetail();
  draw();
  if (typeof loadAttrManage === 'function') loadAttrManage();
  if (typeof loadQueryAttrKeys === 'function') loadQueryAttrKeys();
  if (!result.failed.length) {
    showMsg('msg', '문 객체정의 적용 완료: ' + result.okCount + '개 객체', 'success');
  } else {
    var failIds = result.failed.slice(0, 10).map(function(f) { return '#' + f.id; }).join(', ');
    var suffix = result.failed.length > 10 ? ' 외 ' + (result.failed.length - 10) + '개' : '';
    showMsg('msg', '부분 적용: 성공 ' + result.okCount + ', 실패 ' + result.failed.length + ' (' + failIds + suffix + ')', 'error');
  }
}
function bindDoorDefPanelEvents() {
  var panel = document.getElementById('featurePanel-door-object-define');
  if (!panel || panel.dataset.doorDefBound === '1') return;
  panel.dataset.doorDefBound = '1';
  var captureBtn = document.getElementById('doorDefCaptureSeedBtn');
  var findBtn = document.getElementById('doorDefFindSimilarBtn');
  var autoDetectBtn = document.getElementById('doorDefAutoDetectBtn');
  var clearBtn = document.getElementById('doorDefClearBtn');
  var autoApplyBtn = document.getElementById('doorDefApplyAutoBtn');
  var applyBtn = document.getElementById('doorDefApplyBtn');
  var selectAllChk = document.getElementById('doorDefSelectAllChk');
  var listEl = document.getElementById('doorDefCandidateList');
  var autoDoorClassListEl = document.getElementById('doorDefAutoDoorClassList');
  var autoWindowClassListEl = document.getElementById('doorDefAutoWindowClassList');
  var autoPartialClassListEl = document.getElementById('doorDefAutoPartialClassList');
  var selectAllAllBtn = document.getElementById('doorDefSelectAllAllBtn');
  var selectAllDoorsBtn = document.getElementById('doorDefSelectAllDoorsBtn');
  var selectAllWindowsBtn = document.getElementById('doorDefSelectAllWindowsBtn');
  var selectAllPartialsBtn = document.getElementById('doorDefSelectAllPartialsBtn');
  var includeExtentEl = document.getElementById('doorDefIncludeExtent');
  var includeExtentValEl = document.getElementById('doorDefIncludeExtentVal');
  var arcNearGaugeEl = document.getElementById('doorDefArcNearGauge');
  var arcNearGaugeValEl = document.getElementById('doorDefArcNearGaugeVal');
  var minArcWidthEl = document.getElementById('doorDefMinArcWidth');
  var minArcWidthValEl = document.getElementById('doorDefMinArcWidthVal');
  var maxArcWidthEl = document.getElementById('doorDefMaxArcWidth');
  var maxArcWidthValEl = document.getElementById('doorDefMaxArcWidthVal');
  var overlayChk = document.getElementById('doorDefPreviewOverlayChk');
  var dimOthersChk = document.getElementById('doorDefDimOthersChk');
  var overlayShapeSel = document.getElementById('doorDefPreviewShapeSel');
  var definedListEl = document.getElementById('doorDefDefinedList');
  var definedSelectBtn = document.getElementById('doorDefDefinedSelectBtn');
  if (captureBtn) captureBtn.addEventListener('click', function() { doorDefCaptureSeedFromSelection(false); });
  if (findBtn) findBtn.addEventListener('click', function() { doorDefRunFindSimilarFromSelection(false); });
  if (autoDetectBtn) {
    autoDetectBtn.setAttribute('data-door-def-auto-bound', '1');
    autoDetectBtn.addEventListener('click', function() {
      try {
        var st = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
        var openings = doorDefAutoDetectDoors();
        if (!Array.isArray(openings)) openings = [];
        var doorCnt = 0;
        var winCnt = 0;
        var partialCnt = 0;
        for (var oi = 0; oi < openings.length; oi++) {
          var k = String(openings[oi] && openings[oi].kind || '').toLowerCase();
          if (k === 'double') winCnt += 1;
          else if (k === 'partial') partialCnt += 1;
          else doorCnt += 1;
        }
        var et = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
        var ms = Math.max(0, et - st);
        var txt = ms >= 1000 ? (Math.round(ms / 10) / 100).toFixed(2) + 's' : Math.round(ms) + 'ms';
        var range = doorDefGetArcWidthRangeMm();
        var includeExtent = doorDefGetIncludeExtent();
        var arcNear = doorDefGetArcNearGauge();
        if (!openings.length) showMsg('msg', 'ARC 기반 자동탐지 결과가 없습니다. 폭범위 ' + range.min + '~' + range.max + 'mm / 포함정도 ' + includeExtent + '% / ARC근접도 자동연동(' + arcNear + ') / 선형근거(ARC폭의 50%~100%, 선분 70mm 초과) / 스윙각(일반문)+부분개방 ARC 조건을 확인하세요. (' + txt + ')', 'info');
        else showMsg('msg', 'ARC 기반 개구부 자동탐지: 문 ' + doorCnt + '개 / 양개문 ' + winCnt + '개 / 부분개방문 ' + partialCnt + '개 (폭범위 ' + range.min + '~' + range.max + 'mm, 포함정도 ' + includeExtent + '%, ARC근접도 자동연동 ' + arcNear + ', ' + txt + ')', 'success');
        draw();
      } catch (e) {
        showMsg('msg', 'ARC 자동탐지 실행 중 오류: ' + (e && e.message ? e.message : String(e)), 'error');
      }
    });
  }
  if (selectAllAllBtn) selectAllAllBtn.addEventListener('click', function() {
    if (!doorDefSelectAllAuto(false)) showMsg('msg', '선택 가능한 분류가 없습니다.', 'info');
    draw();
  });
  if (selectAllDoorsBtn) selectAllDoorsBtn.addEventListener('click', function() {
    if (!doorDefSelectAllAutoKind('single', false)) showMsg('msg', '선택 가능한 문 분류가 없습니다.', 'info');
    draw();
  });
  if (selectAllWindowsBtn) selectAllWindowsBtn.addEventListener('click', function() {
    if (!doorDefSelectAllAutoKind('double', false)) showMsg('msg', '선택 가능한 양개문 분류가 없습니다.', 'info');
    draw();
  });
  if (selectAllPartialsBtn) selectAllPartialsBtn.addEventListener('click', function() {
    if (!doorDefSelectAllAutoKind('partial', false)) showMsg('msg', '선택 가능한 부분개방문 분류가 없습니다.', 'info');
    draw();
  });
  function syncIncludeExtentLabel(v) {
    var n = doorDefSetIncludeExtent(v);
    if (includeExtentValEl) includeExtentValEl.textContent = String(n);
    doorDefRefreshDetailBrief();
    return n;
  }
  function syncArcNearGaugeLabel(v) {
    var n = doorDefSetArcNearGauge(v);
    if (arcNearGaugeValEl) arcNearGaugeValEl.textContent = String(n);
    return n;
  }
  function syncMinArcWidthLabel(v) {
    var w = doorDefSetMinArcWidthMm(v);
    var maxW = doorDefGetMaxArcWidthMm();
    if (w > maxW) {
      maxW = doorDefSetMaxArcWidthMm(w);
      if (maxArcWidthEl) maxArcWidthEl.value = String(maxW);
      if (maxArcWidthValEl) maxArcWidthValEl.textContent = String(maxW);
    }
    if (minArcWidthValEl) minArcWidthValEl.textContent = String(w);
    doorDefRefreshDetailBrief();
    return w;
  }
  function syncMaxArcWidthLabel(v) {
    var w = doorDefSetMaxArcWidthMm(v);
    var minW = doorDefGetMinArcWidthMm();
    if (w < minW) {
      minW = doorDefSetMinArcWidthMm(w);
      if (minArcWidthEl) minArcWidthEl.value = String(minW);
      if (minArcWidthValEl) minArcWidthValEl.textContent = String(minW);
    }
    if (maxArcWidthValEl) maxArcWidthValEl.textContent = String(w);
    doorDefRefreshDetailBrief();
    return w;
  }
  if (includeExtentEl) {
    includeExtentEl.value = String(doorDefGetIncludeExtent());
    syncIncludeExtentLabel(includeExtentEl.value);
    includeExtentEl.addEventListener('input', function() {
      syncIncludeExtentLabel(includeExtentEl.value);
    });
    includeExtentEl.addEventListener('change', function() {
      var v = syncIncludeExtentLabel(includeExtentEl.value);
      var st = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var openings = doorDefAutoDetectDoors();
      var et = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var ms = Math.max(0, et - st);
      var txt = ms >= 1000 ? (Math.round(ms / 10) / 100).toFixed(2) + 's' : Math.round(ms) + 'ms';
      if (!openings.length) showMsg('msg', '포함정도 ' + v + '%로 재탐지했지만 결과가 없습니다. (' + txt + ')', 'info');
      else showMsg('msg', '포함정도 ' + v + '% 적용 재탐지: ' + openings.length + '개 후보 (' + txt + ')', 'success');
      draw();
    });
  }
  if (arcNearGaugeEl) {
    arcNearGaugeEl.value = String(doorDefGetArcNearGauge());
    syncArcNearGaugeLabel(arcNearGaugeEl.value);
    arcNearGaugeEl.addEventListener('input', function() {
      syncArcNearGaugeLabel(arcNearGaugeEl.value);
    });
    arcNearGaugeEl.addEventListener('change', function() {
      var v = syncArcNearGaugeLabel(arcNearGaugeEl.value);
      var st = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var openings = doorDefAutoDetectDoors();
      var et = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var ms = Math.max(0, et - st);
      var txt = ms >= 1000 ? (Math.round(ms / 10) / 100).toFixed(2) + 's' : Math.round(ms) + 'ms';
      if (!openings.length) showMsg('msg', 'ARC근접도 ' + v + '로 재탐지했지만 결과가 없습니다. (' + txt + ')', 'info');
      else showMsg('msg', 'ARC근접도 ' + v + ' 적용 재탐지: ' + openings.length + '개 후보 (' + txt + ')', 'success');
      draw();
    });
  }
  if (minArcWidthEl) {
    minArcWidthEl.value = String(doorDefGetMinArcWidthMm());
    syncMinArcWidthLabel(minArcWidthEl.value);
    minArcWidthEl.addEventListener('input', function() {
      syncMinArcWidthLabel(minArcWidthEl.value);
    });
    minArcWidthEl.addEventListener('change', function() {
      var w = syncMinArcWidthLabel(minArcWidthEl.value);
      var st = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var openings = doorDefAutoDetectDoors();
      var et = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var ms = Math.max(0, et - st);
      var txt = ms >= 1000 ? (Math.round(ms / 10) / 100).toFixed(2) + 's' : Math.round(ms) + 'ms';
      var range = doorDefGetArcWidthRangeMm();
      if (!openings.length) showMsg('msg', '최소폭 ' + w + 'mm(범위 ' + range.min + '~' + range.max + ')로 재탐지했지만 결과가 없습니다. (' + txt + ')', 'info');
      else showMsg('msg', '최소폭 ' + w + 'mm 적용 재탐지: ' + openings.length + '개 후보 (범위 ' + range.min + '~' + range.max + ', ' + txt + ')', 'success');
      draw();
    });
  }
  if (maxArcWidthEl) {
    maxArcWidthEl.value = String(doorDefGetMaxArcWidthMm());
    syncMaxArcWidthLabel(maxArcWidthEl.value);
    maxArcWidthEl.addEventListener('input', function() {
      syncMaxArcWidthLabel(maxArcWidthEl.value);
    });
    maxArcWidthEl.addEventListener('change', function() {
      var w = syncMaxArcWidthLabel(maxArcWidthEl.value);
      var st = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var openings = doorDefAutoDetectDoors();
      var et = (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : Date.now();
      var ms = Math.max(0, et - st);
      var txt = ms >= 1000 ? (Math.round(ms / 10) / 100).toFixed(2) + 's' : Math.round(ms) + 'ms';
      var range = doorDefGetArcWidthRangeMm();
      if (!openings.length) showMsg('msg', '최대폭 ' + w + 'mm(범위 ' + range.min + '~' + range.max + ')로 재탐지했지만 결과가 없습니다. (' + txt + ')', 'info');
      else showMsg('msg', '최대폭 ' + w + 'mm 적용 재탐지: ' + openings.length + '개 후보 (범위 ' + range.min + '~' + range.max + ', ' + txt + ')', 'success');
      draw();
    });
  }
  if (clearBtn) clearBtn.addEventListener('click', function() {
    doorDefResetState({ keepLabel: true, keepDefinedSelection: true });
    doorDefSyncSelectionFromCandidates();
    showMsg('msg', '문 객체정의 상태를 초기화했습니다.', 'info');
  });
  if (autoApplyBtn) autoApplyBtn.addEventListener('click', function() { doorDefApplyAutoSelection(); });
  if (applyBtn) applyBtn.addEventListener('click', function() { doorDefApplyCandidates(); });
  if (selectAllChk) selectAllChk.addEventListener('change', function() {
    for (var i = 0; i < doorDefState.candidates.length; i++) {
      var c = doorDefState.candidates[i];
      doorDefState.checkedCandidateIds[c.candidate_id] = !!selectAllChk.checked;
    }
    doorDefState.selectedDefinedGroupId = '';
    if (doorDefState.candidates.length) {
      var firstChecked = doorDefState.candidates.find(function(c) { return doorDefState.checkedCandidateIds[c.candidate_id] !== false; });
      doorDefState.activeCandidateId = firstChecked ? firstChecked.candidate_id : 'origin';
    }
    doorDefSyncSelectionFromCandidates();
    doorDefRenderCandidateList();
  });
  if (listEl) listEl.addEventListener('change', function(e) {
    var target = e.target;
    if (!target || !target.matches || !target.matches('input[type="checkbox"][data-door-cid]')) return;
    var cid = String(target.getAttribute('data-door-cid') || '');
    if (!cid) return;
    doorDefState.checkedCandidateIds[cid] = !!target.checked;
    doorDefState.selectedDefinedGroupId = '';
    if (target.checked) doorDefState.activeCandidateId = cid;
    else if (String(doorDefState.activeCandidateId || '') === cid) doorDefState.activeCandidateId = 'origin';
    doorDefSyncSelectionFromCandidates();
    doorDefRenderCandidateList();
    draw();
  });
  if (listEl) listEl.addEventListener('click', function(e) {
    var target = e.target;
    if (!target || !target.closest) return;
    if (target.matches && target.matches('input[type="checkbox"][data-door-cid]')) return;
    var row = target.closest('[data-door-candidate]');
    if (!row) return;
    var cid = String(row.getAttribute('data-door-candidate') || '').trim();
    if (!cid) return;
    doorDefSetActiveCandidate(cid, { keepDefined: false });
    draw();
  });
  function onAutoClassListClick(e) {
    var target = e.target;
    if (!target || !target.closest) return;
    var adjustBtn = target.closest('[data-door-auto-adjust]');
    if (adjustBtn) {
      var classKeyAdj = String(adjustBtn.getAttribute('data-door-auto-class') || '').trim();
      var delta = parseInt(adjustBtn.getAttribute('data-door-auto-adjust') || '0', 10);
      if (!classKeyAdj || !(delta === 10 || delta === -10)) return;
      doorDefAdjustAutoClassWidth(classKeyAdj, delta, false);
      draw();
      return;
    }
    var row = target.closest('[data-door-auto-class]');
    if (!row) return;
    var key = String(row.getAttribute('data-door-auto-class') || '').trim();
    if (!key) return;
    doorDefSelectAutoClass(key, false);
    draw();
  }
  if (autoDoorClassListEl) autoDoorClassListEl.addEventListener('click', onAutoClassListClick);
  if (autoWindowClassListEl) autoWindowClassListEl.addEventListener('click', onAutoClassListClick);
  if (autoPartialClassListEl) autoPartialClassListEl.addEventListener('click', onAutoClassListClick);
  if (overlayChk) {
    overlayChk.checked = doorDefState.previewVisible !== false;
    overlayChk.addEventListener('change', function() {
      doorDefState.previewVisible = !!overlayChk.checked;
      draw();
    });
  }
  if (dimOthersChk) {
    dimOthersChk.checked = doorDefState.dimOthers === true;
    dimOthersChk.addEventListener('change', function() {
      doorDefState.dimOthers = !!dimOthersChk.checked;
      draw();
    });
  }
  if (overlayShapeSel) {
    var mode = String(doorDefState.previewShape || 'both');
    if (mode !== 'bbox' && mode !== 'circle' && mode !== 'both') mode = 'both';
    overlayShapeSel.value = mode;
    overlayShapeSel.addEventListener('change', function() {
      var v = String(overlayShapeSel.value || 'both');
      if (v !== 'bbox' && v !== 'circle' && v !== 'both') v = 'both';
      doorDefState.previewShape = v;
      draw();
    });
  }
  function selectDefinedFromInput(showNotice) {
    if (!definedListEl) return;
    var gid = String(definedListEl.value || '').trim();
    if (!gid) {
      doorDefState.selectedDefinedGroupId = '';
      if (doorDefState.seedIds && doorDefState.seedIds.length) {
        doorDefSyncSelectionFromCandidates();
        doorDefRenderCandidateList();
      }
      return;
    }
    doorDefSelectDefinedGroup(gid, !showNotice);
    doorDefRenderCandidateList();
    draw();
  }
  if (definedListEl) definedListEl.addEventListener('change', function() { selectDefinedFromInput(false); });
  if (definedSelectBtn) definedSelectBtn.addEventListener('click', function() { selectDefinedFromInput(true); });
  doorDefRefreshPanelState();
}


