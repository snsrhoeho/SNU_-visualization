"""수도권 시·군·구 경계를 GeoJSON으로 저장한다.

출처: OpenStreetMap contributors (ODbL). Nominatim 공개 API 정책에 맞춰 요청은
초당 1회만 보낸다. 경계 파일은 최초 생성·갱신 때만 만든다.
"""
from __future__ import annotations

import json
import time
import argparse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "capital_private_preview.json"
OUTPUT = ROOT / "static" / "data" / "capital_sigungu_boundaries.geojson"
USER_AGENT = "SNU-visualization-course-project/1.0 (educational dashboard)"


def get_boundary(area: dict) -> dict:
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": f"{area['name']}, {area['sido']}, 대한민국",
            "format": "jsonv2",
            "polygon_geojson": 1,
            "limit": 5,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    match = next(
        (item for item in response.json() if item.get("geojson", {}).get("type") in {"Polygon", "MultiPolygon"}),
        None,
    )
    if not match:
        raise RuntimeError(f"{area['sido']} {area['name']}의 경계를 찾지 못했습니다.")
    return {
        "type": "Feature",
        "id": area["id"],
        "properties": {
            "id": area["id"],
            "name": area["name"],
            "sido": area["sido"],
            "center_lat": float(match["lat"]),
            "center_lng": float(match["lon"]),
            "source": "OpenStreetMap contributors",
            "source_url": f"https://www.openstreetmap.org/{match['osm_type']}/{match['osm_id']}",
        },
        "geometry": match["geojson"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0, help="대시보드 지역 목록에서 시작 위치")
    parser.add_argument("--limit", type=int, default=12, help="한 번에 받을 최대 지역 수")
    args = parser.parse_args()
    dashboard = json.loads(INPUT.read_text(encoding="utf-8"))
    existing = {"type": "FeatureCollection", "features": [], "failures": []}
    if OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
    features_by_id = {feature["id"]: feature for feature in existing.get("features", [])}
    failures_by_id = {failure["id"]: failure for failure in existing.get("failures", [])}
    targets = dashboard["areas"][args.offset : args.offset + args.limit]
    for index, area in enumerate(targets):
        if area["id"] in features_by_id:
            print(f"skip {area['sido']} {area['name']}", flush=True)
            continue
        try:
            feature = get_boundary(area)
            features_by_id[area["id"]] = feature
            failures_by_id.pop(area["id"], None)
            print(f"saved {area['sido']} {area['name']}", flush=True)
        except (requests.RequestException, RuntimeError) as error:
            failures_by_id[area["id"]] = {"id": area["id"], "name": area["name"], "error": str(error)}
            print(f"failed {area['sido']} {area['name']}: {error}", flush=True)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps({"type": "FeatureCollection", "features": list(features_by_id.values()), "failures": list(failures_by_id.values())}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if index < len(targets) - 1:
            time.sleep(1)
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(features_by_id)} boundaries, {len(failures_by_id)} failures")


if __name__ == "__main__":
    main()
