"""경기데이터드림 Sheet 조회 API(searchSheetData.do)를 직접 호출해
1인가구_경기데이터드림_데이터셋_목록.md 에 정리된 나머지 데이터셋을 받아온다.

로그인 없이도 데이터셋 상세페이지를 한 번 GET하면 세션 쿠키 + CSRF 토큰을
얻을 수 있고, 그 값으로 searchSheetData.do를 POST하면 전체 행을 JSON으로
받을 수 있다(별도 인증키 불필요, Open API 샘플 5건 제한과 무관).

경기도 전체 원본은 data/raw/gg_data_dream_csv/에, 시흥시 행만 걸러
data/processed/siheung_infra/에 저장한다(로컬 필터링이라 데이터셋마다
주소 컬럼명이 달라도 안전하게 동작한다).

사용 예:
  python scripts/fetch_siheung_from_api.py
"""
from __future__ import annotations

import csv
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "gg_data_dream_csv"
OUT_DIR = ROOT / "data" / "processed" / "siheung_infra"
KEYWORD = "시흥시"
BASE = "https://data.gg.go.kr"
PAGE_SIZE = 3000

# (파일명 slug, infId) — 1인가구/경기데이터드림_데이터셋_목록.md 기준,
# 이미 받은 5개(fitness/bathhouse/laundry/karaoke/sports_facility) 제외.
DATASETS = [
    ("golf_range", "713RY08G3A3TSH85H2DT899077"),
    ("century_store", "6XGZIF1N2RBQF7DTIIU831075013"),
    ("camping", "6243I631A7C7L7M0JR1B21715119"),
    ("city_park", "4QS969262YM8X8SU2HT912679931"),
    ("playground", "I6Y5W00421151P0RPW7Y12521845"),
    ("culture_festival", "65YE99614B6X51X6084912706650"),
    ("library", "8OA7QE89M021HP3G100712792133"),
    ("shared_facility_rental", "0MQ4S7NZHRSP1QBGP8M236822019"),
    ("convenience_store", "CPMB3F3D1SDTN6V7LTWE13467194"),
    ("traditional_market", "59V8JWVM94BJ858NH0HV12692968"),
    ("local_food_store", "SUNJ3MPX6Z6P99HX374S11661850"),
    ("pharmacy", "374OQ18937P0828Q981618796"),
    ("mental_health_center", "DR5A9PI77Q1831V975Q1889283"),
    ("animal_hospital", "Y5M0CVS8XM2C821G09A813809578"),
    ("safe_parcel_locker", "97BM2OZKIYD2GMWJZ0UI26817441"),
    ("cctv", "VIPK0N53968Q7DV5TT2312643570"),
    ("security_light", "VEY71398U2941WM4E7PV21507518"),
    ("tourist_spot", "6D55H4P620YMVJ36G63F21726511"),
    ("gg_attraction", "BM4IHHEFJAEFIJMM6SC031171354"),
    ("health_center", "302402102AS0TA1SY80R404746"),
    ("health_checkup_agency", "KACQ2WNP7ERK8JYMIXMM28063004"),
    ("nhis_branch", "FP2JAJCK569IFNIGRZI524893778"),
    ("addiction_center", "VP6N5SJ9BHMEQ9RTWGAY15043133"),
    ("lunchbox_manufacturer", "BNY245C2R3NE25DRJT3X14569434"),
    ("instant_food_processing", "NAFYRSLLJHWP89BVCBOD27934841"),
    ("delivery_express_store", "WYR67CWJMLW6JZRWKE0D32401928"),
    ("pet_store", "99L24Y065OQ36TTGVENX502240"),
    ("pet_convenience_facility", "UX2OPRPXURITBZQ3L7W732294628"),
    ("performance_hall", "N4LY6H5VP5047641W5DQ1742165"),
    ("culture_facility", "UFGNHHHFT8SWMJ0WK4J831124989"),
]


def make_opener() -> urllib.request.OpenerDirector:
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    return opener


def get_csrf(opener: urllib.request.OpenerDirector, inf_id: str) -> str:
    url = f"{BASE}/portal/data/service/selectServicePage.do?infId={inf_id}&infSeq=1"
    with opener.open(url, timeout=20) as resp:
        html = resp.read().decode("utf-8")
    m = re.search(r'name="_csrf" content="([^"]+)"', html)
    if not m:
        raise RuntimeError("CSRF 토큰을 찾지 못했습니다")
    return m.group(1)


def fetch_page(opener, csrf: str, inf_id: str, page: int, rows: int) -> dict:
    body = urllib.parse.urlencode({
        "_csrf": csrf,
        "CSRFToken": csrf,
        "rows": str(rows),
        "infId": inf_id,
        "infSeq": "1",
        "downloadType": "",
        "loc": "",
        "orderby": "",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/portal/data/sheet/searchSheetData.do?page={page}",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        method="POST",
    )
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            with opener.open(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
            return json.loads(text)
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{inf_id} page={page} 요청 실패: {last_err}")


def fetch_all_rows(opener, inf_id: str) -> list[dict]:
    csrf = get_csrf(opener, inf_id)
    first = fetch_page(opener, csrf, inf_id, 1, 1)
    total = first.get("count", 0)
    if total == 0:
        return []

    rows: list[dict] = []
    page = 1
    while len(rows) < total:
        j = fetch_page(opener, csrf, inf_id, page, PAGE_SIZE)
        chunk = j.get("data", [])
        if not chunk:
            break
        rows.extend(chunk)
        page += 1
        time.sleep(0.3)
    return rows


def write_csv(path: Path, rows: list[dict], headers: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if headers is None:
        headers = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    headers.append(key)

    if not headers:
        path.write_text("", encoding="utf-8-sig")
        return

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    opener = make_opener()
    print(f"{'파일':<28} {'전체 행':>10} {'시흥시 행':>10}")
    for slug, inf_id in DATASETS:
        try:
            rows = fetch_all_rows(opener, inf_id)
        except Exception as e:  # noqa: BLE001
            print(f"{slug:<28} FAILED: {e}")
            continue

        write_csv(RAW_DIR / f"{slug}.csv", rows)
        matched = [
            row for row in rows
            if any(KEYWORD in str(v) for v in row.values() if v is not None)
        ]
        headers = list(rows[0].keys()) if rows else None
        write_csv(OUT_DIR / f"{slug}.csv", matched, headers=headers)
        print(f"{slug:<28} {len(rows):>10} {len(matched):>10}")


if __name__ == "__main__":
    main()
