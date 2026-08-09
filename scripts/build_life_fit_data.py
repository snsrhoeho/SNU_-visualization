"""Build the static dataset used by the Nahonja Sanda prototype.

The source CSV is left untouched.  The output contains only the fields the
browser needs, grouped by legal dong (법정동) parsed from parcel addresses.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
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

LEGAL_DONG_PATTERN = re.compile(r"시흥시\s+([^\s(),]+동)(?:\s|\d|,|\)|$)")

RUNNING_ROUTES = [
    {
        "id": "baegot-life-loop", "area": "배곧동", "name": "배곧생명공원 물빛 루프",
        "distance_km": 3.2, "duration_min": 28, "difficulty": "쉬움", "surface": "공원 산책로",
        "summary": "배곧생명공원의 수변과 잔디광장을 한 바퀴 도는 입문용 순환 코스",
        "highlights": ["수변 풍경", "평탄한 구간", "화장실·주차장"],
        "coordinates": [[126.7196,37.3712],[126.7203,37.3701],[126.7245,37.3725],[126.7228,37.3740],[126.7197,37.3735],[126.7196,37.3712]],
        "svg_points": [[14,69],[16,62],[22,60],[27,66],[24,74],[17,76],[14,69]],
        "basis": "배곧생명공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "okgu-park-loop", "area": "정왕동", "name": "옥구공원 초록 언덕 루프",
        "distance_km": 2.8, "duration_min": 25, "difficulty": "보통", "surface": "공원길·완만한 언덕",
        "summary": "한국정원과 조가비무대를 지나 옥구공원의 녹지를 연결하는 코스",
        "highlights": ["한국정원", "완만한 오르막", "운동시설"],
        "coordinates": [[126.7091,37.3524],[126.7115,37.3540],[126.7134,37.3555],[126.7132,37.3561],[126.7100,37.3545],[126.7091,37.3524]],
        "svg_points": [[41,70],[43,62],[49,59],[55,65],[54,74],[47,78],[41,70]],
        "basis": "옥구공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "oido-history-coast", "area": "정왕동", "name": "오이도 역사·해안 코스",
        "distance_km": 4.6, "duration_min": 42, "difficulty": "보통", "surface": "해안 보행로·공원길",
        "summary": "오이도 선사유적공원과 해안 방향의 주요 지점을 연결하는 풍경 코스",
        "highlights": ["선사유적공원", "서해 풍경", "노을 추천"],
        "coordinates": [[126.6962,37.3430],[126.6934,37.3472],[126.6900,37.3481],[126.6900,37.3416],[126.6908,37.3348],[126.6962,37.3430]],
        "svg_points": [[70,67],[72,59],[79,56],[87,62],[89,73],[82,78],[74,75],[70,67]],
        "basis": "시흥시 오이도 공원·해안 지점 기반 MVP 추천 동선",
    },
    {
        "id": "sincheon-park-link", "area": "신천동", "name": "신천 도심공원 연결 코스",
        "distance_km": 3.6, "duration_min": 33, "difficulty": "쉬움", "surface": "도심 보행로·공원길",
        "summary": "신천공원에서 둥지공원·바람길공원 방향으로 이어지는 생활권 코스",
        "highlights": ["도심 접근성", "여러 공원", "가벼운 야간런"],
        "coordinates": [[126.7849,37.4381],[126.7876,37.4385],[126.7889,37.4366],[126.7916,37.4355],[126.7904,37.4351],[126.7854,37.4356],[126.7849,37.4381]],
        "svg_points": [[52,22],[57,13],[65,11],[70,17],[68,25],[61,29],[55,27],[52,22]],
        "basis": "신천동 공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "eungye-lake-loop", "area": "은행동", "name": "은계호수공원 산뜻 루프",
        "distance_km": 2.4, "duration_min": 22, "difficulty": "쉬움", "surface": "호수공원 산책로",
        "summary": "은계호수공원 수변을 중심으로 짧고 가볍게 반복할 수 있는 코스",
        "highlights": ["호수 풍경", "카페 접근성", "평탄한 루프"],
        "coordinates": [[126.8034,37.4443],[126.8059,37.4439],[126.8069,37.4447],[126.8040,37.4462],[126.8026,37.4452],[126.8034,37.4443]],
        "svg_points": [[78,22],[82,13],[89,12],[94,19],[92,28],[84,31],[78,22]],
        "basis": "은계호수공원 시설 좌표 기반 MVP 추천 동선",
    },
    {
        "id": "daeya-eungye-forest", "area": "대야동", "name": "대야–은계숲 그린 코스",
        "distance_km": 4.1, "duration_min": 38, "difficulty": "보통", "surface": "공원길·생활도로",
        "summary": "대야공원에서 은계공원과 은계숲생태공원 방향을 연결하는 녹지 코스",
        "highlights": ["연속된 공원", "중거리 훈련", "생활권 접근"],
        "coordinates": [[126.7883,37.4468],[126.7942,37.4468],[126.7959,37.4476],[126.8005,37.4483],[126.7963,37.4460],[126.7906,37.4484],[126.7883,37.4468]],
        "svg_points": [[16,24],[20,13],[29,10],[37,16],[39,27],[31,32],[22,31],[16,24]],
        "basis": "대야·은계권 공원 시설 좌표 기반 MVP 추천 동선",
    },
]


def legal_dong(address: str) -> str | None:
    match = LEGAL_DONG_PATTERN.search(address or "")
    return match.group(1) if match else None


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def road_key(address: str) -> str | None:
    match = re.search(r"시흥시\s+([^\s,]+(?:로|길)(?:\d+번길)?)", address or "")
    return match.group(1).replace(" ", "") if match else None


def tile_layout(centers: dict[str, tuple[float, float]]) -> dict[str, dict]:
    """Create a compact, geography-aware tile map until legal-dong polygons are connected."""
    ordered = sorted(centers, key=lambda name: (-centers[name][0], centers[name][1], name))
    columns = 7
    result = {}
    for index, name in enumerate(ordered):
        row, column = divmod(index, columns)
        row_items = ordered[row * columns:(row + 1) * columns]
        row_items.sort(key=lambda item: centers[item][1])
        column = row_items.index(name)
        x = 8.5 + column * 14.3
        y = 12 + row * 20.5
        radius = 5.4
        points = [
            (x + math.cos(math.radians(60 * point)) * radius, y + math.sin(math.radians(60 * point)) * radius)
            for point in range(6)
        ]
        result[name] = {"x": round(x, 2), "y": round(y, 2), "polygon": " ".join(f"{px:.2f},{py:.2f}" for px, py in points)}
    return result


def read_good_price_businesses(road_dongs: dict[str, str]) -> list[dict]:
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
            area = legal_dong(address)
            if not area:
                area = road_dongs.get(road_key(address) or "")
            businesses.append({
                "id": f"good-price-{index}", "area": area,
                "category": "good_price", "business_type": row.get("업종", "").strip(),
                "name": name, "address": address, "phone": row.get("연락처", "").strip(),
                "menus": menus, "url": f"https://map.naver.com/p/search/{quote(name + ' ' + address)}",
            })
    return businesses


def main() -> None:
    facilities = []
    road_dong_votes: dict[str, Counter] = defaultdict(Counter)
    with SOURCE.open(encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            category = CATEGORY_MAP.get(row.get("검색카테고리", ""))
            if not category:
                continue
            try:
                lng, lat = float(row["x"]), float(row["y"])
            except (TypeError, ValueError):
                continue
            area = legal_dong(row.get("address_name", ""))
            if not area:
                continue
            key = road_key(row.get("road_address_name", ""))
            if key:
                road_dong_votes[key][area] += 1
            facilities.append({
                "id": row.get("id", ""), "area": area, "category": category,
                "name": row.get("place_name", ""), "detail": row.get("category_name", ""),
                "address": row.get("road_address_name") or row.get("address_name", ""),
                "phone": row.get("phone", ""), "lng": lng, "lat": lat,
                "url": row.get("place_url", ""),
            })

    road_dongs = {
        key: counts.most_common(1)[0][0]
        for key, counts in road_dong_votes.items()
        if counts
    }
    good_price_businesses = read_good_price_businesses(road_dongs)
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

    coordinate_groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for facility in facilities:
        if facility.get("lat") is not None and facility.get("lng") is not None:
            coordinate_groups[facility["area"]].append((facility["lat"], facility["lng"]))
    centers = {
        name: (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        for name, points in coordinate_groups.items()
    }
    layout = tile_layout(centers)
    stations = [facility for facility in facilities if facility["category"] == "subway" and facility.get("lat") is not None]
    result_areas = []
    for name, tile in layout.items():
        center_lat, center_lng = centers[name]
        counts = Counter(facility["category"] for facility in facilities if facility["area"] == name)
        nearest = min(
            stations,
            key=lambda station: haversine_m(center_lat, center_lng, station["lat"], station["lng"]),
            default=None,
        )
        station_distance = round(haversine_m(center_lat, center_lng, nearest["lat"], nearest["lng"])) if nearest else None
        station_walk = max(1, math.ceil(station_distance * 1.25 / 67)) if station_distance is not None else None
        result_areas.append({
            "id": name, "name": name, **tile,
            "center_lat": round(center_lat, 7), "center_lng": round(center_lng, 7),
            "counts": dict(counts),
            "station": nearest["name"] if nearest else None,
            "station_walk": station_walk,
            "station_distance_m": station_distance,
            "station_basis": "법정동 시설 중심점과 역 좌표 간 직선거리 환산 추정",
            "bus": None, "routes": None,
            "rent": None, "jeonse": None, "sale": None,
        })

    result = {
        "meta": {
            "project_name": "나혼자산다",
            "subtitle": "시흥시 1인 가구 도시선정 의사결정지원 웹사이트",
            "updated_at": "2026-08-09",
            "area_unit": "법정동",
            "area_count": len(result_areas),
            "map_mode": "법정동 위치 기반 타일 지도",
            "notice": f"시설 주소를 기준으로 원본에 등장하는 시흥시 법정동 {len(result_areas)}개를 비교합니다. 지도는 실제 경계가 아닌 위치 기반 타일이며, 역 도보시간은 법정동 시설 중심점에서 환산한 추정치입니다.",
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
            {"name": "법정동 분류", "organization": "시설 지번주소", "scope": f"원본에 등장하는 시흥시 법정동 {len(result_areas)}개"},
            {"name": "교통 접근성", "organization": "카카오 Local 기반 수집본", "scope": "법정동 시설 중심점과 지하철 좌표 간 추정"},
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(result_areas)} legal dongs, {len(facilities)} facilities, {len(good_price_businesses)} good-price businesses")


if __name__ == "__main__":
    main()
