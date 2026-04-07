# 수평 벽체 끝단 미채움 원인 분석 및 Junction-Aware 벽체 채움 설계

## 1. 대표 현상: 수평 벽체가 수직 구조선/벽체와 만나는 끝단에서 채움이 노란 골조선까지 도달하지 못함

### 1.1 현재 파이프라인 요약

코드 기준으로 현재 벽체 채움은 다음 순서로 동작한다.

```
[Raw segments] → [Tracks] → [Pairs + overlap_intervals] → [Parts (seg_a, seg_b)] → [Base quad + Join patches] → [Hatch/표시]
```

- **Track**: 동일 축에 가까운 선분들을 모아 만든 “한 줄” 단위. 각 track은 `intervals`/`samples`로 **원본 선분 구간**만 가진다. 선분 끝을 교차점/접합부까지 **연장·스냅하는 단계는 없다.**
- **Pair**: 두 track이 겹치는 구간을 `overlap_intervals`(파라미터 [s,e])로 계산. 다른 pair가 쓰는 구간은 `reserved`로 빼서, **각 벽체가 “가져갈 수 있는 구간”만** 남긴다.
- **Part**: `frameDefBuildWallPartsFromTrackPair`에서 `overlap_intervals`의 각 [s,e]에 대해 **track 위 s, e 위치의 점**으로 `seg_a`, `seg_b`를 만든다. 즉 part의 길이는 **원본 overlap 구간 그대로**이다.
- **Base quad**: `frameDefWallOverlapQuad(part)`가 `seg_a`·`seg_b`를 축에 투영해 **겹치는 t 구간**만으로 사각형을 만든다. part가 짧으면 quad도 그만큼 짧다.
- **Join patch**: 인접 벽체와의 corner/T/collinear 관계를 찾아 `frameDefWallCornerJoinPolygon` 등으로 **추가 폴리곤**을 그린다. 다만 이 patch는 **이미 정해진 part의 끝단(seg_a/seg_b 끝)**을 기준으로 하므로, part가 교차점 전에서 끊겨 있으면 patch도 “끊긴 끝”에서만 이어 붙는다.

정리하면, **채움의 끝단은 “원본 선분의 overlap 구간 끝”에서 결정**되며, “노란 골조선(실제 교차/접합 위치)”까지 **끝을 밀어 넣는 로직이 전혀 없다.**

---

### 1.2 왜 수평 벽체 끝단이 노란선까지 안 닿는가 (근본 원인)

- **원인 1: 선 토폴로지 미구성**  
  - 골조선 네트워크(끝점·교차점·near-touch를 기준으로 한 junction node)를 만들지 않는다.  
  - 따라서 “이 선의 유효 끝”이 **원본 엔티티 끝**으로 고정되어 있고, **교차점/접합부 경계**로 스냅·연장되지 않는다.

- **원인 2: 채움 범위 = overlap interval 그대로**  
  - 수평 track의 overlap_intervals는 **원본 수평 선분의 [s,e]**에서 나온다.  
  - 수직 벽/구조선과의 **교차점**이 s 또는 e 밖에 있으면, 그 교차점은 interval에 반영되지 않는다.  
  - Part의 `seg_a`/`seg_b`는 “track 위 s, e”이므로, **끝이 교차점 전에서 끊긴 상태**로 고정된다.

- **원인 3: 끝단 연장 개념 부재**  
  - “벽체 끝단은 원래 선분 끝이 아니라, **가장 가까운 유효 접합 경계(junction boundary)**까지 연장”한다는 규칙이 없다.  
  - 그래서 **fill 종료 조건이 raw endpoint**이고, resolved junction boundary가 아니다.

- **원인 4: Join patch가 “끊긴 끝” 기준**  
  - L/T junction patch는 **현재 part의 끝단(seg_a/seg_b 끝)**을 기준으로 만들어진다.  
  - Part가 이미 교차점 전에서 끊겨 있으므로, patch를 아무리 잘 그려도 **끊긴 끝 ↔ 수직 벽** 사이를 메울 뿐, **수평 벽 채움 자체를 노란선(교차점)까지 늘리지는 않는다.**

따라서 “수평 벽체가 수직 구조선/벽체와 만나는 끝단에서 채움이 노란 골조선까지 도달하지 못하는” 현상은,  
**선 단위 topology/junction을 만들지 않고, 채움 범위를 overlap interval(원본 선분 구간)에만 묶어 두기 때문**으로 요약할 수 있다.

---

## 2. 요구사항과 현재 구조의 갭

| 요구사항 | 현재 구조 | 갭 |
|----------|-----------|-----|
| 1. 선분 단위 offset이 아니라 **골조선 네트워크** 먼저 구성, endpoint/intersection/near-touch로 junction node | Track은 “같은 축 선분 묶음”만 있고, 끝점·교차점을 모아 **junction node를 만드는 단계 없음** | topology 단계 없음 |
| 2. 벽체 끝단은 **가장 가까운 유효 접합 경계까지 연장** (교차/기둥/구조경계/동방향 near-touch) | Part/quad 범위 = overlap_intervals의 [s,e] 그대로, 연장 없음 | 연장 로직 없음 |
| 3. L/T/Cross/Column-adjacent 등 **접합부 유형별 보정** (corner closing, junction patch) | Corner/T patch는 있으나, part 끝이 이미 “끊긴 끝”이라 patch만으로는 교차점까지 채움 불가 | part 끝이 junction까지 안 나감 |
| 4. 순서: 골조선 추출 → 선 정리/병합/스냅 → 교차·접합 해석 → **유효 연장 범위** → 접합부 patch → 외곽 polygon → 검증·미세 gap 제거 | 현재: segment → track → pair → interval → part → quad + patch. **선 정리·교차 해석·유효 연장** 단계 없음 | 단계 순서·내용 불일치 |
| 5. 미세 gap 후처리: 두께/방향/인접 구조선 관계가 맞을 때만 geometric closing, 잘못된 bridging 방지 | 갭은 “빈벽” 이슈로 수집되나, **채움 연장·bridging 보호** 규칙은 없음 | 후처리 기준 없음 |
| 6. 수평–수직 끝단 채움이 노란선까지 도달 | 위 1~4 미구현으로 **끝단이 raw endpoint에서 멈춤** | 동일 원인 |

---

## 3. Junction-Aware 벽체 채움으로 바꾸는 방식

요구사항 1~6을 만족하려면, **“선 토폴로지 → 접합부 해석 → 유효 연장 범위 → 접합부별 patch → 최종 면”** 순서로 가는 파이프라인이 필요하다.

### 3.1 목표 파이프라인 (요구 4 반영)

```
1. 벽체 골조선 추출
   - 인식된 벽체/구조선의 중심선(또는 외곽선 쌍)에서 골조선 세그먼트 추출

2. 선 정리/병합/스냅
   - 동일 직선상·tolerance 내 선분 병합
   - 끝점을 tolerance 내 다른 끝점/교차점에 스냅

3. 교차 및 접합부 해석
   - 모든 골조선에 대해 교차점 계산 (선-선, 선-기둥/구조경계)
   - tolerance 안의 끝점/교차점을 하나의 “junction node”로 통합
   - Junction 유형 분류: L, T, Cross, Column-adjacent, End(open) 등

4. 각 벽체 구간의 유효 연장 범위 결정
   - 벽체(또는 track) 단위로, “이 선이 채워져야 하는 구간”을 정의
   - 시작/끝을 **raw endpoint가 아니라** “가장 가까운 유효 junction 경계”로 설정
     - 다른 골조선과 교차: 교차점까지 연장
     - 기둥/구조 경계와 만남: 해당 면/기준선까지 연장
     - 같은 방향 near-touch: tolerance 내면 연결된 것으로 보고 한 구간으로

5. 접합부별 corner patch / closing 처리 (요구 3)
   - L: 두 벽체 외곽면이 자연스럽게 코너를 닫도록 patch
   - T: 들어오는 벽 끝단이 주벽 외곽면/중심에 정확히 닿도록 보정
   - Cross: 4방향 면이 빈틈 없이 닫히도록
   - Column-adjacent: 벽체가 기둥 면/구조 기준선까지 채워지도록

6. 최종 외곽 polygon 생성
   - 연장된 구간으로 offset(두께) 적용 → 각 벽체별 폴리곤
   - 접합부 patch로 코너/끝단 메우기
   - 단순 “선분별 offset 결과를 그대로 쓰지 않고”, 위 1~5 결과를 기반으로 생성

7. Polygon 검증 및 작은 gap 제거 (요구 5)
   - 아주 작은 gap은 geometric closing 후보
   - 벽체 두께/방향/인접 구조선 관계가 맞을 때만 메우기
   - 잘못된 bridging으로 다른 공간이 합쳐지지 않도록 보호 조건 적용
```

이 순서를 지키면 “offset → 바로 hatch”가 아니라 **topology → junction → 연장 → patch → polygon → 검증**이 된다.

### 3.2 수평–수직 끝단 케이스를 이렇게 해결

- **1단계(골조선 네트워크)**  
  수평 벽 중심선과 수직 벽/구조선을 모두 골조선으로 넣고, **교차점**을 계산해 둔다.

- **2~3단계(선 정리 + 접합부 해석)**  
  수평선 끝점이 수직선과 tolerance 안에 있거나, 연장 시 교차하면 **같은 junction**으로 묶고, 그 junction을 “수평선의 유효 끝”으로 쓸 수 있게 한다.

- **4단계(유효 연장 범위)**  
  수평 벽체의 “채움 구간” 끝을 **원본 선분 끝**이 아니라 **그 junction(교차점)까지**로 정한다.  
  → Part(또는 이에 대응하는 “벽체 구간”)의 seg_a/seg_b 끝이 **노란선(교차점)**에 오게 된다.

- **5~6단계(patch + polygon)**  
  이미 끝이 교차점까지 연장되어 있으므로, L/T junction patch는 **노란선 위치**를 기준으로 자연스럽게 코너를 닫고, **채움도 노란선까지 도달**한다.

즉, **끝단 조건을 “raw endpoint”에서 “resolved junction boundary”로 바꾸고**, 그 junction까지 **구간을 연장해 두는 것**이 핵심이다.

### 3.3 구현 시 유의점 (요구 1, 2, 5 반영)

- **Junction node 통합 (요구 1)**  
  - 끝점·교차점을 수집한 뒤, **거리 tolerance**로 클러스터링하거나 같은 node로 merge.  
  - “tolerance 안에 있으면 동일 접합부”를 코드에서 한 곳에서만 정의해 일관 적용.

- **연장 규칙 (요구 2)**  
  - “가장 가까운 유효 접합 경계”를 구할 때:  
    다른 골조선과의 교차, 기둥/구조 경계, 동일 방향 near-touch를 모두 후보로 두고, **벽체 방향으로 가장 가까운 것**을 선택.  
  - Fill 종료 조건을 **이 경계**로 두고, overlap_intervals 또는 이에 대응하는 “유효 구간”을 이 경계 기준으로 다시 계산해야 한다.

- **미세 gap 후처리 (요구 5)**  
  - 작은 gap을 메울 때:  
    - 벽 두께·방향이 인접 벽/구조와 맞는지,  
    - 인접 구조선과의 관계(같은 방향인지, 교차인지)가 맞는지 확인.  
  - 조건을 만족하지 않으면 bridging하지 않아, 다른 공간이 합쳐지지 않도록 한다.

---

## 4. 정리

- **현상**: 수평 벽체가 수직 구조선과 만나는 끝단에서 채움이 노란 골조선까지 도달하지 못함.  
- **원인**:  
  - 선 단위 **topology/junction을 만들지 않음**,  
  - 채움 범위가 **overlap_intervals(원본 선분 구간)**에만 묶여 있음,  
  - 끝단을 **교차점(junction boundary)까지 연장하는 단계가 없음**,  
  - Join patch는 “이미 끊긴 끝” 기준이라 채움 연장 효과 없음.  

- **해결 방향**:  
  - **벽체 골조선 네트워크**를 만들고,  
  - **끝점·교차점·near-touch를 junction node로 통합**한 뒤,  
  - **각 벽체 구간의 유효 끝을 “가장 가까운 유효 접합 경계”로 연장**하고,  
  - 이 **연장된 구간**으로 면 생성과 접합부 patch를 적용하며,  
  - 마지막에 **polygon 검증과 미세 gap 후처리(보호 조건 포함)**를 두는,  
  **junction-aware wall fill** 로직으로 전환하는 것이 필요하다.

이 문서는 `frame_object_define.js`의 현재 동작을 분석한 결과와, 위 요구사항 1~6에 맞춘 설계 방향을 담고 있으며, 실제 구현 시 참고용으로 사용할 수 있다.
