from __future__ import annotations

import csv
import json
import math
import os
import re
from statistics import median
from pathlib import Path

import requests
from fastapi import FastAPI
from fastapi import Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_PATH = ROOT / "data" / "processed" / "dashboard.json"
CAPITAL_PREVIEW_PATH = ROOT / "data" / "processed" / "capital_private_preview.json"
INFRASTRUCTURE_PATH = ROOT / "data" / "processed" / "siheung_infrastructure.json"
LEGAL_DONG_RENT_PATH = ROOT / "data" / "processed" / "siheung_legal_dong_rent.json"
SUBWAY_PATH = ROOT / "데이터" / "siheung_data" / "siheung_지하철역.csv"
TRANSPORT_CATEGORY_IDS = {"subway", "bus", "bus_stop"}

# 로컬 .env는 개발 편의를 위해 읽고, Cloudtype에서는 환경변수를 그대로 사용한다.
load_dotenv(ROOT / ".env")

app = FastAPI(title="시흥 청년 주거 지도", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def load_dashboard(scope: str = "capital") -> dict:
    path = CAPITAL_PREVIEW_PATH if scope == "capital" else DATA_PATH
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_legal_dong_rent() -> dict:
    with LEGAL_DONG_RENT_PATH.open(encoding="utf-8") as file:
        return json.load(file)


@app.get("/health")
def health() -> dict[str, str]:
    data_mode = load_dashboard("capital").get("meta", {}).get("data_mode", "unknown")
    return {"status": "ok", "data_mode": data_mode}


@app.get("/api/dashboard")
def dashboard(scope: str = "capital") -> JSONResponse:
    if scope not in {"siheung", "capital"}:
        return JSONResponse({"detail": "scope는 siheung 또는 capital만 가능합니다."}, status_code=400)
    # 브라우저가 매번 최신 정제본을 읽도록 캐시를 짧게 설정합니다.
    try:
        payload = load_dashboard(scope)
    except FileNotFoundError:
        return JSONResponse({"detail": "수도권 미리보기 데이터가 아직 생성되지 않았습니다."}, status_code=404)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@app.get("/api/housing-costs")
def housing_costs() -> JSONResponse:
    """시흥시 전월세 실거래 요약과 화면용 대표 거래 범위를 반환합니다."""
    try:
        payload = load_dashboard("capital")
    except FileNotFoundError:
        return JSONResponse({"detail": "전월세 실거래 데이터가 없습니다."}, status_code=404)

    area = next((item for item in payload.get("areas", []) if item.get("id") == "gyeonggi-siheung"), None)
    if area is None:
        return JSONResponse({"detail": "시흥시 전월세 실거래 요약을 찾지 못했습니다."}, status_code=404)

    private = [
        item for item in payload.get("listings", [])
        if item.get("region_id") == "gyeonggi-siheung" and str(item.get("kind", "")).startswith("민간")
    ]
    monthly = [item for item in private if float(item.get("monthly") or 0) > 0]
    jeonse = [item for item in private if float(item.get("monthly") or 0) == 0]

    def sample_range(items: list[dict], key: str) -> dict[str, float | int | None]:
        values = [float(item[key]) for item in items if item.get(key) is not None]
        if not values:
            return {"min": None, "median": None, "max": None}
        return {
            "min": round(min(values), 1),
            "median": round(float(median(values)), 1),
            "max": round(max(values), 1),
        }

    result = {
        "source": "국토교통부 전월세 실거래가",
        "period": payload.get("meta", {}).get("period"),
        "scope": payload.get("meta", {}).get("scope"),
        "deals": area.get("deals"),
        "coverage_months": area.get("coverage_months"),
        "monthly": {
            "median_deposit": area.get("private_deposit"),
            "median_rent": area.get("private_monthly"),
            "converted_rent": area.get("converted_rent"),
            "sample_count": len(monthly),
            "deposit_range": sample_range(monthly, "deposit"),
            "rent_range": sample_range(monthly, "monthly"),
        },
        "jeonse": {
            "sample_count": len(jeonse),
            "deposit_range": sample_range(jeonse, "deposit"),
        },
        "note": "시흥시 전체 거래 요약이며 동별 추천 점수와는 별도로 제공됩니다.",
    }
    return JSONResponse(result, headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/legal-dong-rent")
def legal_dong_rent(
    housing_type: str = Query(default="monthly", pattern="^(monthly|jeonse)$"),
    deposit_min: float | None = Query(default=None, ge=0),
    deposit_max: float | None = Query(default=None, ge=0),
    monthly_min: float | None = Query(default=None, ge=0),
    monthly_max: float | None = Query(default=None, ge=0),
) -> JSONResponse:
    """법정동별 전월세 집계와 사용자가 선택한 예산 범위의 과거 실거래 건수를 반환합니다."""
    if not LEGAL_DONG_RENT_PATH.exists():
        return JSONResponse({"detail": "법정동별 전월세 집계 데이터가 없습니다."}, status_code=404)
    if deposit_min is not None and deposit_max is not None and deposit_min > deposit_max:
        return JSONResponse({"detail": "최소 보증금은 최대 보증금보다 클 수 없습니다."}, status_code=400)
    if monthly_min is not None and monthly_max is not None and monthly_min > monthly_max:
        return JSONResponse({"detail": "최소 월세는 최대 월세보다 클 수 없습니다."}, status_code=400)

    payload = load_legal_dong_rent()
    records = payload.get("records", [])
    records_by_dong: dict[str, list[dict]] = {}
    for item in records:
        is_monthly = float(item.get("monthly") or 0) > 0
        if (housing_type == "monthly") != is_monthly:
            continue
        records_by_dong.setdefault(str(item.get("dong") or ""), []).append(item)

    result_areas = []
    for area in payload.get("areas", []):
        candidates = records_by_dong.get(area.get("name", ""), [])
        matched = []
        for item in candidates:
            deposit = float(item.get("deposit") or 0)
            monthly = float(item.get("monthly") or 0)
            if deposit_min is not None and deposit < deposit_min:
                continue
            if deposit_max is not None and deposit > deposit_max:
                continue
            if housing_type == "monthly" and monthly_min is not None and monthly < monthly_min:
                continue
            if housing_type == "monthly" and monthly_max is not None and monthly > monthly_max:
                continue
            matched.append(item)
        result_areas.append({
            **area,
            "budget": {
                "housing_type": housing_type,
                "eligible_count": len(candidates),
                "matched_count": len(matched),
                "match_rate": round(len(matched) / len(candidates) * 100, 1) if candidates else None,
            },
        })

    return JSONResponse({
        "meta": payload.get("meta", {}),
        "filters": {
            "housing_type": housing_type,
            "deposit_min": deposit_min,
            "deposit_max": deposit_max,
            "monthly_min": monthly_min if housing_type == "monthly" else None,
            "monthly_max": monthly_max if housing_type == "monthly" else None,
        },
        "areas": result_areas,
    }, headers={"Cache-Control": "no-store"})


@app.get("/api/infrastructure")
def infrastructure() -> JSONResponse:
    if not INFRASTRUCTURE_PATH.exists():
        return JSONResponse({"detail": "생활 인프라 데이터가 아직 생성되지 않았습니다."}, status_code=404)
    with INFRASTRUCTURE_PATH.open(encoding="utf-8") as file:
        payload = json.load(file)
    counts_by_area = {area["id"]: {} for area in payload.get("areas", [])}
    for facility in payload.get("facilities", []):
        area_counts = counts_by_area.get(facility.get("area_id"))
        if area_counts is None:
            continue
        category = facility.get("category")
        if category in TRANSPORT_CATEGORY_IDS:
            continue
        area_counts[category] = area_counts.get(category, 0) + 1
    for area in payload.get("areas", []):
        area["counts"] = counts_by_area.get(area["id"], {})
        area["facility_total"] = sum(area["counts"].values())
    payload["categories"] = [category for category in payload.get("categories", []) if category.get("id") not in TRANSPORT_CATEGORY_IDS]
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def normalized_address(value: str) -> str:
    normalized = re.sub(r"[^0-9가-힣]", "", value.lower())
    return normalized.replace("경기시흥시", "경기도시흥시")


def address_core(value: str) -> str:
    """주소 데이터에 덧붙은 법정동 괄호 표기를 제외한 정확한 주소 본문을 반환한다."""
    without_parenthetical = re.sub(r"\([^)]*\)", "", value)
    return normalized_address(without_parenthetical)


def local_geocode(address: str) -> dict | None:
    query = address_core(address)
    if not query:
        return None
    with INFRASTRUCTURE_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    candidates = []
    for facility in data.get("facilities", []):
        if facility.get("lat") is None or facility.get("lng") is None:
            continue
        facility_address = facility.get("address", "")
        normalized = address_core(facility_address)
        # 괄호 속 법정동 표기는 무시하되 도로명·건물번호 본문은 완전히 같은 주소만 허용한다.
        if query != normalized:
            continue
        candidates.append((len(normalized), facility))
    if not candidates:
        return None
    facility = max(candidates, key=lambda item: item[0])[1]
    return {
        "address": address.strip(),
        "lat": facility["lat"],
        "lng": facility["lng"],
        "area_id": facility.get("area_id"),
        "source": "local-facility-address",
    }


@app.get("/api/geocode")
def geocode(
    address: str = Query(min_length=2, max_length=160),
    x_kakao_rest_key: str = Header(default="", max_length=128),
) -> JSONResponse:
    kakao_key = x_kakao_rest_key.strip() or os.getenv("KAKAO_REST_API_KEY", "").strip()
    if kakao_key:
        try:
            response = requests.get(
                "https://dapi.kakao.com/v2/local/search/address.json",
                headers={"Authorization": f"KakaoAK {kakao_key}"},
                params={"query": address},
                timeout=5,
            )
            response.raise_for_status()
            documents = response.json().get("documents", [])
            if documents:
                result = documents[0]
                road = result.get("road_address") or {}
                parcel = result.get("address") or {}
                region_2depth = parcel.get("region_2depth_name") or road.get("region_2depth_name") or ""
                resolved_address = road.get("address_name") or parcel.get("address_name") or result.get("address_name") or address
                if region_2depth != "시흥시" and "시흥시" not in resolved_address:
                    raise HTTPException(status_code=422, detail="시흥시 내 주소를 입력해 주세요.")
                area_name = parcel.get("region_3depth_name") or ""
                with INFRASTRUCTURE_PATH.open(encoding="utf-8") as file:
                    data = json.load(file)
                area = next((item for item in data.get("areas", []) if item.get("name") == area_name), None)
                return JSONResponse({
                    "address": resolved_address,
                    "lat": float(result["y"]),
                    "lng": float(result["x"]),
                    "area_id": area.get("id") if area else None,
                    "source": "kakao-address",
                })
        except HTTPException:
            raise
        except (requests.RequestException, ValueError, KeyError):
            pass
    fallback = local_geocode(address)
    if fallback:
        return JSONResponse(fallback)
    raise HTTPException(
        status_code=404,
        detail="선택한 주소의 좌표를 찾지 못했습니다. 카카오 REST API 키 연결 상태를 확인해 주세요.",
    )


def kakao_local_search(endpoint: str, kakao_key: str, params: dict) -> list[dict]:
    response = requests.get(
        f"https://dapi.kakao.com/v2/local/search/{endpoint}.json",
        headers={"Authorization": f"KakaoAK {kakao_key}"},
        params=params,
        timeout=7,
    )
    response.raise_for_status()
    return response.json().get("documents", [])


def transport_item(document: dict, transport_type: str) -> dict:
    distance = max(0, int(float(document.get("distance") or 0)))
    walk_minutes = max(1, (distance + 66) // 67)
    if walk_minutes <= 10:
        bucket = "within_10"
    elif walk_minutes <= 20:
        bucket = "within_20"
    elif walk_minutes <= 30:
        bucket = "within_30"
    else:
        bucket = "over_30"
    return {
        "type": transport_type,
        "name": document.get("place_name") or "이름 미확인",
        "address": document.get("road_address_name") or document.get("address_name") or "",
        "lat": float(document["y"]),
        "lng": float(document["x"]),
        "distance_m": distance,
        "walk_minutes": walk_minutes,
        "bucket": bucket,
        "place_url": document.get("place_url") or "",
    }


def distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    earth_radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return round(earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def local_subway_items(lat: float, lng: float) -> list[dict]:
    """카카오 키가 없어도 프로젝트의 시흥시 지하철역 좌표로 주변 역을 계산한다."""
    if not SUBWAY_PATH.exists():
        return []
    items = []
    with SUBWAY_PATH.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            try:
                station_lat = float(row["y"])
                station_lng = float(row["x"])
            except (KeyError, TypeError, ValueError):
                continue
            distance = distance_meters(lat, lng, station_lat, station_lng)
            if distance > 20_000:
                continue
            items.append(transport_item({
                "place_name": row.get("place_name"),
                "road_address_name": row.get("road_address_name"),
                "address_name": row.get("address_name"),
                "x": station_lng,
                "y": station_lat,
                "distance": distance,
                "place_url": row.get("place_url"),
            }, "subway"))
    return sorted(items, key=lambda item: item["distance_m"])


@app.get("/api/transport")
def transport(
    lat: float = Query(ge=36.5, le=38.5),
    lng: float = Query(ge=125.0, le=128.5),
    x_kakao_rest_key: str = Header(default="", max_length=128),
) -> JSONResponse:
    """주소 좌표 주변 교통시설을 행정동 경계와 무관하게 조회한다."""
    kakao_key = x_kakao_rest_key.strip() or os.getenv("KAKAO_REST_API_KEY", "").strip()
    local_subways = local_subway_items(lat, lng)
    if not kakao_key:
        return JSONResponse({
            "items": local_subways,
            "warning": "지하철역은 프로젝트의 시흥시 역 좌표 데이터로 조회했습니다. 버스정류장 조회에는 카카오 REST API 키가 필요합니다.",
            "method": "주소 기준 직선거리 ÷ 분당 67m로 도보시간을 추정합니다.",
        })
    common = {"x": lng, "y": lat, "radius": 20000, "sort": "distance", "size": 15}
    try:
        subway_documents = kakao_local_search(
            "category", kakao_key, {**common, "category_group_code": "SW8"}
        )
        # 카카오 로컬에는 버스정류장 전용 분류 코드가 없어 키워드 검색으로 보완한다.
        bus_documents = kakao_local_search(
            "keyword", kakao_key, {**common, "query": "버스정류장"}
        )
        items = local_subways or [transport_item(item, "subway") for item in subway_documents]
        items.extend(transport_item(item, "bus") for item in bus_documents)
        unique = {}
        for item in items:
            unique[(item["type"], item["name"], item["lat"], item["lng"])] = item
        return JSONResponse({
            "items": sorted(unique.values(), key=lambda item: item["distance_m"]),
            "warning": "버스정류장은 카카오 장소 검색 기반의 참고 정보이며 노선 수는 포함하지 않습니다.",
            "method": "주소 기준 직선거리 ÷ 분당 67m로 도보시간을 추정합니다.",
        })
    except (requests.RequestException, ValueError, KeyError):
        return JSONResponse(
            {"detail": "주변 교통정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."},
            status_code=502,
        )


@app.get("/api/config")
def client_config() -> dict[str, str | bool]:
    # Key ID는 지도 JavaScript를 불러오기 위한 공개 식별자다. Key Secret은 절대 반환하지 않는다.
    return {
        "naver_maps_key_id": os.getenv("NAVER_MAPS_KEY_ID", ""),
        "kakao_rest_ready": bool(os.getenv("KAKAO_REST_API_KEY", "").strip()),
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
