"""원본 전월세·공공임대 자료를 배포용 dashboard.json으로 정제한다.

원본 파일은 절대 수정하지 않는다. 민간 전월세 API XML은 data/raw/private_rent/에,
공공임대 검토본은 data/raw/public_housing/public_housing.csv에 둔다.

실행 예:
  .venv/bin/python scripts/build_dashboard_data.py

주의: 실제 첫 수집 뒤 XML의 필드명, 동명, 공고별 공급 호수 중복 여부를 반드시
검토해야 한다. 이 스크립트는 그 검토를 대신하지 않는다.
"""
from __future__ import annotations

import copy
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PRIVATE = ROOT / "data" / "raw" / "private_rent"
PUBLIC_PATH = ROOT / "data" / "raw" / "public_housing" / "public_housing.csv"
DEMO_PATH = ROOT / "data" / "processed" / "dashboard.json"
OUTPUT = ROOT / "data" / "processed" / "dashboard_actual.json"
MIN_AREA, MAX_AREA = 20, 39


def numeric(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(value))
    return float(cleaned) if cleaned else None


def text_of(item: ET.Element, *names: str) -> str | None:
    for name in names:
        element = item.find(name)
        if element is not None and element.text:
            return element.text.strip()
    return None


def normalize_dong(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\s+", "", value)
    # 법정동 본번·부번이나 괄호는 제거하되 '정왕1동'처럼 숫자가 동명인 경우는 보존한다.
    value = re.sub(r"\([^)]*\)", "", value)
    return value if value.endswith("동") else None


def parse_private_xml() -> pd.DataFrame:
    rows: list[dict] = []
    for xml_path in sorted(RAW_PRIVATE.glob("*.xml")):
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as error:
            print(f"skip malformed XML: {xml_path.name} ({error})")
            continue
        for item in root.findall(".//item"):
            area = numeric(text_of(item, "전용면적", "excluUseAr"))
            deposit = numeric(text_of(item, "보증금액", "deposit"))
            monthly = numeric(text_of(item, "월세금액", "monthlyRent"))
            dong = normalize_dong(text_of(item, "법정동", "umdNm"))
            year = text_of(item, "계약년", "dealYear")
            month = text_of(item, "계약월", "dealMonth")
            day = text_of(item, "계약일", "dealDay")
            if None in (area, deposit, monthly) or not dong or not (MIN_AREA <= area <= MAX_AREA):
                continue
            is_officetel = xml_path.name.startswith("officetel_")
            rows.append({
                "dong": dong,
                "area_m2": area,
                "deposit_10k": deposit,
                "monthly_10k": monthly,
                "date": f"{year or ''}-{str(month or '').zfill(2)}-{str(day or '').zfill(2)}".strip("-"),
                "kind": "민간 오피스텔" if is_officetel else "민간 연립다세대",
                "source": "국토교통부 전월세 실거래가",
                "url": "https://www.data.go.kr/data/15126475/openapi.do" if is_officetel else "https://www.data.go.kr/data/15126473/openapi.do",
            })
    if not rows:
        raise SystemExit("면적 조건을 만족하는 민간 전월세 XML 레코드가 없습니다. API 응답과 필드명을 점검하세요.")
    return pd.DataFrame(rows)


def read_public() -> pd.DataFrame:
    if not PUBLIC_PATH.exists():
        raise SystemExit(f"공공임대 CSV가 없습니다: {PUBLIC_PATH}")
    public = pd.read_csv(PUBLIC_PATH)
    required = {"announcement_title", "announcement_date", "dong", "supply_units", "area_m2", "deposit_10k", "monthly_10k", "source_url"}
    missing = required - set(public.columns)
    if missing:
        raise SystemExit(f"공공임대 CSV 필수 열 누락: {', '.join(sorted(missing))}")
    public = public[public["area_m2"].between(MIN_AREA, MAX_AREA)].copy()
    public["dong"] = public["dong"].map(normalize_dong)
    public = public.dropna(subset=["dong", "supply_units", "deposit_10k", "monthly_10k"])
    if public.empty:
        raise SystemExit("면적 20~39㎡ 및 필수 가격을 만족하는 공공임대 레코드가 없습니다.")
    return public


def converted_monthly(deposit: pd.Series | float, monthly: pd.Series | float, rate: float = 0.05):
    return monthly + deposit * rate / 12


def base_area_layout() -> dict[str, dict]:
    demo = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    return {area["name"]: area for area in demo["areas"]}


def main() -> None:
    private = parse_private_xml()
    public = read_public()
    layout = base_area_layout()
    unknown = sorted((set(private.dong) | set(public.dong)) - set(layout))
    if unknown:
        print("warning: 지도 레이아웃에 없는 동은 제외됩니다:", ", ".join(unknown))

    private["converted"] = converted_monthly(private.deposit_10k, private.monthly_10k)
    public["converted"] = converted_monthly(public.deposit_10k, public.monthly_10k)
    private_summary = private.groupby("dong").agg(
        private_deposit=("deposit_10k", "median"), private_monthly=("monthly_10k", "median"), deals=("dong", "size")
    )
    public_summary = public.groupby("dong").agg(
        public_deposit=("deposit_10k", "median"), public_monthly=("monthly_10k", "median"),
        supply_units=("supply_units", "sum"), notices=("announcement_title", "nunique")
    )

    result = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    result["areas"] = []
    for dong, design in layout.items():
        if dong not in private_summary.index and dong not in public_summary.index:
            continue
        area = copy.deepcopy(design)
        p = private_summary.loc[dong] if dong in private_summary.index else None
        q = public_summary.loc[dong] if dong in public_summary.index else None
        # 한쪽이 없는 지역은 0으로 보이지 않게 한다. 웹에서는 상세 해석 전에 데이터 공백으로 확인해야 한다.
        area.update({
            "private_deposit": float(p.private_deposit) if p is not None else 0,
            "private_monthly": float(p.private_monthly) if p is not None else 0,
            "public_deposit": float(q.public_deposit) if q is not None else 0,
            "public_monthly": float(q.public_monthly) if q is not None else 0,
            "supply_units": int(q.supply_units) if q is not None else 0,
            "notices": int(q.notices) if q is not None else 0,
            "deals": int(p.deals) if p is not None else 0,
        })
        result["areas"].append(area)
    if not result["areas"]:
        raise SystemExit("시연 지도 레이아웃에 매칭되는 동이 없습니다. normalize_dong 규칙을 확인하세요.")

    private_records = private.assign(area=private.dong).rename(columns={"deposit_10k":"deposit", "monthly_10k":"monthly", "area_m2":"area_m2"})
    public_records = public.assign(area=public.dong, kind="청년 공공임대", source="공식 모집공고", date=public.announcement_date, url=public.source_url).rename(columns={"deposit_10k":"deposit", "monthly_10k":"monthly"})
    record_columns = ["area", "kind", "area_m2", "deposit", "monthly", "date", "source", "url"]
    all_records = pd.concat([private_records[record_columns], public_records[record_columns]], ignore_index=True)
    all_records = all_records[all_records.area.isin(layout)].sort_values("date", ascending=False)
    result["listings"] = all_records.head(500).to_dict(orient="records")

    monthly = private.assign(month=private.date.str.slice(0, 7)).groupby("month").converted.median().reset_index()
    result["monthly_trend"] = [{"month": row.month, "rent": round(float(row.converted), 1)} for row in monthly.itertuples(index=False) if row.month]
    result["meta"].update({
        "data_mode": "actual",
        "updated_at": "실제 원본 수집 후 생성됨",
        "notice": "실제 수집본입니다. 공고별 공급 호수 중복, 동명 매칭, API 원본의 누락 여부를 제출 전에 재검토하세요.",
        "scope": "시흥시 · 오피스텔·연립다세대 · 전용면적 20~39㎡ · 청년 공공임대 모집공고",
    })
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: areas={len(result['areas'])}, records={len(result['listings'])}")


if __name__ == "__main__":
    main()
