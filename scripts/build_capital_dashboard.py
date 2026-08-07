"""수도권 민간 전월세 원본을 시·군·구 단위 대시보드 데이터로 정제한다.

공공임대 원본이 아직 없으면 민간 전월세 미리보기만 생성한다. 이 결과는
공공임대 공급량과 비교한 '최종 분석본'이 아니므로 dashboard.json을 덮어쓰지 않는다.
"""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "private_rent" / "capital"
REGION_PATH = ROOT / "data" / "reference" / "capital_lawd_regions.csv"
PUBLIC_PATH = ROOT / "data" / "raw" / "public_housing" / "capital_public_housing.csv"
OUTPUT = ROOT / "data" / "processed" / "capital_private_preview.json"
QUALITY_OUTPUT = ROOT / "data" / "processed" / "capital_private_quality.json"
MIN_AREA, MAX_AREA = 20, 39

# 2026-07-01 이후 구 단위로 바뀐 곳은 기존 시 단위와 합쳐서 12개월 비교를 유지한다.
CITY_PARENT = {
    "gyeonggi-suwon-": "gyeonggi-suwon",
    "gyeonggi-seongnam-": "gyeonggi-seongnam",
    "gyeonggi-anyang-": "gyeonggi-anyang",
    "gyeonggi-bucheon-": "gyeonggi-bucheon",
    "gyeonggi-ansan-": "gyeonggi-ansan",
    "gyeonggi-goyang-": "gyeonggi-goyang",
    "gyeonggi-yongin-": "gyeonggi-yongin",
    "gyeonggi-hwaseong-": "gyeonggi-hwaseong",
}
INCHEON_REORG_PREFIXES = (
    "incheon-jemulpo",
    "incheon-yeongjong",
    "incheon-seohae",
    "incheon-geomdan",
)


def numeric(value: str | None) -> float | None:
    if value is None:
        return None
    text = re.sub(r"[^0-9.]", "", str(value))
    return float(text) if text else None


def text_of(item: ET.Element, *names: str) -> str | None:
    for name in names:
        element = item.find(name)
        if element is not None and element.text:
            return element.text.strip()
    return None


def converted_monthly(deposit: pd.Series, monthly: pd.Series, rate: float = 0.05) -> pd.Series:
    return monthly + deposit * rate / 12


def region_catalog() -> dict[str, dict[str, str]]:
    with REGION_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    catalog = {row["region_id"]: row for row in rows}
    # 개편 후 구 자료를 합칠 부모 시는 개편 전 행의 이름·시도를 사용한다.
    for prefix, parent_id in CITY_PARENT.items():
        catalog.setdefault(parent_id, catalog[parent_id])
    return catalog


def canonical_region(region_id: str) -> str | None:
    for prefix, parent_id in CITY_PARENT.items():
        if region_id.startswith(prefix):
            return parent_id
    if region_id.startswith(INCHEON_REORG_PREFIXES):
        # 7월 인천 신규 구는 이전 11개월의 구 경계와 일대일 대응이 아니므로 지역 순위에서 제외한다.
        return None
    return region_id


def file_month(path: Path) -> str | None:
    match = re.search(r"_(\d{6})\.xml$", path.name)
    return match.group(1) if match else None


def valid_for_month(region: dict[str, str], month: str) -> bool:
    return region["valid_from"] <= month <= region["valid_to"]


def parse_private_xml(catalog: dict[str, dict[str, str]]) -> tuple[pd.DataFrame, dict]:
    rows: list[dict] = []
    skipped = Counter()
    files_seen = 0
    for xml_path in sorted(RAW_DIR.glob("*/*.xml")):
        region_id = xml_path.parent.name
        month_from_path = file_month(xml_path)
        region = catalog.get(region_id)
        if not region or not month_from_path or not valid_for_month(region, month_from_path):
            skipped["out_of_scope_file"] += 1
            continue
        files_seen += 1
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            skipped["malformed_xml"] += 1
            continue
        kind = "민간 오피스텔" if xml_path.name.startswith("officetel_") else "민간 연립다세대"
        source_url = "https://www.data.go.kr/data/15126475/openapi.do" if kind.endswith("오피스텔") else "https://www.data.go.kr/data/15126473/openapi.do"
        for item in root.findall(".//item"):
            area = numeric(text_of(item, "전용면적", "excluUseAr"))
            deposit = numeric(text_of(item, "보증금액", "deposit"))
            monthly = numeric(text_of(item, "월세금액", "monthlyRent"))
            if None in (area, deposit, monthly) or not (MIN_AREA <= area <= MAX_AREA):
                skipped["outside_filter_or_missing"] += 1
                continue
            year = text_of(item, "계약년", "dealYear")
            contract_month = text_of(item, "계약월", "dealMonth")
            day = text_of(item, "계약일", "dealDay")
            rows.append({
                "source_region_id": region_id,
                "region_id": canonical_region(region_id),
                "source_region_name": region["region_name"],
                "area_m2": area,
                "deposit": deposit,
                "monthly": monthly,
                "date": f"{year or month_from_path[:4]}-{str(contract_month or month_from_path[4:]).zfill(2)}-{str(day or '').zfill(2)}".strip("-"),
                "kind": kind,
                "source": "국토교통부 전월세 실거래가",
                "url": source_url,
            })
    if not rows:
        raise SystemExit("수도권 민간 전월세 레코드가 없습니다. 수집 완료 여부를 확인하세요.")
    return pd.DataFrame(rows), {"files_seen": files_seen, "skipped": dict(skipped)}


def read_partial_public() -> pd.DataFrame:
    """현재 확보한 LH 공식 공고 범위의 공공임대만 읽는다.

    이 파일은 수도권 전체 공고를 망라하지 않으므로, 값이 없는 지역은 0이 아닌
    '자료 미확보'로 웹에서 다뤄야 한다.
    """
    if not PUBLIC_PATH.exists():
        return pd.DataFrame()
    public = pd.read_csv(PUBLIC_PATH)
    required = {"region_id", "announcement_title", "announcement_date", "area_m2", "deposit_10k", "monthly_10k", "supply_units", "source_url"}
    missing = required - set(public.columns)
    if missing:
        raise SystemExit(f"공공임대 CSV 필수 열 누락: {', '.join(sorted(missing))}")
    public = public[public["area_m2"].between(MIN_AREA, MAX_AREA)].copy()
    public["converted"] = converted_monthly(public["deposit_10k"], public["monthly_10k"])
    return public


def main() -> None:
    catalog = region_catalog()
    private, quality = parse_private_xml(catalog)
    public = read_partial_public()
    private["converted"] = converted_monthly(private.deposit, private.monthly)

    # 인천 개편 신규 구의 7월 수치는 수도권 전체 추세에는 포함하되, 기존 구와 직접 순위 비교는 하지 않는다.
    comparable = private.dropna(subset=["region_id"]).copy()
    summary = comparable.groupby("region_id").agg(
        private_deposit=("deposit", "median"),
        private_monthly=("monthly", "median"),
        converted_rent=("converted", "median"),
        deals=("region_id", "size"),
        months=("date", lambda values: values.str.slice(0, 7).nunique()),
    ).reset_index()

    public_summary = pd.DataFrame()
    if not public.empty:
        public_summary = public.groupby("region_id").agg(
            public_deposit=("deposit_10k", "median"),
            public_monthly=("monthly_10k", "median"),
            public_converted_rent=("converted", "median"),
            supply_units=("supply_units", "sum"),
            notices=("announcement_title", "nunique"),
        )
    areas: list[dict] = []
    for row in summary.itertuples(index=False):
        region = catalog[row.region_id]
        pub = public_summary.loc[row.region_id] if row.region_id in public_summary.index else None
        areas.append({
            "id": row.region_id,
            "name": region["region_name"],
            "sido": region["sido"],
            "private_deposit": round(float(row.private_deposit), 1),
            "private_monthly": round(float(row.private_monthly), 1),
            "converted_rent": round(float(row.converted_rent), 1),
            "deals": int(row.deals),
            "coverage_months": int(row.months),
            "public_deposit": round(float(pub.public_deposit), 1) if pub is not None else None,
            "public_monthly": round(float(pub.public_monthly), 1) if pub is not None else None,
            "public_converted_rent": round(float(pub.public_converted_rent), 1) if pub is not None else None,
            "supply_units": int(pub.supply_units) if pub is not None else None,
            "notices": int(pub.notices) if pub is not None else None,
            "public_data_status": "official_partial" if pub is not None else "not_collected",
        })
    areas.sort(key=lambda area: area["converted_rent"], reverse=True)

    monthly = private.assign(month=private.date.str.slice(0, 7)).groupby("month").converted.median().reset_index()
    private_listings = comparable.sort_values("date", ascending=False).head(1000)
    private_listings = private_listings.assign(area=private_listings.source_region_name)
    public_listings = pd.DataFrame()
    if not public.empty:
        public_listings = public.assign(
            area=public.region_id.map(lambda region_id: catalog[region_id]["region_name"]),
            kind="청년 공공임대",
            deposit=public.deposit_10k,
            monthly=public.monthly_10k,
            date=public.announcement_date,
            source="LH 공식 모집공고",
            url=public.source_url,
        )
    listing_columns = ["region_id", "area", "kind", "area_m2", "deposit", "monthly", "date", "source", "url"]
    listings = pd.concat([private_listings[listing_columns], public_listings[listing_columns]], ignore_index=True) if not public_listings.empty else private_listings[listing_columns]
    output = {
        "meta": {
            "project_name": "수도권 청년 주거 지도",
            "data_mode": "partial_sources",
            "scope": "수도권 · 시·군·구 · 오피스텔·연립다세대 · 전용면적 20~39㎡",
            "period": "2025-08 ~ 2026-07",
            "updated_at": date.today().isoformat(),
            "notice": "민간 전월세는 수도권 12개월 실제 원본입니다. 공공임대는 현재 LH 경기남부 공식 공고 일부만 결합했으므로, 서울·인천 또는 미수집 지역의 공급량을 0으로 해석하거나 수도권 전체 순위를 확정하면 안 됩니다.",
            "incheon_boundary_note": "인천은 2026-07-01 구 개편으로 신규 구의 7월 거래를 전체 추세에는 포함하지만, 기존 구의 12개월 순위에는 직접 합치지 않았습니다.",
        },
        "areas": areas,
        "sources": [
            {"name": "오피스텔 전월세 실거래가", "organization": "국토교통부", "description": "수도권 시·군·구별 오피스텔 전월세 실거래가", "url": "https://www.data.go.kr/data/15126475/openapi.do"},
            {"name": "연립다세대 전월세 실거래가", "organization": "국토교통부", "description": "수도권 시·군·구별 연립다세대 전월세 실거래가", "url": "https://www.data.go.kr/data/15126473/openapi.do"},
            {"name": "법정동코드", "organization": "행정표준코드관리시스템", "description": "수집 대상 시·군·구 코드와 2026년 7월 개편 시점 관리", "url": "https://www.code.go.kr/stdcode/regCodeL.do"},
            {"name": "청년 매입임대 모집공고", "organization": "LH", "description": "현재 확보한 경기남부 공식 공고 일부(공급량 전체가 아님)", "url": "https://apply.lh.or.kr"},
        ],
        "monthly_trend": [{"month": row.month, "rent": round(float(row.converted), 1)} for row in monthly.itertuples(index=False)],
        "listings": listings.sort_values("date", ascending=False).head(1200).to_dict(orient="records"),
    }
    quality.update({
        "record_count": int(len(private)),
        "comparable_record_count": int(len(comparable)),
        "non_comparable_incheon_reorg_records": int(private.region_id.isna().sum()),
        "area_count": int(len(areas)),
        "public_record_count": int(len(public)),
        "public_regions_with_official_records": int(public.region_id.nunique()) if not public.empty else 0,
        "periods_seen": sorted(private.date.str.slice(0, 7).dropna().unique().tolist()),
    })
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    QUALITY_OUTPUT.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: areas={len(areas)}, records={len(private):,}")
    print(f"wrote {QUALITY_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
