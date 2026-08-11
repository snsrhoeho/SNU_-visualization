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
    "affordable": "알뜰생활",
}
JOO_CATEGORY_META = {
    "food": ("음식점", "food"),
    "cafe": ("카페", "food"),
    "convenience": ("편의점", "daily"),
    "hospital": ("병원", "health"),
    "park": ("공원", "nature"),
    "pharmacy": ("약국", "health"),
    "laundry": ("세탁방", "daily"),
    "good_price": ("착한가격업소", "affordable"),
    "mart": ("대형마트", "daily"),
    "subway": ("지하철역", "public"),
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
    # 파일명과 달리 위생업 인허가의 '휴게음식점' 자료다. 편의점으로 합치지 않는다.
    "convenience_store.csv": ("snack_food", "휴게음식점", "food", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "culture_facility.csv": ("culture", "문화시설", "culture", ["faclt_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "culture_festival.csv": ("festival", "문화축제", "culture", ["fastvl_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "delivery_express_store.csv": ("parcel", "택배취급점", "daily", ["str_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "fitness.csv": ("exercise", "헬스장", "nature", ["사업장명"], ["소재지도로명주소", "소재지지번주소"], ["WGS84위도"], ["WGS84경도"], False),
    "gg_attraction.csv": ("attraction", "관광명소", "culture", ["nm_sm_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "golf_range.csv": ("golf", "골프연습장", "nature", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "health_center.csv": ("health_center", "보건소", "health", ["bizplc_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "health_checkup_agency.csv": ("health_check", "건강검진기관", "health", ["medchek_inst_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "karaoke.csv": ("karaoke", "노래연습장", "culture", ["사업장명"], ["도로명주소", "지번주소"], ["WGS84위도"], ["WGS84경도"], False),
    "laundry.csv": ("laundry", "세탁방", "daily", ["사업장명"], ["소재지도로명주소", "소재지지번주소"], ["위도"], ["경도"], False),
    "library.csv": ("library", "도서관", "culture", ["librry_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
    "local_food_store.csv": ("local_food", "지역음식점", "food", ["cmpnm_nm"], ["refine_road_nm_addr", "refine_lotno_addr"], ["refine_wgs84_lat"], ["refine_wgs84_logt"], False),
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


def area_id(address: str, lng: float | None, area_hint: str = "") -> str | None:
    """주연 데이터의 지역명은 법정동 주소보다 우선한다.

    배곧은 주소가 정왕동으로 표기되는 경우가 있어, 좌표가 있는 수집본의
    area 값을 먼저 사용한다. 정왕동만 1·2동 비교 생활권으로 경도 기준 분리한다.
    """
    if area_hint in {"배곧동", "대야동", "신천동", "은행동"}:
        return {"배곧동": "baegot", "대야동": "daeya", "신천동": "sincheon", "은행동": "eunhaeng"}[area_hint]
    if area_hint == "정왕동":
        if lng is None:
            return None
        return "jeongwang1" if lng >= 126.735 else "jeongwang2"
    if "정왕동" in address:
        if lng is None:
            return None
        return "jeongwang1" if lng >= 126.735 else "jeongwang2"
    for key, area in AREAS.items():
        if area["match"] != "정왕동" and area["match"] in address:
            return key
    return None


def add(facilities: list[dict], seen: set[tuple], *, category: str, group: str, label: str, name: str, address: str, lat: float | None, lng: float | None, source: str, density_only: bool = False, area_hint: str = "", url: str = "") -> str:
    if lat is None or lng is None or not (36.9 <= lat <= 37.6 and 126.3 <= lng <= 127.2):
        return "invalid_coordinate"
    area = area_id(address, lng, area_hint)
    if not area:
        return "outside_comparison_area"
    key = (category, name, round(lat, 6), round(lng, 6))
    if key in seen:
        return "duplicate"
    seen.add(key)
    facilities.append({"id": f"{source}:{len(facilities) + 1}", "area_id": area, "category": category, "group": group, "name": name or label, "address": address, "lat": lat, "lng": lng, "url": url, "source": source, "density_only": density_only, "map_visible": True})
    return "added"


def add_area_summary(facilities: list[dict], seen: set[tuple], *, category: str, group: str, label: str, name: str, address: str, source: str, area_hint: str = "", url: str = "", detail: str = "") -> str:
    """좌표가 없는 공식 현황은 동 단위 수치·목록으로만 제공한다.

    임의의 중심좌표를 넣어 실제 위치처럼 보이게 하지 않는다.
    """
    area = area_id(address, None, area_hint)
    if not area:
        return "outside_comparison_area"
    key = (category, name, address)
    if key in seen:
        return "duplicate"
    seen.add(key)
    facilities.append({"id": f"{source}:{len(facilities) + 1}", "area_id": area, "category": category, "group": group, "name": name or label, "address": address, "lat": None, "lng": None, "url": url, "source": source, "detail": detail, "density_only": False, "map_visible": False})
    return "added"


def main() -> None:
    facilities = []
    seen: set[tuple] = set()
    quality = Counter()
    # category_meta에는 실제로 지도에 추가된 시설이 하나 이상인 항목만 넣는다.
    category_meta: dict[str, dict] = {}

    if JOO.exists():
        joo = json.loads(JOO.read_text(encoding="utf-8"))
        for item in joo.get("facilities", []):
            category = item.get("category", "")
            if category not in JOO_CATEGORY_META:
                quality["unsupported:juyeon"] += 1
                continue
            label, group = JOO_CATEGORY_META[category]
            outcome = add(
                facilities, seen, category=category, group=group, label=label,
                name=item.get("name", ""), address=item.get("address", ""),
                lat=item.get("lat"), lng=item.get("lng"), source="juyeon_life_fit",
                area_hint=item.get("area", ""), url=item.get("url", ""),
            )
            quality[f"juyeon:{outcome}"] += 1
            if outcome == "added":
                category_meta.setdefault(category, {"id": category, "label": label, "group": group})

        # 착한가격업소는 공식 현황에 주소·업종은 있으나 좌표가 없다.
        # 동 단위 비교와 상세 목록에는 반영하되, 지도 점으로는 표시하지 않는다.
        label, group = JOO_CATEGORY_META["good_price"]
        for item in joo.get("good_price_businesses", []):
            outcome = add_area_summary(
                facilities, seen, category="good_price", group=group, label=label,
                name=item.get("name", ""), address=item.get("address", ""),
                source="juyeon_good_price", area_hint=item.get("area", ""),
                url=item.get("url", ""), detail=item.get("business_type", ""),
            )
            quality[f"good_price:{outcome}"] += 1
            if outcome == "added":
                category_meta.setdefault("good_price", {"id": "good_price", "label": label, "group": group, "aggregate_only": True})

    for filename, spec in SOURCES.items():
        category, label, group, names, addresses, lats, lngs, density_only = spec
        path = RAW / filename
        if not path.exists():
            quality[f"missing:{filename}"] += 1
            continue
        with path.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                outcome = add(facilities, seen, category=category, group=group, label=label, name=first(row, names), address=first(row, addresses), lat=number(row, lats), lng=number(row, lngs), source=filename, density_only=density_only)
                quality[f"{filename}:{outcome}"] += 1
                if outcome == "added":
                    category_meta.setdefault(category, {"id": category, "label": label, "group": group, "density_only": density_only})

    counts_by_area = {key: Counter() for key in AREAS}
    for item in facilities:
        counts_by_area[item["area_id"]][item["category"]] += 1
    category_order = list(dict.fromkeys([*JOO_CATEGORY_META, *(spec[0] for spec in SOURCES.values())]))
    result = {
        "meta": {"project_name": "시흥시 생활 인프라 지도", "period": "협업 수집본 통합", "updated_at": date.today().isoformat(), "notice": "원격 협업 브랜치 원본을 통합했습니다. 좌표가 있는 시설은 지도 점·추천에, 좌표가 없는 착한가격업소 공식 현황은 동 단위 비교·목록에만 반영합니다. 식품제조업 등 방문형 생활시설이 아닌 자료는 추천 목록에서 제외했습니다."},
        "groups": [{"id": key, "label": label} for key, label in GROUPS.items()],
        "categories": [category_meta[key] for key in category_order if key in category_meta],
        "areas": [{"id": key, "name": value["name"], "center": value["center"], "counts": dict(counts_by_area[key]), "facility_total": sum(counts_by_area[key].values())} for key, value in AREAS.items()],
        "facilities": facilities,
        "sources": [{"name": "주연 생활 인프라 수집본", "organization": "협업 브랜치 juyeon", "description": "카페·음식점·의료·교통 등 좌표 기반 시설"}, {"name": "협업 수집 CSV", "organization": "협업 브랜치 시각화_ch_branch", "description": "안전·건강·문화·반려동물 등 시설 원본"}],
        "quality": dict(quality),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: facilities={len(facilities):,}, categories={len(category_meta)}")
    print(dict(quality))


if __name__ == "__main__":
    main()
