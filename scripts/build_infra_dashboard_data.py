"""경기데이터드림 원본(및 수기 검증본)을 배포용 infra_dashboard.json으로 정제한다.

원본 파일은 절대 수정하지 않는다. API 수집본은 data/raw/infra_poi/*.json,
수기로 검증한 항목(좌표 미확정 등)은 data/raw/infra_poi/*_manual.csv에 둔다.

실행 예:
  python scripts/build_infra_dashboard_data.py

주의: 이 스크립트를 실행하는 시점에 data/raw/infra_poi/*.json이 없는 카테고리는
0건이 아니라 "미수집"으로 표시한다 — collect_gg_infra_poi.py의 endpoint가 아직
채워지지 않았기 때문일 수 있다. 자세한 배경은 1인가구/경기데이터드림_데이터셋_목록.md 참고.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "infra_poi"
BASE_LAYOUT_PATH = ROOT / "data" / "processed" / "dashboard.json"
OUTPUT = ROOT / "data" / "processed" / "infra_dashboard.json"

CATEGORIES = [
    "laundry", "karaoke", "fitness", "bathhouse", "hundred_year_store",
    "camping", "delivery_box", "mental_health_center", "animal_hospital",
    "tourist_spot", "public_health_center", "lunchbox_maker",
    "delivery_franchise", "pet_convenience", "performance_hall",
    "cultural_facility", "addiction_center",
]

SOURCES = [
    {"name": "세탁업 현황_인허가", "organization": "경기도", "description": "코인세탁소 포함", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=ID5BS7KC5J3HB8V0BKTA28799592"},
    {"name": "노래연습장업_인허가", "organization": "경기도", "description": "코인노래방 포함", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=DTG5WLA687OMHJMFRXH627862292"},
    {"name": "체력단련장업체 현황", "organization": "경기도", "description": "헬스장·트레이닝장", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=W79O75LJ92OZ3P30IFST755934"},
    {"name": "목욕장업(공동탕업·찜질시설) 현황_인허가", "organization": "경기도", "description": "원룸·오피스텔 욕조 부재 보완", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=BFUGJ7554MHXY19ZITH014384743"},
    {"name": "백년가게 지정현황", "organization": "중소벤처기업부·경기도", "description": "30년 이상 운영 소상공인 인증", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=6XGZIF1N2RBQF7DTIIU831075013"},
    {"name": "야영(캠핑)장 현황", "organization": "경기도·시흥시", "description": "시흥시 4곳 수기 검증(좌표 미확정)", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=6243I631A7C7L7M0JR1B21715119"},
    {"name": "여성안심무인택배함 현황", "organization": "경기도", "description": "여성·1인가구 안전 인프라", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=97BM2OZKIYD2GMWJZ0UI26817441"},
    {"name": "정신 건강 복지센터 현황", "organization": "경기도", "description": "1인가구 고독·정신건강 지원", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=DR5A9PI77Q1831V975Q1889283"},
    {"name": "동물병원 현황", "organization": "경기도", "description": "반려동물 의료", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=Y5M0CVS8XM2C821G09A813809578"},
    {"name": "경기도 명소 현황", "organization": "경기관광공사", "description": "관광", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=BM4IHHEFJAEFIJMM6SC031171354"},
    {"name": "보건소 현황", "organization": "경기도", "description": "건강", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=302402102AS0TA1SY80R404746"},
    {"name": "도시락제조업 현황", "organization": "경기도", "description": "1인분 소포장 식사", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=BNY245C2R3NE25DRJT3X14569434"},
    {"name": "경기도 공공배달앱 배달특급 가맹점", "organization": "경기도", "description": "1인가구 배달 수요", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=WYR67CWJMLW6JZRWKE0D32401928"},
    {"name": "반려동물 생활편의 시설", "organization": "경기도", "description": "미용·호텔링 등", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=UX2OPRPXURITBZQ3L7W732294628"},
    {"name": "공연장 현황", "organization": "경기도", "description": "문화", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=N4LY6H5VP5047641W5DQ1742165"},
    {"name": "경기도 문화시설지 현황", "organization": "경기도", "description": "박물관·미술관·문예회관", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=UFGNHHHFT8SWMJ0WK4J831124989"},
    {"name": "중독관리통합지원센터 현황", "organization": "경기도", "description": "1인가구 고립·중독 이슈", "url": "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=VP6N5SJ9BHMEQ9RTWGAY15043133"},
]


def base_area_layout() -> dict[str, dict]:
    demo = json.loads(BASE_LAYOUT_PATH.read_text(encoding="utf-8"))
    return {area["name"]: area for area in demo["areas"]}


def load_manual_places() -> list[dict]:
    places: list[dict] = []
    for csv_path in sorted(RAW_DIR.glob("*_manual.csv")):
        rows = pd.read_csv(csv_path).fillna("")
        for i, row in enumerate(rows.itertuples(index=False), start=1):
            places.append({
                "id": f"{csv_path.stem}_{i}",
                "name": row.name,
                "category": row.category,
                "address": row.address,
                "lat": None,
                "lon": None,
                "dong_id": None,
                "dong_guess": getattr(row, "dong_guess", "") or None,
                "verified": "manual",
                "note": getattr(row, "note", "") or None,
                "source": csv_path.name,
                "url": getattr(row, "source_url", "") or None,
            })
    return places


def load_api_places() -> list[dict]:
    # collect_gg_infra_poi.py의 endpoint가 채워져 실행된 뒤에는 이 함수가 실제 파싱을 담당해야 한다.
    # 현재는 raw JSON 스키마가 확정되지 않아 존재 여부만 확인하고 건수를 places에 병합하지 않는다.
    places: list[dict] = []
    for category in CATEGORIES:
        raw_path = RAW_DIR / f"{category}.json"
        if raw_path.exists():
            print(f"note: {raw_path.name} 발견 — 실제 파싱 로직 구현 필요 (아직 미구현)")
    return places


def main() -> None:
    layout = base_area_layout()
    manual_places = load_manual_places()
    api_places = load_api_places()
    places = manual_places + api_places

    collected_categories = {p["category"] for p in places}
    missing_categories = [c for c in CATEGORIES if c not in collected_categories]

    areas = []
    for dong, design in layout.items():
        area = {
            "id": design["id"],
            "name": dong,
            "x": design["x"],
            "y": design["y"],
            "polygon": design["polygon"],
            "counts": {c: None for c in CATEGORIES},  # None = 미수집, 0과 구분
        }
        areas.append(area)

    result = {
        "meta": {
            "project_name": "시흥 1인가구 생활 인프라 지도",
            "data_mode": "demo_partial",
            "updated_at": "야영장 4곳만 수기 검증, 나머지는 미수집",
            "notice": (
                "이 파일은 참고용 초안입니다. 캠핑장 4곳은 검색으로 실존을 확인했으나 좌표는 "
                "미확정(Naver Geocoding 필요)이며, 나머지 카테고리는 collect_gg_infra_poi.py의 "
                "Open API endpoint가 채워진 뒤 실제 수집이 필요합니다. "
                "자세한 내용은 1인가구/경기데이터드림_데이터셋_목록.md 참고."
            ),
            "scope": "시흥시 · 1인가구 생활 인프라 (세탁·놀이·운동·상권인증·자연·문화·먹거리·의료·안전)",
            "missing_categories": missing_categories,
        },
        "areas": areas,
        "places": places,
        "sources": SOURCES,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: places={len(places)}, missing_categories={missing_categories}")


if __name__ == "__main__":
    main()
