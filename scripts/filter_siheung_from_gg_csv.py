"""경기데이터드림에서 받은 경기도 전체 CSV(data/raw/gg_data_dream_csv/)에서
시흥시 관련 행만 걸러 data/processed/siheung_infra/에 저장한다.

사용 예:
  python scripts/filter_siheung_from_gg_csv.py
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "gg_data_dream_csv"
OUT_DIR = ROOT / "data" / "processed" / "siheung_infra"
KEYWORD = "시흥시"


def filter_file(src: Path) -> tuple[int, int]:
    with src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if row]

    if not rows:
        return (0, 0)

    header, body = rows[0], rows[1:]
    matched = [row for row in body if any(KEYWORD in cell for cell in row)]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = OUT_DIR / src.name
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(matched)

    return (len(matched), len(body))


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"{RAW_DIR.relative_to(ROOT)} 이 없습니다.")

    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        raise SystemExit(f"{RAW_DIR.relative_to(ROOT)} 에 CSV가 없습니다.")

    print(f"{'파일':<20} {'시흥시 행':>10} {'전체 행':>10}")
    for src in csv_files:
        matched, total = filter_file(src)
        print(f"{src.stem:<20} {matched:>10} {total:>10}")


if __name__ == "__main__":
    main()
