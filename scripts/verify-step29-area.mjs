/**
 * ②-9 / ②-8 면적 대조에 쓰이는 polygonAreaAbs(동일 shoelace)와
 * 허용 오차(1.5mm²) 일치 판정을 Node로 검증합니다.
 */
function polygonAreaAbs(poly) {
  if (!Array.isArray(poly) || poly.length < 3) return 0;
  var a = 0;
  for (var i = 0; i < poly.length; i++) {
    var j = (i + 1) % poly.length;
    var p = poly[i] || {};
    var q = poly[j] || {};
    a += (Number(p.x) || 0) * (Number(q.y) || 0) - (Number(q.x) || 0) * (Number(p.y) || 0);
  }
  return Math.abs(a) * 0.5;
}

function round1(x) {
  return Math.round(Number(x) * 10) / 10;
}

var tol = 1.5;

// 직사각 10×10 = 100
var rect = [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 10, y: 10 },
  { x: 0, y: 10 }
];
console.assert(Math.abs(polygonAreaAbs(rect) - 100) < 1e-6, 'rect 10x10');

// L자: 10×10 - 5×5 = 75
var lshape = [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 10, y: 5 },
  { x: 5, y: 5 },
  { x: 5, y: 10 },
  { x: 0, y: 10 }
];
console.assert(Math.abs(polygonAreaAbs(lshape) - 75) < 1e-3, 'L-shape');

// ②-9 입력 합 vs ②-8 ref (시뮬)
var srcSum = round1(polygonAreaAbs(rect) + polygonAreaAbs(lshape));
var ref28 = round1(175);
var delta = round1(srcSum - ref28);
var match = Math.abs(delta) <= tol + 1e-9;
console.assert(match === true, '175 vs 175 delta');

var refBad = round1(180);
var deltaBad = round1(srcSum - refBad);
var matchBad = Math.abs(deltaBad) <= tol + 1e-9;
console.assert(matchBad === false, '175 vs 180 should not match');

console.log('verify-step29-area: ok (shoelace + tolerance logic)');
