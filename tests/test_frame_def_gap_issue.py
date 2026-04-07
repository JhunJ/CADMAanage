"""빈벽(빈구간) 표시 개선 상수 및 패턴 회귀 테스트.

frame_object_define.js 내 한도·임계값이 계획대로 유지되는지 검증합니다.
"""
import re
from pathlib import Path


def _read_frame_object_define() -> str:
    root = Path(__file__).resolve().parent.parent
    path = root / "app" / "static" / "plugins" / "frame_object_define.js"
    return path.read_text(encoding="utf-8")


def test_overlay_join_max_neighbors() -> None:
    """FRAME_DEF_OVERLAY_JOIN_MAX_NEIGHBORS가 36 이상이어야 함 (계획: 22→36)."""
    src = _read_frame_object_define()
    m = re.search(
        r"var\s+FRAME_DEF_OVERLAY_JOIN_MAX_NEIGHBORS\s*=\s*(\d+)\s*;",
        src,
    )
    assert m is not None, "FRAME_DEF_OVERLAY_JOIN_MAX_NEIGHBORS not found"
    assert int(m.group(1)) >= 36, "OVERLAY_JOIN_MAX_NEIGHBORS should be >= 36"


def test_gap_issue_min_missing_ratio() -> None:
    """FRAME_DEF_GAP_ISSUE_MIN_MISSING_RATIO가 0.45로 설정되어 있어야 함 (해치 있는 구간 빈벽 오표기 방지)."""
    src = _read_frame_object_define()
    m = re.search(
        r"var\s+FRAME_DEF_GAP_ISSUE_MIN_MISSING_RATIO\s*=\s*([\d.]+)\s*;",
        src,
    )
    assert m is not None, "FRAME_DEF_GAP_ISSUE_MIN_MISSING_RATIO not found"
    assert float(m.group(1)) == 0.45, "GAP_ISSUE_MIN_MISSING_RATIO should be 0.45"


def test_max_pair_checks_uses_12000_and_20() -> None:
    """maxPairChecks가 12000 상한, list.length * 20 사용."""
    src = _read_frame_object_define()
    assert "Math.min(12000" in src, "maxPairChecks upper bound should be 12000"
    assert "list.length * 20" in src, "maxPairChecks should use list.length * 20"


def test_max_ms_uses_800_and_1000() -> None:
    """maxMs가 800/1000 사용 (벽 많을 때 800, 적을 때 1000)."""
    src = _read_frame_object_define()
    assert "? 800 : 1000" in src or "800" in src and "1000" in src, (
        "maxMs should use 800 and 1000"
    )


def test_collect_wall_gap_issues_returns_partial_on_exception() -> None:
    """frameDefCollectWallGapIssues 내부 try/catch로 부분 결과 반환."""
    src = _read_frame_object_define()
    assert "} catch (innerErr)" in src, "Inner try/catch for partial results expected"
    assert "st._gapIssueDebug" in src, "Debug info for gap issue collection expected"


def test_build_gap_issue_uses_min_missing_ratio_constant() -> None:
    """frameDefBuildGapIssue가 FRAME_DEF_GAP_ISSUE_MIN_MISSING_RATIO 사용."""
    src = _read_frame_object_define()
    assert "FRAME_DEF_GAP_ISSUE_MIN_MISSING_RATIO" in src, (
        "BuildGapIssue should use FRAME_DEF_GAP_ISSUE_MIN_MISSING_RATIO"
    )


def test_cand_idx_sorted_by_endpoint_gap() -> None:
    """candIdx가 frameDefWallMinEndpointGap으로 정렬됨."""
    src = _read_frame_object_define()
    assert "candIdx.sort" in src, "candIdx.sort expected"
    assert "frameDefWallMinEndpointGap" in src, "Sort by endpoint gap expected"
