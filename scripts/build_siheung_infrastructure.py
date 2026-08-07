"""시흥시 생활시설 수집본을 지도용 데이터로 정제한다.

원본은 juyeon 브랜치의 카카오 장소 수집 CSV이며, 지도에는 배곧·정왕1·2·대야·신천·은행
6개 비교 생활권만 넣는다. 선택 카테고리별 색상 계산은 브라우저에서 수행한다.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "데이터" / "siheung_data" / "siheung_life_infra.csv"
OUTPUT = ROOT / "data" / "processed" / "siheung_infrastructure.json"

CATEGORY_MAP = {
    "음식점": "food", "카페": "cafe", "코인세탁방": "laundry", "편의점": "convenience",
    "대형마트": "mart", "지하철역": "subway", "공원": "park", "병원": "hospital", "약국": "pharmacy",
}
CATEGORY_LABELS = {
    "food": "음식점", "cafe": "카페", "laundry": "코인세탁방", "convenience": "편의점",
    "mart": "대형마트", "subway": "지하철역", "park": "공원", "hospital": "병원", "pharmacy": "약국",
}
AREAS = {
    "baegot": {"name": "배곧동", "match": "배곧동", "center": [37.3690909, 126.7208477]},
    "jeongwang1": {"name": "정왕1동", "match": "정왕동", "center": [37.3328622, 126.7361104]},
    "jeongwang2": {"name": "정왕2동", "match": "정왕동", "center": [37.3318474, 126.6598047]},
    "daeya": {"name": "대야동", "match": "대야동", "center": [37.4551254, 126.8013314]},
    "sincheon": {"name": "신천동", "match": "신천동", "center": [37.4396138, 126.7788556]},
    "eunhaeng": {"name": "은행동", "match": "은행동", "center": [37.4334715, 126.8093504]},
}


def area_id(address: str, lng: float) -> str | None:
    for key, area in AREAS.items():
        if area["match"] in address and area["match"] != "정왕동":
            return key
    if "정왕동" in address:
        return "jeongwang1" if lng >= 126.735 else "jeongwang2"
    return None


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"원본 CSV가 없습니다: {SOURCE}")
    facilities: list[dict] = []
    seen_ids: set[str] = set()
    skipped = Counter()
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            category = CATEGORY_MAP.get(row.get("검색카테고리", ""))
            if not category:
                skipped["unsupported_category"] += 1
                continue
            place_id = row.get("id", "").strip()
            if not place_id or place_id in seen_ids:
                skipped["duplicate_or_missing_id"] += 1
                continue
            try:
                lng, lat = float(row["x"]), float(row["y"])
            except (KeyError, TypeError, ValueError):
                skipped["invalid_coordinate"] += 1
                continue
            area = area_id(row.get("address_name", ""), lng)
            if not area:
                skipped["outside_comparison_area"] += 1
                continue
            seen_ids.add(place_id)
            facilities.append({
                "id": place_id, "area_id": area, "category": category,
                "name": row.get("place_name", "").strip(),
                "address": (row.get("road_address_name") or row.get("address_name") or "").strip(),
                "lng": lng, "lat": lat, "url": row.get("place_url", "").strip(),
            })

    areas = []
    for area_id_value, area in AREAS.items():
        counts = Counter(facility["category"] for facility in facilities if facility["area_id"] == area_id_value)
        areas.append({"id": area_id_value, "name": area["name"], "center": area["center"], "counts": dict(counts), "facility_total": sum(counts.values())})
    result = {
        "meta": {
            "project_name": "시흥 공공주택 생활 인프라 지도",
            "period": "수집본 기준",
            "updated_at": date.today().isoformat(),
            "notice": "시설 수는 카카오 장소 기반 수집본의 행정동 배정 결과입니다. 선택 카테고리의 수집 건수를 비교하며, 실제 도보거리·면적·인구를 보정한 인프라 밀도는 아닙니다.",
        },
        "categories": [{"id": category, "label": label} for category, label in CATEGORY_LABELS.items()],
        "areas": areas,
        "facilities": facilities,
        "sources": [
            {"name": "생활 인프라 수집본", "organization": "카카오 장소 기반 제공 데이터", "description": "시흥시 6개 비교 생활권의 장소명·카테고리·좌표"},
            {"name": "행정동 경계", "organization": "OpenStreetMap contributors", "description": "배곧·정왕1·2·대야·신천·은행동 경계"},
        ],
        "quality": {"raw_rows": 2123, "usable_rows": len(facilities), "skipped": dict(skipped)},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: facilities={len(facilities):,}")


if __name__ == "__main__":
    main()
