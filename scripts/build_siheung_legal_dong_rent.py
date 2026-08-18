"""시흥시 민간 전월세 XML을 법정동 지도용 집계 JSON으로 만든다.

원본 XML의 법정동(umdNm)을 그대로 사용한다. 지도 색상용으로 모든 원본 거래를
브라우저에 보내지 않고, 법정동별 중위값·사분위 범위·표본 수만 JSON으로 만든다.

실행:
  .venv/bin/python scripts/build_siheung_legal_dong_rent.py
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "private_rent"
INFRA_PATH = ROOT / "data" / "processed" / "siheung_infrastructure.json"
OUTPUT = ROOT / "data" / "processed" / "siheung_legal_dong_rent.json"
MIN_AREA, MAX_AREA = 20, 39
CONVERSION_RATE = 0.05
MIN_RELIABLE_SAMPLE = 10


def numeric(value: str | None) -> float | None:
    cleaned = re.sub(r"[^0-9.]", "", str(value or ""))
    return float(cleaned) if cleaned else None


def text_of(item: ET.Element, *names: str) -> str | None:
    for name in names:
        value = item.findtext(name)
        if value and value.strip():
            return value.strip()
    return None


def normalize_dong(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\([^)]*\)", "", value)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized if normalized.endswith("동") else None


def parse_records() -> tuple[pd.DataFrame, dict[str, int]]:
    rows: list[dict] = []
    quality: Counter[str] = Counter()
    for xml_path in sorted(RAW_DIR.glob("*.xml")):
        kind = "오피스텔" if xml_path.name.startswith("officetel_") else "연립다세대"
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            quality["malformed_xml"] += 1
            continue
        for item in root.findall(".//item"):
            area = numeric(text_of(item, "excluUseAr", "전용면적"))
            deposit = numeric(text_of(item, "deposit", "보증금액"))
            monthly = numeric(text_of(item, "monthlyRent", "월세금액"))
            dong = normalize_dong(text_of(item, "umdNm", "법정동"))
            if None in (area, deposit, monthly) or not dong or not MIN_AREA <= area <= MAX_AREA:
                quality["outside_filter_or_missing"] += 1
                continue
            year = text_of(item, "dealYear", "계약년") or ""
            month = text_of(item, "dealMonth", "계약월") or ""
            day = text_of(item, "dealDay", "계약일") or ""
            rows.append({
                "dong": dong,
                "kind": kind,
                "area_m2": area,
                "deposit": deposit,
                "monthly": monthly,
                "converted": monthly + deposit * CONVERSION_RATE / 12,
                "date": f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}".strip("-"),
            })
    if not rows:
        raise SystemExit("필터 조건을 만족하는 시흥시 전월세 XML 거래가 없습니다.")
    return pd.DataFrame(rows), dict(quality)


def price_summary(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"count": 0, "median_deposit": None, "median_rent": None, "median_converted_rent": None, "p25_converted_rent": None, "p75_converted_rent": None, "latest_date": None, "by_type": {}}
    by_type = {
        kind: {"count": int(len(part)), "median_deposit": round(float(part.deposit.median()), 1), "median_rent": round(float(part.monthly.median()), 1)}
        for kind, part in frame.groupby("kind")
    }
    return {
        "count": int(len(frame)),
        "median_deposit": round(float(frame.deposit.median()), 1),
        "median_rent": round(float(frame.monthly.median()), 1),
        "median_converted_rent": round(float(frame.converted.median()), 1),
        "p25_converted_rent": round(float(frame.converted.quantile(.25)), 1),
        "p75_converted_rent": round(float(frame.converted.quantile(.75)), 1),
        "latest_date": str(frame.date.max()),
        "by_type": by_type,
    }


def confidence(count: int) -> str:
    if count >= MIN_RELIABLE_SAMPLE:
        return "sufficient"
    if count:
        return "reference"
    return "missing"


def main() -> None:
    records, quality = parse_records()
    infrastructure = json.loads(INFRA_PATH.read_text(encoding="utf-8"))
    area_names = {area["id"]: area["name"] for area in infrastructure["areas"]}
    known_names = set(area_names.values())
    unknown = sorted(set(records.dong) - known_names)
    mapped = records[records.dong.isin(known_names)].copy()

    areas = []
    for area_id, name in area_names.items():
        subset = mapped[mapped.dong == name]
        monthly = subset[subset.monthly > 0]
        jeonse = subset[subset.monthly == 0]
        areas.append({
            "id": area_id,
            "name": name,
            "all_count": int(len(subset)),
            "monthly": price_summary(monthly),
            "jeonse": price_summary(jeonse),
            "confidence": confidence(len(subset)),
        })

    output = {
        "meta": {
            "scope": "시흥시 법정동 · 민간 오피스텔·연립다세대 · 전용면적 20~39㎡",
            "period": f"{mapped.date.min()} ~ {mapped.date.max()}",
            "source": "국토교통부 전월세 실거래가",
            "conversion_rate": CONVERSION_RATE,
            "minimum_reliable_sample": MIN_RELIABLE_SAMPLE,
            "note": "월세 0원 거래는 전세로 분리했습니다. 법정동별 표본 수가 적으면 가격 비교의 신뢰도가 낮을 수 있습니다.",
            "updated_at": date.today().isoformat(),
        },
        "quality": {
            "raw_filtered_records": int(len(records)),
            "mapped_records": int(len(mapped)),
            "unmapped_records": int(len(records) - len(mapped)),
            "unmapped_dongs": unknown,
            # 건물명·지번까지 완전 동일한 키가 API에 없으므로 자동 제거하지 않는다.
            # 같은 날짜·동·면적·금액 거래는 서로 다른 실제 계약일 수 있다.
            "same_value_rows_for_manual_review": int(records.duplicated(["dong", "kind", "area_m2", "deposit", "monthly", "date"]).sum()),
            **quality,
        },
        "areas": areas,
        # 예산 필터 API가 계산할 최소 원본 항목이다. 주소·건물명은 포함하지 않는다.
        "records": mapped[["dong", "kind", "area_m2", "deposit", "monthly", "date"]].to_dict(orient="records"),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: mapped={len(mapped):,}/{len(records):,}, areas={len(areas)}")
    if unknown:
        print("unmapped legal dongs:", ", ".join(unknown))


if __name__ == "__main__":
    main()
