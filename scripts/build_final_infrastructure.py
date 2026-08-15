"""Build the web data from only the final CSV bundle in data/final."""
from __future__ import annotations

import csv
import json
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "final"
OUTPUT = ROOT / "data" / "processed" / "siheung_infrastructure.json"
BOUNDARY_SOURCE = ROOT / "static" / "data" / "siheung_dong_boundaries.geojson"

GROUPS = {
    "shopping": "쇼핑·유통", "food": "음식점", "cafe": "카페",
    "nature": "휴식·운동", "daily": "생활편의", "culture": "문화",
    "safety": "치안·안전", "health": "의료·건강", "pet": "반려동물",
    "education": "교육",
}

CATEGORIES = [
    ("park", "공원", "nature"), ("playground", "놀이터", "nature"),
    ("exercise", "헬스장", "nature"), ("mart", "대형마트", "shopping"),
    ("small_mart", "소형마트", "shopping"), ("grocery_mart", "식자재마트", "shopping"),
    ("convenience", "편의점", "shopping"), ("hospital_internal", "내과", "health"),
    ("hospital_dental", "치과", "health"), ("hospital_orthopedic", "정형외과", "health"),
    ("hospital_obgyn", "산부인과", "health"), ("hospital_dermatology", "피부과", "health"),
    ("hospital_24h", "24시 병원", "health"), ("hospital_other", "기타 병원", "health"),
    ("pharmacy", "약국", "health"), ("health_center", "보건소", "health"),
    ("pet_hospital", "동물병원", "pet"), ("pet", "반려동물시설", "pet"),
    ("food_korean", "한식", "food"), ("food_asian", "아시안", "food"),
    ("food_western", "양식", "food"), ("food_other", "기타 음식점", "food"),
    ("food_bar", "주점", "food"), ("food_chicken", "치킨", "food"),
    ("cafe_general", "일반카페", "cafe"), ("cafe_theme", "테마카페", "cafe"),
    ("laundry", "코인세탁방", "daily"), ("bathhouse", "목욕탕", "daily"),
    ("performance", "관람시설", "culture"), ("library", "도서관", "culture"),
    ("cctv", "방범 CCTV", "safety"), ("police", "경찰서·파출소·지구대", "safety"),
    ("fire_station", "소방서", "safety"), ("emergency_bell", "안전비상벨", "safety"),
    ("shelter", "민방위대피시설", "safety"), ("child_zone", "어린이보호구역", "safety"),
    ("elementary_school", "초등학교", "education"),
    ("middle_school", "중학교", "education"), ("high_school", "고등학교", "education"),
]
CATEGORY_META = {category: (label, group) for category, label, group in CATEGORIES}

HOSPITAL_TYPES = {"내과": "hospital_internal", "치과": "hospital_dental", "정형외과": "hospital_orthopedic", "산부인과": "hospital_obgyn", "피부과": "hospital_dermatology", "24시 병원": "hospital_24h", "기타": "hospital_other"}
FOOD_TYPES = {"한식": "food_korean", "아시안": "food_asian", "양식": "food_western", "기타": "food_other", "주점": "food_bar", "치킨": "food_chicken"}
CAFE_TYPES = {"일반카페": "cafe_general", "테마카페": "cafe_theme"}


def normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def first(row: dict[str, str], *keys: str) -> str:
    return next((str(row.get(key, "")).strip() for key in keys if str(row.get(key, "")).strip()), "")


def number(row: dict[str, str], *keys: str) -> float | None:
    try:
        return float(first(row, *keys))
    except ValueError:
        return None


def category_for(filename: str, row: dict[str, str]) -> str | None:
    name = normalized(filename)
    if name.startswith("1-1."): return "park"
    if name.startswith("1-2."): return "playground"
    if name.startswith("1-3."): return "exercise"
    if name.startswith("2-1."): return "mart"
    if name.startswith("2-2."): return "small_mart"
    if name.startswith("2-3."): return "grocery_mart"
    if name.startswith("2-4."): return "convenience"
    if name.startswith("3-1."): return HOSPITAL_TYPES.get(first(row, "세부분류"))
    if name.startswith("3-2."): return "pharmacy"
    if name.startswith("3-3."): return "health_center"
    if "동물병원" in name: return "pet_hospital"
    if "반려동물시설" in name: return "pet"
    if name.startswith("5'."): return FOOD_TYPES.get(first(row, "세부분류"))
    if name.startswith("6."): return CAFE_TYPES.get(first(row, "세부분류"))
    if "코인세탁방" in name: return "laundry"
    if "목욕탕" in name: return "bathhouse"
    if "관람시설" in name: return "performance"
    if "도서관" in name: return "library"
    if "CCTV" in name: return "cctv"
    if "경찰관서" in name: return "police"
    if "소방관서" in name: return "fire_station"
    if "안전비상벨" in name: return "emergency_bell"
    if "민방위대피시설" in name: return "shelter"
    if "어린이보호구역" in name: return "child_zone"
    if "초등학교" in name: return "elementary_school"
    if "중학교" in name: return "middle_school"
    if "고등학교" in name: return "high_school"
    return None


def geometry_rings(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    return [polygon[0] for polygon in geometry["coordinates"]]


def point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > lat) != (y2 > lat):
            crossing = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lng < crossing:
                inside = not inside
        previous = current
    return inside


def area_for(address: str, lat: float, lng: float, areas: dict[str, dict], hint: str = "") -> str | None:
    text = f"{address} {hint}"
    named = next((area_id for area_id, area in areas.items() if area["name"] in text), None)
    if named:
        return named
    for area_id, area in areas.items():
        if any(point_in_ring(lng, lat, ring) for ring in area["rings"]):
            return area_id
    return None


def main() -> None:
    boundary_data = json.loads(BOUNDARY_SOURCE.read_text(encoding="utf-8"))
    areas = {
        feature["properties"]["id"]: {
            "name": feature["properties"]["name"],
            "center": [feature["properties"]["center_lat"], feature["properties"]["center_lng"]],
            "rings": geometry_rings(feature["geometry"]),
        }
        for feature in boundary_data["features"]
    }
    facilities: list[dict] = []
    seen: set[tuple] = set()
    counts = {area: Counter() for area in areas}
    quality = Counter()
    for path in sorted(SOURCE.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source_file:
            for row_number, row in enumerate(csv.DictReader(source_file), start=2):
                category = category_for(path.name, row)
                if not category:
                    quality["unsupported_category"] += 1
                    continue
                lat = number(row, "위도", "y", "좌표Y", "WGS84위도", "refine_wgs84_lat", "위도(EPSG4326)")
                lng = number(row, "경도", "x", "좌표X", "WGS84경도", "refine_wgs84_logt", "경도(EPSG4326)")
                if lat is None or lng is None or not (36.9 <= lat <= 37.7 and 126.3 <= lng <= 127.3):
                    quality["invalid_coordinate"] += 1
                    continue
                address = first(row, "road_address_name", "address_name", "도로명주소", "주소", "학교주소", "소재지도로명주소", "소재지지번주소", "도로명전체주소", "소재지전체주소", "refine_road_nm_addr", "refine_lotno_addr", "설치위치")
                area_id = area_for(address, lat, lng, areas, first(row, "법정동명", "읍면동명", "법정동_읍면동", "기관명"))
                if not area_id:
                    quality["outside_comparison_area"] += 1
                label, group = CATEGORY_META[category]
                facility_name = first(row, "place_name", "기관명", "시설명", "병원명", "bizplc_nm", "대상시설명", "학교명", "소방서 및 안전센터명", "설치위치", "설치목적구분", "관리번호") or label
                key = (category, facility_name, round(lat, 6), round(lng, 6))
                if key in seen:
                    quality["duplicate"] += 1
                    continue
                seen.add(key)
                item = {"id": f"{path.stem}:{row_number}", "area_id": area_id, "category": category, "group": group, "name": facility_name, "address": address, "lat": lat, "lng": lng, "url": first(row, "place_url", "장소URL", "hmpg_addr"), "source": path.name, "density_only": False, "map_visible": True}
                if category in {*FOOD_TYPES.values(), *CAFE_TYPES.values()}:
                    item["good_price"] = first(row, "착한가격업소여부") == "1"
                if category == "cctv":
                    item["detail"] = " · ".join(filter(None, [first(row, "설치목적구분"), first(row, "카메라대수") and f"카메라 {first(row, '카메라대수')}대"]))
                facilities.append(item)
                if area_id:
                    counts[area_id][category] += 1
                quality["added"] += 1
    result = {
        "meta": {"project_name": "시흥시 생활 인프라 지도", "period": "데이터최종취합/데이터 정제후", "updated_at": date.today().isoformat(), "area_unit": "법정동", "area_count": len(areas), "notice": "최종 취합 CSV의 좌표를 시흥시 전체 법정동 경계에 공간 배정했습니다. CCTV와 경찰관서는 원본 좌표를 개별 점으로 반영합니다."},
        "groups": [{"id": key, "label": label} for key, label in GROUPS.items()],
        "categories": [{"id": key, "label": label, "group": group, "density_only": False} for key, label, group in CATEGORIES],
        "areas": [{"id": key, "name": area["name"], "center": area["center"], "counts": dict(counts[key]), "facility_total": sum(counts[key].values())} for key, area in areas.items()],
        "facilities": facilities,
        "sources": [{"name": "데이터 정제후 최종 CSV", "organization": "데이터최종취합 브랜치", "description": "최종 분류·좌표 정제본"}, {"name": "시흥시 법정동 경계", "organization": "OpenStreetMap contributors", "description": "법정동 28개 폴리곤 경계"}],
        "quality": dict(quality),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(facilities):,} facilities")
    print(dict(quality))


if __name__ == "__main__":
    main()
