"""Build the static dataset used by the Siheung Life Fit prototype.

The source CSV is left untouched.  The output contains only the fields the
browser needs, plus a compact administrative-dong summary.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "데이터" / "siheung_data" / "siheung_life_infra.csv"
OUTPUT = ROOT / "data" / "processed" / "life_fit.json"

CATEGORY_MAP = {
    "음식점": "food", "카페": "cafe", "코인세탁방": "laundry",
    "편의점": "convenience", "대형마트": "mart", "지하철역": "subway",
    "공원": "park", "병원": "hospital", "약국": "pharmacy",
}

AREAS = {
    "baegot": {"name": "배곧동", "match": "배곧동", "x": 20, "y": 66, "polygon": "5,50 28,38 43,55 35,84 9,81", "rent": 59, "jeonse": 18500, "sale": 28600, "station": "오이도역", "station_walk": 24, "bus": 31, "routes": 22},
    "jeongwang1": {"name": "정왕1동", "match": "정왕동", "x": 48, "y": 67, "polygon": "28,38 52,34 68,51 58,82 35,84 43,55", "rent": 52, "jeonse": 14200, "sale": 22100, "station": "정왕역", "station_walk": 9, "bus": 38, "routes": 29},
    "jeongwang2": {"name": "정왕2동", "match": "정왕동", "x": 77, "y": 65, "polygon": "52,34 82,37 96,53 89,82 58,82 68,51", "rent": 50, "jeonse": 13800, "sale": 20900, "station": "정왕역", "station_walk": 14, "bus": 34, "routes": 25},
    "daeya": {"name": "대야동", "match": "대야동", "x": 27, "y": 23, "polygon": "8,8 33,5 52,34 28,38 5,50", "rent": 57, "jeonse": 16700, "sale": 25400, "station": "시흥대야역", "station_walk": 8, "bus": 29, "routes": 24},
    "sincheon": {"name": "신천동", "match": "신천동", "x": 61, "y": 18, "polygon": "33,5 71,7 89,20 82,37 52,34", "rent": 55, "jeonse": 15800, "sale": 23900, "station": "신천역", "station_walk": 7, "bus": 27, "routes": 20},
    "eunhaeng": {"name": "은행동", "match": "은행동", "x": 85, "y": 24, "polygon": "71,7 96,11 98,34 96,53 82,37 89,20", "rent": 61, "jeonse": 19200, "sale": 29800, "station": "시흥대야역", "station_walk": 18, "bus": 25, "routes": 18},
}


def area_id(address: str, lng: float) -> str | None:
    for key, area in AREAS.items():
        if area["match"] in address and area["match"] != "정왕동":
            return key
    if "정왕동" in address:
        return "jeongwang1" if lng >= 126.735 else "jeongwang2"
    return None


def main() -> None:
    facilities = []
    with SOURCE.open(encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            category = CATEGORY_MAP.get(row.get("검색카테고리", ""))
            if not category:
                continue
            try:
                lng, lat = float(row["x"]), float(row["y"])
            except (TypeError, ValueError):
                continue
            area = area_id(row.get("address_name", ""), lng)
            if not area:
                continue
            facilities.append({
                "id": row.get("id", ""), "area": area, "category": category,
                "name": row.get("place_name", ""), "detail": row.get("category_name", ""),
                "address": row.get("road_address_name") or row.get("address_name", ""),
                "phone": row.get("phone", ""), "lng": lng, "lat": lat,
                "url": row.get("place_url", ""),
            })

    result_areas = []
    for key, base in AREAS.items():
        counts = Counter(f["category"] for f in facilities if f["area"] == key)
        area = {k: v for k, v in base.items() if k != "match"}
        area.update({"id": key, "counts": dict(counts)})
        result_areas.append(area)

    result = {
        "meta": {
            "project_name": "시흥생활핏",
            "subtitle": "시흥시 1인 가구 맞춤 생활 인프라 지도",
            "updated_at": "2026-08-07",
            "notice": "시설 위치는 제공된 카카오 장소 수집본을, 주거비·교통은 프로토타입용 행정동 요약값을 사용합니다.",
        },
        "areas": result_areas,
        "facilities": facilities,
        "sources": [
            {"name": "생활 인프라", "organization": "카카오 Local 기반 수집본", "scope": "음식점·카페·생활편의·의료·공원·지하철"},
            {"name": "행정동 경계", "organization": "OpenStreetMap contributors", "scope": "시흥시 6개 비교 지역"},
            {"name": "주거비·교통", "organization": "MVP 프로토타입", "scope": "화면 검증용 요약값"},
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(result_areas)} areas, {len(facilities)} facilities")


if __name__ == "__main__":
    main()
