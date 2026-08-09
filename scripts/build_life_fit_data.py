"""Build the static dataset used by the Siheung Life Fit prototype.

The source CSV is left untouched.  The output contains only the fields the
browser needs, plus a compact administrative-dong summary.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "데이터" / "siheung_data" / "siheung_life_infra.csv"
GOOD_PRICE_SOURCE = ROOT / "데이터" / "행정안전부_착한가격업소 현황_20260630.csv"
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

RUNNING_ROUTES = [
    {
        "id": "baegot-life-loop", "area": "baegot", "name": "배곧생명공원 물빛 루프",
        "distance_km": 3.2, "duration_min": 28, "difficulty": "쉬움", "surface": "공원 산책로",
        "summary": "배곧생명공원의 수변과 잔디광장을 한 바퀴 도는 입문용 순환 코스",
        "highlights": ["수변 풍경", "평탄한 구간", "화장실·주차장"],
        "coordinates": [[126.7196,37.3712],[126.7203,37.3701],[126.7245,37.3725],[126.7228,37.3740],[126.7197,37.3735],[126.7196,37.3712]],
        "svg_points": [[14,69],[16,62],[22,60],[27,66],[24,74],[17,76],[14,69]],
        "basis": "배곧생명공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "okgu-park-loop", "area": "jeongwang1", "name": "옥구공원 초록 언덕 루프",
        "distance_km": 2.8, "duration_min": 25, "difficulty": "보통", "surface": "공원길·완만한 언덕",
        "summary": "한국정원과 조가비무대를 지나 옥구공원의 녹지를 연결하는 코스",
        "highlights": ["한국정원", "완만한 오르막", "운동시설"],
        "coordinates": [[126.7091,37.3524],[126.7115,37.3540],[126.7134,37.3555],[126.7132,37.3561],[126.7100,37.3545],[126.7091,37.3524]],
        "svg_points": [[41,70],[43,62],[49,59],[55,65],[54,74],[47,78],[41,70]],
        "basis": "옥구공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "oido-history-coast", "area": "jeongwang2", "name": "오이도 역사·해안 코스",
        "distance_km": 4.6, "duration_min": 42, "difficulty": "보통", "surface": "해안 보행로·공원길",
        "summary": "오이도 선사유적공원과 해안 방향의 주요 지점을 연결하는 풍경 코스",
        "highlights": ["선사유적공원", "서해 풍경", "노을 추천"],
        "coordinates": [[126.6962,37.3430],[126.6934,37.3472],[126.6900,37.3481],[126.6900,37.3416],[126.6908,37.3348],[126.6962,37.3430]],
        "svg_points": [[70,67],[72,59],[79,56],[87,62],[89,73],[82,78],[74,75],[70,67]],
        "basis": "시흥시 오이도 공원·해안 지점 기반 MVP 추천 동선",
    },
    {
        "id": "sincheon-park-link", "area": "sincheon", "name": "신천 도심공원 연결 코스",
        "distance_km": 3.6, "duration_min": 33, "difficulty": "쉬움", "surface": "도심 보행로·공원길",
        "summary": "신천공원에서 둥지공원·바람길공원 방향으로 이어지는 생활권 코스",
        "highlights": ["도심 접근성", "여러 공원", "가벼운 야간런"],
        "coordinates": [[126.7849,37.4381],[126.7876,37.4385],[126.7889,37.4366],[126.7916,37.4355],[126.7904,37.4351],[126.7854,37.4356],[126.7849,37.4381]],
        "svg_points": [[52,22],[57,13],[65,11],[70,17],[68,25],[61,29],[55,27],[52,22]],
        "basis": "신천동 공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "eungye-lake-loop", "area": "eunhaeng", "name": "은계호수공원 산뜻 루프",
        "distance_km": 2.4, "duration_min": 22, "difficulty": "쉬움", "surface": "호수공원 산책로",
        "summary": "은계호수공원 수변을 중심으로 짧고 가볍게 반복할 수 있는 코스",
        "highlights": ["호수 풍경", "카페 접근성", "평탄한 루프"],
        "coordinates": [[126.8034,37.4443],[126.8059,37.4439],[126.8069,37.4447],[126.8040,37.4462],[126.8026,37.4452],[126.8034,37.4443]],
        "svg_points": [[78,22],[82,13],[89,12],[94,19],[92,28],[84,31],[78,22]],
        "basis": "은계호수공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "daeya-eungye-forest", "area": "daeya", "name": "대야–은계숲 그린 코스",
        "distance_km": 4.1, "duration_min": 38, "difficulty": "보통", "surface": "공원길·생활도로",
        "summary": "대야공원에서 은계공원과 은계숲생태공원 방향을 연결하는 녹지 코스",
        "highlights": ["연속된 공원", "중거리 훈련", "생활권 접근"],
        "coordinates": [[126.7883,37.4468],[126.7942,37.4468],[126.7959,37.4476],[126.8005,37.4483],[126.7963,37.4460],[126.7906,37.4484],[126.7883,37.4468]],
        "svg_points": [[16,24],[20,13],[29,10],[37,16],[39,27],[31,32],[22,31],[16,24]],
        "basis": "대야·은계권 공원 시설 좌표 기반 MVP 추천 동선",
    },
]


def area_id(address: str, lng: float) -> str | None:
    for key, area in AREAS.items():
        if area["match"] in address and area["match"] != "정왕동":
            return key
    if "정왕동" in address:
        return "jeongwang1" if lng >= 126.735 else "jeongwang2"
    return None


def good_price_area_id(address: str) -> str | None:
    direct = {"배곧동": "baegot", "대야동": "daeya", "신천동": "sincheon", "은행동": "eunhaeng"}
    for dong, key in direct.items():
        if dong in address:
            return key
    if "정왕동" in address:
        return "jeongwang2" if "오이도" in address else "jeongwang1"
    return None


def read_good_price_businesses() -> list[dict]:
    businesses = []
    with GOOD_PRICE_SOURCE.open(encoding="cp949", newline="") as source:
        for index, row in enumerate(csv.DictReader(source), start=1):
            if row.get("시군") != "시흥시":
                continue
            menus = []
            for number in range(1, 5):
                name = row.get(f"메뉴{number}", "").strip()
                price = row.get(f"가격{number}", "").strip()
                if name:
                    menus.append({"name": name, "price": int(price) if price.isdigit() else price})
            address = row.get("주소", "").strip()
            name = row.get("업소명", "").strip()
            businesses.append({
                "id": f"good-price-{index}", "area": good_price_area_id(address),
                "category": "good_price", "business_type": row.get("업종", "").strip(),
                "name": name, "address": address, "phone": row.get("연락처", "").strip(),
                "menus": menus, "url": f"https://map.naver.com/p/search/{quote(name + ' ' + address)}",
            })
    return businesses


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

    good_price_businesses = read_good_price_businesses()
    for business in good_price_businesses:
        if not business["area"]:
            continue
        facilities.append({
            **business, "detail": business["business_type"],
            "menu_summary": " · ".join(
                f"{menu['name']} {menu['price']:,}원" if isinstance(menu["price"], int) else f"{menu['name']} {menu['price']}"
                for menu in business["menus"][:2]
            ),
            "lng": None, "lat": None,
        })

    result_areas = []
    for key, base in AREAS.items():
        counts = Counter(f["category"] for f in facilities if f["area"] == key)
        area = {k: v for k, v in base.items() if k != "match"}
        area.update({"id": key, "counts": dict(counts)})
        result_areas.append(area)

    result = {
        "meta": {
            "project_name": "나혼자산다",
            "subtitle": "시흥시 1인 가구 도시선정 의사결정지원 웹사이트",
            "updated_at": "2026-08-07",
            "notice": "시설 위치는 제공된 카카오 장소 수집본을 사용합니다. 착한가격업소는 시흥시 68개 중 현재 6개 비교지역에 주소가 매칭된 25개를 지도에 표시하며, 주거비·교통은 프로토타입용 요약값입니다.",
            "good_price_total": len(good_price_businesses),
            "good_price_mapped": sum(bool(business["area"]) for business in good_price_businesses),
        },
        "areas": result_areas,
        "facilities": facilities,
        "good_price_businesses": good_price_businesses,
        "running_routes": RUNNING_ROUTES,
        "sources": [
            {"name": "생활 인프라", "organization": "카카오 Local 기반 수집본", "scope": "음식점·카페·생활편의·의료·공원·지하철"},
            {"name": "착한가격업소 현황", "organization": "행정안전부", "scope": "2026-06-30 기준 시흥시 업소·메뉴·가격"},
            {"name": "행정동 경계", "organization": "OpenStreetMap contributors", "scope": "시흥시 6개 비교 지역"},
            {"name": "주거비·교통", "organization": "MVP 프로토타입", "scope": "화면 검증용 요약값"},
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(result_areas)} areas, {len(facilities)} facilities, {len(good_price_businesses)} good-price businesses")


if __name__ == "__main__":
    main()
