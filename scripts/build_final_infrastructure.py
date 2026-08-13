"""`데이터 정제후`의 최종 CSV만으로 생활 인프라 JSON을 만든다.

이 스크립트는 이전 수집본과 병합하지 않는다. 좌표가 있는 행은 시흥시
행정동 경계 안에 직접 배정하고, 경계 밖·좌표 누락 행은 품질 통계에만
남긴다. 따라서 지도에서 실제 위치가 아닌 임의의 동 중심점은 만들지 않는다.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "데이터 정제후"
BOUNDARIES = ROOT / "static" / "data" / "siheung_admin_dong_boundaries.geojson"
OUTPUT = ROOT / "data" / "processed" / "siheung_infrastructure.json"

GROUPS = [
    ("rest", "휴식·운동", "🌿", "#2e8e59"),
    ("shopping", "쇼핑·유통", "🛒", "#b87921"),
    ("health", "의료·건강", "🏥", "#d94f5d"),
    ("pet", "반려동물", "🐾", "#b46437"),
    ("food", "음식·카페", "🍜", "#e85c3e"),
    ("life", "생활편의", "🫧", "#397ec1"),
    ("culture", "문화", "🎭", "#8b5cf6"),
    ("safety", "치안·안전", "🛡️", "#475569"),
    ("education", "교육", "🏫", "#247a9b"),
]

# 파일명 일부: (category id, 화면 표기, 분야, density_only)
SOURCES = {
    "1-1.": ("park", "공원", "rest", False),
    "1-2.": ("play_experience", "놀이·체험시설", "rest", False),
    "1-3.": ("sports", "체육시설", "rest", False),
    "1-4.": ("gym", "헬스장", "rest", False),
    "2-1.": ("large_mart", "대형마트", "shopping", False),
    "2-2.": ("small_mart", "소형마트", "shopping", False),
    "2-3.": ("grocery_mart", "식자재마트", "shopping", False),
    "2-4.": ("convenience", "편의점", "shopping", False),
    "3-1.": ("hospital", "병원", "health", False),
    "3-2.": ("pharmacy", "약국", "health", False),
    "3-3.": ("health_center", "보건소", "health", False),
    "4_siheung_동물병원": ("animal_hospital", "동물병원", "pet", False),
    "4_siheung_반려동물시설": ("pet_facility", "반려동물시설", "pet", False),
    "5'.": ("restaurant", "음식점", "food", False),
    "6.": ("cafe", "카페", "food", False),
    "7_siheung_목욕탕": ("bathhouse", "목욕탕", "life", False),
    "7_siheung_코인세탁방": ("laundry", "코인세탁방", "life", False),
    "8_siheung_관람시설": ("venue", "관람시설", "culture", False),
    "8_siheung_도서관": ("library", "도서관", "culture", False),
    "9_siheung_CCTV": ("cctv", "CCTV", "safety", True),
    "9_siheung_경찰관서": ("police", "경찰관서", "safety", False),
    "9_siheung_민방위": ("civil_defense", "민방위대피시설", "safety", True),
    "9_siheung_소방": ("fire", "소방관서", "safety", False),
    "9_siheung_안전비상벨": ("emergency_bell", "안전비상벨", "safety", True),
    "9_siheung_어린이": ("child_zone", "어린이보호구역", "safety", True),
    "10_siheung_초등": ("elementary_school", "초등학교", "education", False),
    "10_siheung_중학교": ("middle_school", "중학교", "education", False),
    "10_siheung_고등": ("high_school", "고등학교", "education", False),
}

NAME_KEYS = (
    "기관명", "시설명", "시설명", "사업장명", "place_name", "병원명", "학교명",
    "대상시설명", "소방서및안전센터명", "기관명", "관리기관명", "시설위치", "업종명",
    "bizplcnm", "librrynm", "시설구분",
)
ADDRESS_MARKERS = ("주소", "위치")
LAT_MARKERS = ("위도", "lat")
LNG_MARKERS = ("경도", "logt", "lng")


def normalized(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def text(row: dict[str, str], *keys: str) -> str:
    targets = {normalized(key) for key in keys}
    for key, value in row.items():
        if normalized(key) in targets and str(value or "").strip():
            return str(value).strip()
    return ""


def name_for(row: dict[str, str], fallback: str) -> str:
    name = text(row, *NAME_KEYS)
    if name:
        return name
    # 이름 열을 특정하지 못한 경우 ID·코드 열은 제외한다.
    for key, value in row.items():
        key_norm = normalized(key)
        value = str(value or "").strip()
        if value and not any(token in key_norm for token in ("id", "코드", "주소", "위도", "경도", "전화")):
            return value
    return fallback


def address_for(row: dict[str, str]) -> str:
    candidates = [str(value or "").strip() for key, value in row.items() if any(marker in key for marker in ADDRESS_MARKERS)]
    return next((value for value in candidates if value), "")


def number(value: str) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def coordinates(row: dict[str, str]) -> tuple[float | None, float | None]:
    """열 이름 차이를 견뎌 실제 범위(위도 37, 경도 126)로 좌표 순서를 판별한다."""
    values: list[float] = []
    for key, value in row.items():
        key_norm = normalized(key)
        if key_norm in {"x", "y", "좌표x", "좌표y", "x좌표", "y좌표"} or any(marker in key_norm for marker in LAT_MARKERS + LNG_MARKERS):
            parsed = number(value)
            if parsed is not None:
                values.append(parsed)
    candidates: list[tuple[float, float]] = []
    for first in values:
        for second in values:
            if 36.8 <= first <= 37.7 and 126.2 <= second <= 127.3:
                candidates.append((first, second))
            if 36.8 <= second <= 37.7 and 126.2 <= first <= 127.3:
                candidates.append((second, first))
    if not candidates:
        return None, None
    # 도·분·초 열의 37/126보다 EPSG4326 소수 좌표를 우선한다.
    return min(candidates, key=lambda pair: abs(pair[0] - 37.4) + abs(pair[1] - 126.8))


def rings(feature: dict) -> list[list[list[float]]]:
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    return [polygon[0] for polygon in geometry["coordinates"]]


def contains(point_lng: float, point_lat: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        intersects = (y1 > point_lat) != (y2 > point_lat) and point_lng < (x2 - x1) * (point_lat - y1) / (y2 - y1) + x1
        if intersects:
            inside = not inside
        previous = current
    return inside


def boundary_center(boundary_rings: list[list[list[float]]]) -> list[float]:
    points = [point for ring in boundary_rings for point in ring]
    return [round(sum(point[1] for point in points) / len(points), 6), round(sum(point[0] for point in points) / len(points), 6)]


def source_for(path: Path) -> tuple[str, str, str, bool] | None:
    return next((spec for marker, spec in SOURCES.items() if path.name.startswith(marker)), None)


def subtype_for(category: str, row: dict[str, str]) -> str:
    if category in {"hospital", "restaurant", "cafe"}:
        return text(row, "세부분류") or category
    if category == "pet_facility":
        return text(row, "시설구분", "업종명") or category
    return text(row, "종별", "학교구분", "시설구분", "유형") or category


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"최종 원본 폴더가 없습니다: {RAW}")
    geojson = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    boundary_rows = []
    for feature in geojson["features"]:
        props = feature["properties"]
        boundary_rows.append({"id": props["id"], "name": props["name"], "rings": rings(feature)})

    areas = [{"id": item["id"], "name": item["name"], "center": boundary_center(item["rings"]), "counts": {}, "facility_total": 0} for item in boundary_rows]
    area_lookup = {item["id"]: item for item in areas}
    facilities: list[dict] = []
    quality: Counter[str] = Counter()
    category_definitions = {
        category: {"id": category, "label": label, "group": group, "density_only": density_only}
        for category, label, group, density_only in SOURCES.values()
    }
    active_categories: set[str] = set()

    for path in sorted(RAW.glob("*.csv")):
        spec = source_for(path)
        if not spec:
            quality[f"unmapped:{path.name}"] += 1
            continue
        category, label, group, density_only = spec
        with path.open(encoding="utf-8-sig", newline="") as source:
            for index, row in enumerate(csv.DictReader(source), start=1):
                lat, lng = coordinates(row)
                if lat is None or lng is None:
                    quality[f"{path.name}:missing_coordinate"] += 1
                    continue
                area_id = next((item["id"] for item in boundary_rows if any(contains(lng, lat, ring) for ring in item["rings"])), None)
                if not area_id:
                    quality[f"{path.name}:outside_boundary"] += 1
                    continue
                facility = {
                    "id": f"{path.stem}:{index}", "area_id": area_id, "category": category,
                    "group": group, "name": name_for(row, label), "address": address_for(row),
                    "lat": lat, "lng": lng, "detail": subtype_for(category, row),
                    "good_price": text(row, "착한가격업소여부") == "1", "source": path.name,
                    "density_only": density_only, "map_visible": True,
                }
                facilities.append(facility)
                area_lookup[area_id]["counts"][category] = area_lookup[area_id]["counts"].get(category, 0) + 1
                area_lookup[area_id]["facility_total"] += 1
                active_categories.add(category)
                quality[f"{path.name}:added"] += 1

    category_order = [spec[0] for spec in SOURCES.values()]
    result = {
        "meta": {
            "project_name": "시흥시 생활 인프라 지도", "period": "데이터최종취합 정제본",
            "updated_at": date.today().isoformat(),
            "notice": "데이터최종취합 브랜치의 `데이터 정제후` CSV 28개만 반영했습니다. 좌표가 있고 시흥시 행정동 경계 안에 들어오는 시설만 지도·추천에 사용합니다.",
        },
        "groups": [{"id": key, "label": label, "icon": icon, "color": color} for key, label, icon, color in GROUPS],
        "categories": [
            {**category_definitions[key], "map_unavailable": key not in active_categories}
            for key in category_order if key in category_definitions
        ],
        "areas": areas,
        "facilities": facilities,
        "sources": [{"name": "데이터 정제후", "organization": "데이터최종취합 브랜치", "description": "최종 확정 28개 CSV"}],
        "quality": dict(sorted(quality.items())),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: facilities={len(facilities):,}, areas={len(areas)}, categories={len(category_definitions)}")
    print(json.dumps(dict(sorted(quality.items())), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
