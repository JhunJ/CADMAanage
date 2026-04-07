"""
테스트용 샘플 DXF 생성.
실행 후 프로젝트 루트에 sample.dxf 가 생성됩니다.
"""
import io
import sys
from pathlib import Path

import ezdxf

# 프로젝트 루트 = 스크립트 기준 상위
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "sample.dxf"


def main():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # LINE
    msp.add_line((0, 0), (100, 100), dxfattribs={"layer": "0", "color": 1})
    # CIRCLE
    msp.add_circle((50, 50), radius=20, dxfattribs={"layer": "0", "color": 2})
    # LWPOLYLINE (사각형)
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True, dxfattribs={"layer": "0", "color": 3})
    # TEXT
    msp.add_text("CAD Manage Sample", dxfattribs={"layer": "0", "color": 1}).set_placement((10, 80))

    buf = io.StringIO()
    doc.write(buf)
    OUTPUT.write_text(buf.getvalue(), encoding="utf-8")
    print(f"Created: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
