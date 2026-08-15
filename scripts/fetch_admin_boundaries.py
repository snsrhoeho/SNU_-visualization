"""시흥시 생활권 비교에 쓰는 전체 법정동 경계를 GeoJSON으로 저장한다.

출처: OpenStreetMap contributors (ODbL). Nominatim 사용 정책을 따라 요청 사이에
1초 간격을 둔다. 최초 생성 또는 경계 갱신이 필요할 때만 실행한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "data" / "siheung_dong_boundaries.geojson"
LIFE_FIT = ROOT / "data" / "processed" / "life_fit.json"


def legal_dongs() -> dict[str, str]:
    data = json.loads(LIFE_FIT.read_text(encoding="utf-8"))
    return {area["name"]: area["name"] for area in data["areas"]}


def get_boundary(area_id: str, name: str) -> dict:
    query = urlencode({"q": f"{name}, 시흥시, 대한민국", "format": "jsonv2", "polygon_geojson": 1})
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{query}",
        headers={"User-Agent": "SNU-visualization-course-project/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    candidates = [item for item in payload if item.get("geojson", {}).get("type") in {"Polygon", "MultiPolygon"}]
    match = next((item for item in candidates if item.get("type") == "legal"), candidates[0] if candidates else None)
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
            "boundary_type": match.get("type"),
            "source": "OpenStreetMap contributors",
            "source_url": f"https://www.openstreetmap.org/{match['osm_type']}/{match['osm_id']}",
        },
        "geometry": match["geojson"],
    }


def main() -> None:
    areas = legal_dongs()
    features = []
    for index, (area_id, name) in enumerate(areas.items()):
        features.append(get_boundary(area_id, name))
        if index < len(areas) - 1:
            time.sleep(1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(features)} boundaries)")


if __name__ == "__main__":
    main()
