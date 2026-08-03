"""시흥시 대시보드에 쓰는 행정동 경계를 GeoJSON으로 저장한다.

출처: OpenStreetMap contributors (ODbL). Nominatim 사용 정책을 따라 요청 사이에
1초 간격을 둔다. 최초 생성 또는 경계 갱신이 필요할 때만 실행한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "data" / "siheung_dong_boundaries.geojson"
AREAS = {
    "baegot": "배곧동",
    "jeongwang1": "정왕1동",
    "jeongwang2": "정왕2동",
    "daeya": "대야동",
    "sincheon": "신천동",
    "eunhaeng": "은행동",
}


def get_boundary(area_id: str, name: str) -> dict:
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{name}, 시흥시, 대한민국", "format": "jsonv2", "polygon_geojson": 1},
        headers={"User-Agent": "SNU-visualization-course-project/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    match = next(
        (
            item for item in response.json()
            if item.get("geojson", {}).get("type") in {"Polygon", "MultiPolygon"}
        ),
        None,
    )
    if not match:
        raise RuntimeError(f"{name}의 행정구역 경계를 찾지 못했습니다.")
    return {
        "type": "Feature",
        "id": area_id,
        "properties": {
            "id": area_id,
            "name": name,
            "center_lat": float(match["lat"]),
            "center_lng": float(match["lon"]),
            "source": "OpenStreetMap contributors",
            "source_url": f"https://www.openstreetmap.org/{match['osm_type']}/{match['osm_id']}",
        },
        "geometry": match["geojson"],
    }


def main() -> None:
    features = []
    for index, (area_id, name) in enumerate(AREAS.items()):
        features.append(get_boundary(area_id, name))
        if index < len(AREAS) - 1:
            time.sleep(1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(features)} boundaries)")


if __name__ == "__main__":
    main()
