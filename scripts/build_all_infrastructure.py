"""협업 브랜치의 시흥시 시설 CSV를 웹용 생활 인프라 JSON으로 통합한다.

원본 CSV는 그대로 보관하고, 지도·추천에는 좌표가 있고 6개 비교 생활권에
배정 가능한 행만 넣는다. 대량 안전시설은 `density_only`로 표시해 개별 마커
폭주를 막는다.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "processed" / "siheung_infrastructure.json"
RAW = ROOT / "data" / "processed" / "siheung_infra"
JOO = ROOT / "data" / "processed" / "life_fit.json"
OUTPUT = ROOT / "data" / "processed" / "siheung_infrastructure.json"

AREAS = {
    "baegot": {"name": "배곧동", "match": "배곧동", "center": [37.3690909, 126.7208477]},
    "jeongwang1": {"name": "정왕1동", "match": "정왕동", "center": [37.3328622, 126.7361104]},
    "jeongwang2": {"name": "정왕2동", "match": "정왕동", "center": [37.3318474, 126.6598047]},
    "daeya": {"name": "대야동", "match": "대야동", "center": [37.4551254, 126.8013314]},
    "sincheon": {"name": "신천동", "match": "신천동", "center": [37.4396138, 126.7788556]},
    "eunhaeng": {"name": "은행동", "match": "은행동", "center": [37.4334715, 126.8093504]},
}

GROUPS = {
    "daily": "일상", "health": "건강", "safety": "안전", "nature": "휴식·운동",
    "culture": "문화", "pet": "반려동물", "public": "공공·공유", "food": "먹거리",
}
BASE_CATEGORY_GROUPS = {
    "food": "food", "cafe": "food", "laundry": "daily", "convenience": "daily",
    "mart": "daily", "subway": "public", "park": "nature", "hospital": "health", "pharmacy": "health",
}

# 파일명: (카테고리 id, 표시명, 분야, 이름 후보 열, 주소 후보 열, 위도 후보 열, 경도 후보 열, 밀집도 전용)
SOURCES = {
    "addiction_center.csv": ("addiction", "중독관리센터", "public", ["center_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "animal_hospital.csv": ("pet_hospital", "동물병원", "pet", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "bathhouse.csv": ("bathhouse", "목욕탕", "daily", ["사업장명"], ["소재지도로명주소", "소재지지번주소"], ["WGS84위도"], ["WGS84경도"], False),
    "camping.csv": ("camping", "캠핑장", "nature", ["faclt_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "cctv.csv": ("cctv", "CCTV", "safety", ["instl_purps_div", "mnginst_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], True),
    "century_store.csv": ("century_store", "백년가게", "food", ["entrps_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "city_park.csv": ("park", "공원", "nature", ["park_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "convenience_store.csv": ("convenience", "편의점", "daily", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "culture_facility.csv": ("culture", "문화시설", "culture", ["faclt_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "culture_festival.csv": ("festival", "문화축제", "culture", ["fastvl_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "delivery_express_store.csv": ("parcel", "택배취급점", "daily", ["str_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "fitness.csv": ("exercise", "헬스장", "nature", ["사업장명"], ["소재지도로명주소", "소재지지번주소"], ["WGS84위도"], ["WGS84경도"], False),
    "gg_attraction.csv": ("attraction", "관광명소", "culture", ["nm_sm_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "golf_range.csv": ("golf", "골프연습장", "nature", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "health_center.csv": ("health_center", "보건소", "health", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "health_checkup_agency.csv": ("health_check", "건강검진기관", "health", ["medchek_inst_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "instant_food_processing.csv": ("food_processing", "식품제조업", "food", ["bizcond_div_nm_info", "sanittn_bizcond_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "karaoke.csv": ("karaoke", "노래연습장", "culture", ["사업장명"], ["도로명주소", "지번주소"], ["WGS84위도"], ["WGS84경도"], False),
    "laundry.csv": ("laundry", "세탁방", "daily", ["사업장명"], ["소재지도로명주소", "소재지지번주소"], ["위도"], ["경도"], False),
    "library.csv": ("library", "도서관", "culture", ["librry_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "local_food_store.csv": ("local_food", "지역음식점", "food", ["cmpnm_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "lunchbox_manufacturer.csv": ("food_processing", "식품제조업", "food", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "mental_health_center.csv": ("mental_health", "정신건강센터", "health", ["center_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "nhis_branch.csv": ("nhis", "건강보험공단", "public", ["inst_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "performance_hall.csv": ("performance", "공연장", "culture", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "pet_convenience_facility.csv": ("pet", "반려동물시설", "pet", ["cmpnm_nm"], ["roadnm_addr", "lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "pet_store.csv": ("pet", "반려동물시설", "pet", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "pharmacy.csv": ("pharmacy", "약국", "health", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "playground.csv": ("playground", "어린이놀이터", "nature", ["play_si_desc", "instl_plc"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "security_light.csv": ("security_light", "보안등", "safety", ["secrtlgt_loc_nm_info", "mnginst_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], True),
    "shared_facility_rental.csv": ("shared", "공유시설", "public", ["faclt_nm"], ["addr", "detail_addr"], ["lat"], ["logt"], False),
    "sports_facility.csv": ("exercise", "체육시설", "nature", ["사업장명"], ["소재지도로명주소", "소재지지번주소"], ["WGS84위도"], ["WGS84경도"], False),
    "tourist_spot.csv": ("attraction", "관광명소", "culture", ["faclt_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "traditional_market.csv": ("market", "전통시장", "food", ["market_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
}


def first(row: dict[str, str], keys: list[str]) -> str:
    return next((str(row.get(key, "")).strip() for key in keys if str(row.get(key, "")).strip()), "")


def number(row: dict[str, str], keys: list[str]) -> float | None:
    try:
        return float(first(row, keys))
    except ValueError:
        return None


def area_id(address: str, lng: float) -> str | None:
    if "정왕동" in address:
        return "jeongwang1" if lng >= 126.735 else "jeongwang2"
    for key, area in AREAS.items():
        if area["match"] != "정왕동" and area["match"] in address:
            return key
    return None


def add(facilities: list[dict], seen: set[tuple], *, category: str, group: str, label: str, name: str, address: str, lat: float | None, lng: float | None, source: str, density_only: bool = False) -> str:
    if lat is None or lng is None or not (36.9 <= lat <= 37.6 and 126.3 <= lng <= 127.2):
        return "invalid_coordinate"
    area = area_id(address, lng)
    if not area:
        return "outside_comparison_area"
    key = (category, name, round(lat, 6), round(lng, 6))
    if key in seen:
        return "duplicate"
    seen.add(key)
    facilities.append({"id": f"{source}:{len(facilities) + 1}", "area_id": area, "category": category, "group": group, "name": name or label, "address": address, "lat": lat, "lng": lng, "url": "", "source": source, "density_only": density_only})
    return "added"


def main() -> None:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    facilities = []
    seen: set[tuple] = set()
    quality = Counter()
    category_meta = {item["id"]: {**item, "group": BASE_CATEGORY_GROUPS.get(item["id"], "daily")} for item in base["categories"]}
    for item in base["facilities"]:
        category = item["category"]
        category_meta.setdefault(category, {"id": category, "label": category, "group": "daily"})
        quality[add(facilities, seen, category=category, group=category_meta[category].get("group", "daily"), label=category_meta[category]["label"], name=item["name"], address=item["address"], lat=item["lat"], lng=item["lng"], source="기존 생활인프라")] += 1

    for filename, spec in SOURCES.items():
        category, label, group, names, addresses, lats, lngs, density_only = spec
        category_meta[category] = {"id": category, "label": label, "group": group, "density_only": density_only}
        path = RAW / filename
        if not path.exists():
            quality[f"missing:{filename}"] += 1
            continue
        with path.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                quality[add(facilities, seen, category=category, group=group, label=label, name=first(row, names), address=first(row, addresses), lat=number(row, lats), lng=number(row, lngs), source=filename, density_only=density_only)] += 1

    if JOO.exists():
        joo = json.loads(JOO.read_text(encoding="utf-8"))
        category_meta["good_price"] = {"id": "good_price", "label": "착한가격업소", "group": "food"}
        for item in joo.get("facilities", []):
            if item.get("category") != "good_price":
                continue
            quality[add(facilities, seen, category="good_price", group="food", label="착한가격업소", name=item.get("name", ""), address=item.get("address", ""), lat=item.get("lat"), lng=item.get("lng"), source="juyeon_life_fit")] += 1

    counts_by_area = {key: Counter() for key in AREAS}
    for item in facilities:
        counts_by_area[item["area_id"]][item["category"]] += 1
    result = {
        "meta": {"project_name": "시흥시 생활 인프라 지도", "period": "협업 수집본 통합", "updated_at": date.today().isoformat(), "notice": "원본 협업 데이터 중 좌표가 있고 6개 비교 생활권에 배정 가능한 시설만 지도·추천에 반영했습니다. CCTV·보안등은 밀집도용 데이터입니다."},
        "groups": [{"id": key, "label": label} for key, label in GROUPS.items()],
        "categories": list(category_meta.values()),
        "areas": [{"id": key, "name": value["name"], "center": value["center"], "counts": dict(counts_by_area[key]), "facility_total": sum(counts_by_area[key].values())} for key, value in AREAS.items()],
        "facilities": facilities,
        "sources": base.get("sources", []) + [{"name": "협업 수집 CSV", "organization": "시흥시 공공데이터 수집본", "description": "안전·건강·문화·반려동물 등 시설 원본"}],
        "quality": dict(quality),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: facilities={len(facilities):,}, categories={len(category_meta)}")
    print(dict(quality))


if __name__ == "__main__":
    main()
