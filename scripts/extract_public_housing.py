"""LH 공식 주택목록 엑셀에서 청년 매입임대 레코드를 추출한다.

원본 엑셀은 data/raw/public_housing/에 두고, 이 스크립트는 같은 폴더에
public_housing.csv(시흥시) 또는 capital_public_housing.csv(수도권)를 만든다.
한 행은 한 공고에 포함된 한 공급 주택이다.
"""
from __future__ import annotations

import re
import csv
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "public_housing"
OUTPUT = RAW / "public_housing.csv"
CAPITAL_OUTPUT = RAW / "capital_public_housing.csv"
REGION_PATH = ROOT / "data" / "reference" / "capital_lawd_regions.csv"

# 분석기간(2025-08 ~ 2026-07)에 포함되는 LH 경기남부 청년 매입임대 공고.
SOURCES = [
    {
        "file": "lh_youth_2025_3.xlsx",
        "header_row": 10,
        "area_col": 10,
        "deposit_col": 20,  # 청년 일반 임대보증금(원)
        "monthly_col": 21,  # 청년 일반 월임대료(원)
        "date": "2025-08-28",
        "title": "[경기남부] 25년 3차 청년 매입임대주택 예비입주자 모집공고",
        "url": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=26&ccrCnntSysDsCd=03&mi=1026&panId=2015122300018675&uppAisTpCd=13",
    },
    {
        "file": "lh_youth_2025_4.xlsx",
        "header_row": 10,
        "area_col": 10,
        "deposit_col": 21,
        "monthly_col": 22,
        "date": "2025-12-18",
        "title": "[경기남부] 25년 4차 청년 매입임대주택 예비입주자 모집공고",
        "url": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=26&ccrCnntSysDsCd=03&mi=1026&panId=2015122300019211&uppAisTpCd=13",
    },
    {
        "file": "lh_youth_2026_1.xlsx",
        "header_row": 11,
        "area_col": 10,
        "deposit_col": 21,
        "monthly_col": 22,
        "date": "2026-03-31",
        "title": "[경기남부] 26년 1차 청년 매입임대주택 예비입주자 모집공고",
        "url": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=26&ccrCnntSysDsCd=03&mi=1026&panId=2015122300019626&uppAisTpCd=13",
    },
    {
        "file": "lh_youth_2026_2.xlsx",
        "header_row": 11,
        "area_col": 10,
        "deposit_col": 21,
        "monthly_col": 22,
        "date": "2026-06-30",
        "title": "[경기남부] 26년 2차 청년 매입임대주택 예비입주자 모집공고",
        "url": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=26&ccrCnntSysDsCd=03&mi=1026&panId=2015122300020240&uppAisTpCd=13",
    },
]


def as_number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_dong(address: object) -> str | None:
    match = re.search(r"시흥시\s+[^()]*\(([가-힣]+동)", str(address))
    return match.group(1) if match else None


def capital_region_id(address: str, announcement_date: str) -> str | None:
    """주소의 시·군·구를 분석용 지역 ID로 연결한다.

    현재 확보된 공고는 2026-06-30 이전 자료라, 2026-07 행정구역 개편 전의
    시 단위 코드만 매칭한다. 주소에 '성남시 중원구'처럼 구가 있어도 12개월
    비교 단위인 '성남시'로 합친다.
    """
    with REGION_PATH.open(encoding="utf-8", newline="") as handle:
        regions = list(csv.DictReader(handle))
    candidates = [
        row for row in regions
        if row["valid_from"] <= announcement_date[:6] <= row["valid_to"]
        and row["region_name"] in address
        and not re.search(r"(장안구|권선구|팔달구|영통구|수정구|중원구|분당구|만안구|동안구|원미구|소사구|오정구|상록구|단원구|덕양구|일산동구|일산서구|처인구|기흥구|수지구|만세구|효행구|병점구|동탄구)$", row["region_name"])
    ]
    # 예: '광주시'와 '광명시'처럼 주소 안에 한 번만 포함되는 완전한 시·군·구명을 우선한다.
    candidates.sort(key=lambda row: len(row["region_name"]), reverse=True)
    return candidates[0]["region_id"] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("siheung", "capital"), default="siheung")
    args = parser.parse_args()
    records: list[dict[str, object]] = []
    for source in SOURCES:
        path = RAW / source["file"]
        if not path.exists():
            raise SystemExit(f"원본 엑셀이 없습니다: {path}")
        sheet = pd.read_excel(path, header=None)
        seen: set[tuple[object, ...]] = set()
        for _, row in sheet.iloc[source["header_row"] + 1 :].iterrows():
            address = row.iloc[3] if len(row) > 3 else None
            address_text = str(address)
            if args.scope == "siheung" and "시흥시" not in address_text:
                continue
            area = as_number(row.iloc[source["area_col"]])
            deposit = as_number(row.iloc[source["deposit_col"]])
            monthly = as_number(row.iloc[source["monthly_col"]])
            dong = get_dong(address)
            region_id = capital_region_id(address_text, source["date"]) if args.scope == "capital" else None
            if area is None or deposit is None or monthly is None:
                continue
            if args.scope == "siheung" and not dong:
                continue
            if args.scope == "capital" and not region_id:
                continue
            if not 20 <= area <= 39:
                continue
            # 같은 공고 파일 안의 같은 호수만 중복 제거한다.
            unit_key = (address, row.iloc[7] if len(row) > 7 else None, row.iloc[8] if len(row) > 8 else None)
            if unit_key in seen:
                continue
            seen.add(unit_key)
            records.append(
                {
                    "announcement_title": source["title"],
                    "announcement_date": source["date"],
                    "address": address_text,
                    "dong": dong or "",
                    "region_id": region_id or "gyeonggi-siheung",
                    "target_group": "청년 일반",
                    "supply_units": 1,
                    "area_m2": round(area, 3),
                    "deposit_10k": round(deposit / 10_000, 3),
                    "monthly_10k": round(monthly / 10_000, 3),
                    "move_in_date": "",
                    "source_url": source["url"],
                }
            )
    result = pd.DataFrame(records)
    if result.empty:
        raise SystemExit("시흥시·전용 20~39㎡ 조건에 맞는 공공임대 레코드가 없습니다.")
    result = result.sort_values(["announcement_date", "region_id", "address"]).reset_index(drop=True)
    output = CAPITAL_OUTPUT if args.scope == "capital" else OUTPUT
    result.to_csv(output, index=False, encoding="utf-8")
    print(f"wrote {output.relative_to(ROOT)}: {len(result)} records")
    print(result.groupby(["announcement_date", "region_id"]).size().to_string())


if __name__ == "__main__":
    main()
