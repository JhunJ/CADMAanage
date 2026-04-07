"""fingerprint 서비스 유닛 테스트."""
import pytest
from app.services.fingerprint import (
    fingerprint_line,
    fingerprint_polyline,
    fingerprint_circle,
    fingerprint_text,
    fingerprint_block_insert,
    get_tolerance_from_settings,
    DEFAULT_TOLERANCE_MM,
)


def test_fingerprint_line_deterministic():
    fp1 = fingerprint_line((0, 0, 0), (10, 10, 0), "LINE", "0", 1, None)
    fp2 = fingerprint_line((0, 0, 0), (10, 10, 0), "LINE", "0", 1, None)
    assert fp1 == fp2


def test_fingerprint_line_order_normalized():
    # (작은 점, 큰 점) 순서로 정규화
    fp1 = fingerprint_line((0, 0, 0), (10, 10, 0), "LINE", "0", 0, None)
    fp2 = fingerprint_line((10, 10, 0), (0, 0, 0), "LINE", "0", 0, None)
    assert fp1 == fp2


def test_fingerprint_line_different_layer_different_hash():
    fp1 = fingerprint_line((0, 0, 0), (1, 1, 0), "LINE", "0", 0, None)
    fp2 = fingerprint_line((0, 0, 0), (1, 1, 0), "LINE", "1", 0, None)
    assert fp1 != fp2


def test_fingerprint_polyline():
    points = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
    fp = fingerprint_polyline(points, False, "LWPOLYLINE", "0", 0, None)
    assert isinstance(fp, str)
    assert len(fp) == 32


def test_fingerprint_circle():
    fp = fingerprint_circle((5, 5, 0), 3.0, "CIRCLE", "0", 1, None)
    assert isinstance(fp, str)
    assert len(fp) == 32


def test_fingerprint_text():
    fp = fingerprint_text((0, 0, 0), "Hello", "TEXT", "0", 0, None)
    assert isinstance(fp, str)
    fp2 = fingerprint_text((0, 0, 0), "World", "TEXT", "0", 0, None)
    assert fp != fp2


def test_fingerprint_block_insert():
    fp = fingerprint_block_insert(
        "BLOCK1", (1, 2, 0), 0.5, 1.0, 1.0, 1.0, "0", 0,
        [("TAG1", "VAL1")],
    )
    assert isinstance(fp, str)


def test_get_tolerance_from_settings():
    assert get_tolerance_from_settings(None) == DEFAULT_TOLERANCE_MM
    assert get_tolerance_from_settings({}) == DEFAULT_TOLERANCE_MM
    assert get_tolerance_from_settings({"fp_tolerance_mm": 2.5}) == 2.5
