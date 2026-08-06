"""경기데이터드림 Open API에서 시흥시 1인가구 생활 인프라 자료를 내려받는 수집기.

사용 예:
  cp .env.example .env  # GG_DATA_SERVICE_KEY 입력
  python scripts/collect_gg_infra_poi.py --category laundry
  python scripts/collect_gg_infra_poi.py --category all

원본 응답은 data/raw/infra_poi/에 그대로 보관합니다.

TODO (미확정 항목): 경기데이터드림 상세 페이지가 자바스크립트로만 데이터를 그려서,
아래 CATEGORIES의 endpoint 값을 정적 크롤링으로 확인하지 못했습니다. 로그인한 브라우저에서
https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId={infId}&infSeq=3
(Open API 탭)에 표시되는 실제 "요청 URL"을 복사해 아래 endpoint를 채운 뒤 실행하세요.
필터 파라미터명(SIGUN_NM 등)도 실제 응답 스키마를 보고 조정이 필요할 수 있습니다.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / "data" / "raw" / "infra_poi"
SIHEUNG_SIGUN_NM = "시흥시"

# infId: https://data.gg.go.kr 상세 페이지 식별자 (참고: 1인가구/경기데이터드림_데이터셋_목록.md)
# endpoint: TODO - 로그인 화면의 Open API 탭에서 확인 후 채워 넣기 (예: https://openapi.gg.go.kr/서비스명)
CATEGORIES: dict[str, dict[str, str]] = {
    "laundry": {
        "label": "세탁업 현황_인허가 (코인세탁소)",
        "inf_id": "ID5BS7KC5J3HB8V0BKTA28799592",
        "endpoint": "",  # TODO
    },
    "karaoke": {
        "label": "노래연습장업_인허가 (코인노래방)",
        "inf_id": "DTG5WLA687OMHJMFRXH627862292",
        "endpoint": "",  # TODO
    },
    "fitness": {
        "label": "체력단련장업체 현황 (헬스장)",
        "inf_id": "W79O75LJ92OZ3P30IFST755934",
        "endpoint": "",  # TODO
    },
    "bathhouse": {
        "label": "목욕장업(공동탕업·찜질시설) 현황_인허가",
        "inf_id": "BFUGJ7554MHXY19ZITH014384743",
        "endpoint": "",  # TODO
    },
    "hundred_year_store": {
        "label": "백년가게 지정현황",
        "inf_id": "6XGZIF1N2RBQF7DTIIU831075013",
        "endpoint": "",  # TODO
    },
    "camping": {
        "label": "야영(캠핑)장 현황",
        "inf_id": "6243I631A7C7L7M0JR1B21715119",
        "endpoint": "",  # TODO
    },
    "delivery_box": {
        "label": "여성안심무인택배함 현황",
        "inf_id": "97BM2OZKIYD2GMWJZ0UI26817441",
        "endpoint": "",  # TODO
    },
    "mental_health_center": {
        "label": "정신 건강 복지센터 현황",
        "inf_id": "DR5A9PI77Q1831V975Q1889283",
        "endpoint": "",  # TODO
    },
    "animal_hospital": {
        "label": "동물병원 현황",
        "inf_id": "Y5M0CVS8XM2C821G09A813809578",
        "endpoint": "",  # TODO
    },
    "tourist_spot": {
        "label": "경기도 명소 현황",
        "inf_id": "BM4IHHEFJAEFIJMM6SC031171354",
        "endpoint": "",  # TODO
    },
    "public_health_center": {
        "label": "보건소 현황",
        "inf_id": "302402102AS0TA1SY80R404746",
        "endpoint": "",  # TODO
    },
    "lunchbox_maker": {
        "label": "도시락제조업 현황",
        "inf_id": "BNY245C2R3NE25DRJT3X14569434",
        "endpoint": "",  # TODO
    },
    "delivery_franchise": {
        "label": "경기도 공공배달앱 배달특급 가맹점",
        "inf_id": "WYR67CWJMLW6JZRWKE0D32401928",
        "endpoint": "",  # TODO
    },
    "pet_convenience": {
        "label": "반려동물 생활편의 시설",
        "inf_id": "UX2OPRPXURITBZQ3L7W732294628",
        "endpoint": "",  # TODO
    },
    "performance_hall": {
        "label": "공연장 현황",
        "inf_id": "N4LY6H5VP5047641W5DQ1742165",
        "endpoint": "",  # TODO
    },
    "cultural_facility": {
        "label": "경기도 문화시설지 현황",
        "inf_id": "UFGNHHHFT8SWMJ0WK4J831124989",
        "endpoint": "",  # TODO
    },
    "addiction_center": {
        "label": "중독관리통합지원센터 현황",
        "inf_id": "VP6N5SJ9BHMEQ9RTWGAY15043133",
        "endpoint": "",  # TODO
    },
}


def fetch_category(name: str, config: dict[str, str], service_key: str) -> None:
    if not config["endpoint"]:
        raise SystemExit(
            f"'{name}' ({config['label']})의 endpoint가 비어 있습니다. "
            f"https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId={config['inf_id']}&infSeq=3 "
            "에서 실제 요청 URL을 확인해 CATEGORIES에 채워 넣으세요."
        )

    rows: list[dict] = []
    page = 1
    while True:
        response = requests.get(
            config["endpoint"],
            params={
                "KEY": service_key,
                "Type": "json",
                "pIndex": page,
                "pSize": 1000,
                "SIGUN_NM": SIHEUNG_SIGUN_NM,
            },
            timeout=30,
        )
        if not response.ok:
            # response.raise_for_status()는 예외 메시지에 인증키가 담긴 전체 URL을 노출할 수 있다.
            raise SystemExit(f"{name} 요청 실패: HTTP {response.status_code}")
        payload = response.json()
        page_rows = _extract_rows(payload)
        rows.extend(page_rows)
        if len(page_rows) < 1000:
            break
        page += 1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / f"{name}.json"
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {output.relative_to(ROOT)} ({len(rows)} rows)")


def _extract_rows(payload: dict) -> list[dict]:
    # 경기데이터드림 응답 포맷은 서비스마다 head/row 구조가 다를 수 있어, 첫 실행 뒤
    # 실제 JSON 구조를 보고 이 함수를 조정해야 한다.
    for value in payload.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "row" in item:
                    return item["row"]
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=[*CATEGORIES, "all"], default="all")
    args = parser.parse_args()

    service_key = os.getenv("GG_DATA_SERVICE_KEY")
    if not service_key:
        raise SystemExit("GG_DATA_SERVICE_KEY 환경변수가 필요합니다. .env.example을 확인하세요.")

    targets = CATEGORIES if args.category == "all" else {args.category: CATEGORIES[args.category]}
    for name, config in targets.items():
        fetch_category(name, config, service_key)


if __name__ == "__main__":
    main()
