"""국토교통부 전월세 실거래가 API에서 시흥시 자료를 내려받는 수집기.

사용 예:
  cp .env.example .env  # DATA_GO_KR_SERVICE_KEY 입력
  python scripts/collect_private_rent.py --from 202508 --to 202607

원본 응답은 data/raw/private_rent/에 그대로 보관합니다. API 필드명은 서비스
개편에 따라 달라질 수 있으므로, 실제 첫 실행 뒤 README의 점검 절차를 따릅니다.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / "data" / "raw" / "private_rent"
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", required=True, help="YYYYMM")
    parser.add_argument("--to", dest="end", required=True, help="YYYYMM")
    args = parser.parse_args()
    service_key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not service_key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다. .env.example을 확인하세요.")
    # 공공데이터포털의 Encoding Key와 Decoding Key를 모두 받을 수 있게 한 번만 복호화한다.
    service_key = unquote(service_key.strip())

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for month in months_between(args.start, args.end):
        for housing_type, endpoint in ENDPOINTS.items():
            response = requests.get(
                endpoint,
                params={"serviceKey": service_key, "LAWD_CD": SIHEUNG_LAWD_CD, "DEAL_YMD": month, "numOfRows": 9999},
                timeout=30,
            )
            if not response.ok:
                # requests.raise_for_status()는 예외에 API 키가 포함된 전체 URL을 출력할 수 있다.
                raise SystemExit(f"{housing_type} {month} 요청 실패: HTTP {response.status_code}")
            output = RAW_DIR / f"{housing_type}_{month}.xml"
            output.write_bytes(response.content)
            print(f"saved {output.relative_to(ROOT)} ({len(response.content):,} bytes)")


if __name__ == "__main__":
    main()
