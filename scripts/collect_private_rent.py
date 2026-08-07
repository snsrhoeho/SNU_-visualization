"""국토교통부 전월세 실거래가 API에서 원본 XML을 내려받는 수집기.

사용 예:
  cp .env.example .env  # DATA_GO_KR_SERVICE_KEY 입력
  # 기존 시흥시 수집본
  python scripts/collect_private_rent.py --scope siheung --from 202508 --to 202607

  # 수도권 시·군·구 수집본 (서울·경기·인천)
  python scripts/collect_private_rent.py --scope capital --from 202508 --to 202607

원본 응답은 data/raw/private_rent/에 그대로 보관합니다. API 필드명은 서비스
개편에 따라 달라질 수 있으므로, 실제 첫 실행 뒤 README의 점검 절차를 따릅니다.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
import csv
import time
from urllib.parse import unquote
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / "data" / "raw" / "private_rent"
REGION_PATH = ROOT / "data" / "reference" / "capital_lawd_regions.csv"
SIHEUNG_LAWD_CD = "41390"
ENDPOINTS = {
    "officetel": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
    "rowhouse": "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
}


def months_between(start: str, end: str) -> list[str]:
    cursor = datetime.strptime(start, "%Y%m")
    finish = datetime.strptime(end, "%Y%m")
    months: list[str] = []
    while cursor <= finish:
        months.append(cursor.strftime("%Y%m"))
        cursor = datetime(cursor.year + (cursor.month == 12), (cursor.month % 12) + 1, 1)
    return months


def read_regions(scope: str, month: str) -> list[dict[str, str]]:
    """해당 계약월에 유효한 시·군·구만 돌려준다.

    인천은 2026-07-01 구 개편 때문에, 변경 전/후 코드가 같은 달에 섞이지
    않도록 reference CSV의 유효기간을 기준으로 선택한다.
    """
    if scope == "siheung":
        return [{"region_id": "gyeonggi-siheung", "region_name": "시흥시", "lawd_cd": SIHEUNG_LAWD_CD}]
    with REGION_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row["valid_from"] <= month <= row["valid_to"]]


def api_error(response_content: bytes) -> str | None:
    """공공 API의 XML 오류를 URL/비밀키를 노출하지 않고 요약한다."""
    try:
        root = ET.fromstring(response_content)
    except ET.ParseError:
        return "XML 응답 형식이 아닙니다"
    code = root.findtext(".//resultCode")
    if code and code not in {"00", "000"}:
        message = root.findtext(".//resultMsg") or "API 오류"
        return f"{code}: {message}"
    return None


def target_path(scope: str, region_id: str, housing_type: str, month: str) -> Path:
    if scope == "siheung":
        return RAW_DIR / f"{housing_type}_{month}.xml"
    return RAW_DIR / "capital" / region_id / f"{housing_type}_{month}.xml"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("siheung", "capital"), default="siheung")
    parser.add_argument("--from", dest="start", required=True, help="YYYYMM")
    parser.add_argument("--to", dest="end", required=True, help="YYYYMM")
    parser.add_argument("--overwrite", action="store_true", help="기존 원본도 다시 요청")
    parser.add_argument("--delay", type=float, default=0.1, help="요청 간 대기(초, 기본 0.1)")
    args = parser.parse_args()
    service_key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not service_key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다. .env.example을 확인하세요.")
    # 공공데이터포털의 Encoding Key와 Decoding Key를 모두 받을 수 있게 한 번만 복호화한다.
    service_key = unquote(service_key.strip())

    for month in months_between(args.start, args.end):
        regions = read_regions(args.scope, month)
        if not regions:
            raise SystemExit(f"{month}에 유효한 수집 지역이 없습니다. {REGION_PATH.name}을 확인하세요.")
        for housing_type, endpoint in ENDPOINTS.items():
            for region in regions:
                output = target_path(args.scope, region["region_id"], housing_type, month)
                if output.exists() and not args.overwrite:
                    print(f"skip  {output.relative_to(ROOT)}")
                    continue
                response = requests.get(
                    endpoint,
                    params={"serviceKey": service_key, "LAWD_CD": region["lawd_cd"], "DEAL_YMD": month, "numOfRows": 9999},
                    timeout=30,
                )
                if not response.ok:
                    # requests.raise_for_status()는 예외에 API 키가 포함된 전체 URL을 출력할 수 있다.
                    raise SystemExit(f"{region['region_name']} {housing_type} {month} 요청 실패: HTTP {response.status_code}")
                error = api_error(response.content)
                if error:
                    raise SystemExit(f"{region['region_name']} {housing_type} {month} API 오류: {error}")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(response.content)
                print(f"saved {output.relative_to(ROOT)} ({len(response.content):,} bytes)")
                if args.delay:
                    time.sleep(args.delay)


if __name__ == "__main__":
    main()
