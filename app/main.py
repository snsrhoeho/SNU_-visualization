from __future__ import annotations

import json
import math
import os
import re
import secrets
from statistics import median
from pathlib import Path

import requests
from fastapi import Cookie, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_PATH = ROOT / "data" / "processed" / "dashboard.json"
CAPITAL_PREVIEW_PATH = ROOT / "data" / "processed" / "capital_private_preview.json"
INFRASTRUCTURE_PATH = ROOT / "data" / "processed" / "siheung_infrastructure.json"
TRANSPORT_CATEGORY_IDS = {"subway", "bus", "bus_stop"}

# 로컬 .env는 개발 편의를 위해 읽고, Cloudtype에서는 환경변수를 그대로 사용한다.
load_dotenv(ROOT / ".env")

app = FastAPI(title="시흥 청년 주거 지도", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
chat_sessions: dict[str, tuple[str, str]] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    context: dict = Field(default_factory=dict)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=30, max_length=10_000)


class TeamCodeLoginRequest(BaseModel):
    code: str = Field(min_length=4, max_length=200)


def load_dashboard(scope: str = "capital") -> dict:
    path = CAPITAL_PREVIEW_PATH if scope == "capital" else DATA_PATH
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_infrastructure() -> dict:
    with INFRASTRUCTURE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """두 좌표의 직선거리(m). 주소 생활권 결과의 공통 기준이다."""
    earth_radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return round(earth_radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)))


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
    return JSONResponse(payload, headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/infrastructure")
def infrastructure() -> JSONResponse:
    if not INFRASTRUCTURE_PATH.exists():
        return JSONResponse({"detail": "생활 인프라 데이터가 아직 생성되지 않았습니다."}, status_code=404)
    with INFRASTRUCTURE_PATH.open(encoding="utf-8") as file:
        payload = json.load(file)
    counts_by_area = {area["id"]: {} for area in payload.get("areas", [])}
    for facility in payload.get("facilities", []):
        area_counts = counts_by_area.get(facility.get("area_id"))
        if area_counts is None or facility.get("category") in TRANSPORT_CATEGORY_IDS:
            continue
        category = facility.get("category")
        area_counts[category] = area_counts.get(category, 0) + 1
    for area in payload.get("areas", []):
        area["counts"] = counts_by_area.get(area["id"], {})
        area["facility_total"] = sum(area["counts"].values())
    payload["categories"] = [item for item in payload.get("categories", []) if item.get("id") not in TRANSPORT_CATEGORY_IDS]
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@app.get("/api/housing-costs")
def housing_costs() -> JSONResponse:
    """시흥시 실제 전월세 거래를 예산 필터 화면용 요약으로 제공한다."""
    try:
        payload = load_dashboard("capital")
    except FileNotFoundError:
        return JSONResponse({"detail": "전월세 실거래 데이터가 없습니다."}, status_code=404)
    area = next((item for item in payload.get("areas", []) if item.get("id") == "gyeonggi-siheung"), None)
    if area is None:
        return JSONResponse({"detail": "시흥시 전월세 실거래 요약을 찾지 못했습니다."}, status_code=404)
    private = [item for item in payload.get("listings", []) if item.get("region_id") == "gyeonggi-siheung" and str(item.get("kind", "")).startswith("민간")]
    monthly = [item for item in private if float(item.get("monthly") or 0) > 0]
    jeonse = [item for item in private if float(item.get("monthly") or 0) == 0]

    def value_range(items: list[dict], key: str) -> dict[str, float | None]:
        values = [float(item[key]) for item in items if item.get(key) is not None]
        if not values:
            return {"min": None, "median": None, "max": None}
        return {"min": round(min(values), 1), "median": round(float(median(values)), 1), "max": round(max(values), 1)}

    return JSONResponse({
        "source": "국토교통부 전월세 실거래가",
        "period": payload.get("meta", {}).get("period"),
        "deals": area.get("deals"),
        "coverage_months": area.get("coverage_months"),
        "monthly": {"median_deposit": area.get("private_deposit"), "median_rent": area.get("private_monthly"), "converted_rent": area.get("converted_rent"), "sample_count": len(monthly), "deposit_range": value_range(monthly, "deposit"), "rent_range": value_range(monthly, "monthly")},
        "jeonse": {"sample_count": len(jeonse), "deposit_range": value_range(jeonse, "deposit")},
        "note": "시흥시 전체의 실제 거래 요약입니다. 법정동별 추천 점수와는 별도로 보여줍니다.",
    }, headers={"Cache-Control": "public, max-age=300"})


def normalized_address(value: str) -> str:
    return re.sub(r"[^0-9가-힣]", "", value.lower()).replace("경기시흥시", "경기도시흥시")


def local_geocode(address: str) -> dict | None:
    """카카오 키가 없어도 수집 시설과 정확히 같은 주소는 로컬 좌표를 돌려준다."""
    query = normalized_address(re.sub(r"\([^)]*\)", "", address))
    if not query:
        return None
    candidates = [facility for facility in load_infrastructure().get("facilities", []) if facility.get("lat") is not None and facility.get("lng") is not None and normalized_address(re.sub(r"\([^)]*\)", "", facility.get("address", ""))) == query]
    if not candidates:
        return None
    facility = candidates[0]
    return {"address": address.strip(), "lat": facility["lat"], "lng": facility["lng"], "area_id": facility.get("area_id"), "source": "local-facility-address"}


@app.get("/api/geocode")
def geocode(address: str = Query(min_length=2, max_length=160), x_kakao_rest_key: str = Header(default="", max_length=128)) -> JSONResponse:
    """카카오 주소 검색을 우선 사용하고, 키가 없으면 로컬 시설 주소로 제한적으로 보완한다."""
    kakao_key = x_kakao_rest_key.strip() or os.getenv("KAKAO_REST_API_KEY", "").strip()
    if kakao_key:
        try:
            response = requests.get("https://dapi.kakao.com/v2/local/search/address.json", headers={"Authorization": f"KakaoAK {kakao_key}"}, params={"query": address}, timeout=5)
            response.raise_for_status()
            documents = response.json().get("documents", [])
            if documents:
                result = documents[0]
                road, parcel = result.get("road_address") or {}, result.get("address") or {}
                resolved = road.get("address_name") or parcel.get("address_name") or result.get("address_name") or address
                if "시흥시" not in resolved:
                    raise HTTPException(status_code=422, detail="시흥시 내 주소를 입력해 주세요.")
                area_name = parcel.get("region_3depth_name") or ""
                area = next((item for item in load_infrastructure().get("areas", []) if item.get("name") == area_name), None)
                return JSONResponse({"address": resolved, "lat": float(result["y"]), "lng": float(result["x"]), "area_id": area.get("id") if area else None, "source": "kakao-address"})
        except HTTPException:
            raise
        except (requests.RequestException, ValueError, KeyError):
            pass
    fallback = local_geocode(address)
    if fallback:
        return JSONResponse(fallback)
    raise HTTPException(status_code=404, detail="주소 좌표를 찾지 못했습니다. 카카오 REST API 키를 연결하거나 시설명과 동일한 주소를 입력해 주세요.")


@app.get("/api/nearby-facilities")
def nearby_facilities(lat: float = Query(ge=36.5, le=38.5), lng: float = Query(ge=125.0, le=128.5), radius: int = Query(default=800, ge=200, le=2000), categories: str = Query(default="")) -> JSONResponse:
    selected = {item.strip() for item in categories.split(",") if item.strip()}
    items = []
    for facility in load_infrastructure().get("facilities", []):
        if selected and facility.get("category") not in selected:
            continue
        if facility.get("lat") is None or facility.get("lng") is None or facility.get("map_visible") is False:
            continue
        distance = distance_meters(lat, lng, float(facility["lat"]), float(facility["lng"]))
        if distance <= radius:
            items.append({**facility, "distance_m": distance})
    items.sort(key=lambda item: item["distance_m"])
    return JSONResponse({"items": items[:120], "radius": radius, "method": "주소 좌표 기준 직선거리"}, headers={"Cache-Control": "no-store"})


@app.get("/api/config")
def client_config() -> dict[str, str | bool]:
    # Key ID는 지도 JavaScript를 불러오기 위한 공개 식별자다. Key Secret은 절대 반환하지 않는다.
    return {
        "naver_maps_key_id": os.getenv("NAVER_MAPS_KEY_ID", ""),
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "kakao_rest_ready": bool(os.getenv("KAKAO_REST_API_KEY", "").strip()),
    }


def allowed_chat_emails() -> set[str]:
    return {email.strip().lower() for email in os.getenv("ALLOWED_CHAT_EMAILS", "").split(",") if email.strip()}


def current_chat_user(chat_session: str | None, page_token: str | None) -> str | None:
    session = chat_sessions.get(chat_session or "")
    if not session or not page_token:
        return None
    user, issued_page_token = session
    return user if secrets.compare_digest(issued_page_token, page_token) else None


def is_relevant_chat_question(message: str) -> bool:
    """생활 인프라 추천과 무관한 낱말은 모델 호출 전에 차단한다."""
    compact = re.sub(r"\s+", "", message.lower())
    if len(compact) < 2:
        return False
    terms = {
        "동네", "지역", "생활", "인프라", "시설", "추천", "순위", "비교", "지도", "조건", "도보", "거리",
        "살기", "이사", "주거", "주변", "여기", "어디", "1위", "top", "카페", "음식", "식당", "맛집",
        "편의점", "병원", "약국", "공원", "마트", "지하철", "역", "세탁", "러닝", "운동", "안전",
        "cctv", "반려", "동물", "목욕", "놀이터", "보건", "검진", "공연", "노래", "택배",
    }
    try:
        infrastructure_data = load_infrastructure()
        terms.update(area["name"].lower() for area in infrastructure_data.get("areas", []))
        terms.update(category["label"].lower() for category in infrastructure_data.get("categories", []))
    except (FileNotFoundError, KeyError):
        pass
    return any(term in compact for term in terms)


def create_chat_session(user: str, page_token: str | None) -> JSONResponse:
    if not page_token:
        return JSONResponse({"detail": "페이지 인증 정보를 확인하지 못했습니다. 새로고침 후 다시 시도해 주세요."}, status_code=400)
    session_id = secrets.token_urlsafe(32)
    chat_sessions[session_id] = (user, page_token)
    response = JSONResponse({"authenticated": True, "email": user})
    response.set_cookie(
        "chat_session",
        session_id,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return response


@app.get("/api/auth/status")
def auth_status(
    chat_session: str | None = Cookie(default=None),
    x_chat_page_token: str | None = Header(default=None),
) -> JSONResponse:
    email = current_chat_user(chat_session, x_chat_page_token)
    response = JSONResponse({"authenticated": bool(email), "email": email or ""})
    if chat_session and not email:
        chat_sessions.pop(chat_session, None)
        response.delete_cookie("chat_session")
    return response


@app.post("/api/auth/google")
def google_login(payload: GoogleLoginRequest, x_chat_page_token: str | None = Header(default=None)) -> JSONResponse:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        return JSONResponse({"detail": "GOOGLE_CLIENT_ID가 설정되지 않았습니다."}, status_code=503)
    try:
        token = id_token.verify_oauth2_token(payload.credential, google_requests.Request(), client_id)
        email = str(token.get("email", "")).lower()
        if not token.get("email_verified") or email not in allowed_chat_emails():
            return JSONResponse({"detail": "이 Google 계정은 AI 챗봇 사용 권한이 없습니다."}, status_code=403)
        return create_chat_session(email, x_chat_page_token)
    except ValueError:
        return JSONResponse({"detail": "Google 로그인 토큰을 확인하지 못했습니다."}, status_code=401)


@app.post("/api/auth/team-code")
def team_code_login(payload: TeamCodeLoginRequest, x_chat_page_token: str | None = Header(default=None)) -> JSONResponse:
    expected_code = os.getenv("CHAT_ACCESS_CODE", "").strip()
    if not expected_code:
        return JSONResponse({"detail": "CHAT_ACCESS_CODE가 설정되지 않았습니다."}, status_code=503)
    if not secrets.compare_digest(payload.code.strip(), expected_code):
        return JSONResponse({"detail": "팀 코드가 일치하지 않습니다."}, status_code=401)
    return create_chat_session("team-code-user", x_chat_page_token)


@app.post("/api/auth/logout")
def logout(chat_session: str | None = Cookie(default=None)) -> JSONResponse:
    if chat_session:
        chat_sessions.pop(chat_session, None)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie("chat_session")
    return response


@app.post("/api/chat/suggestions")
def chat_suggestions(payload: ChatRequest, chat_session: str | None = Cookie(default=None), x_chat_page_token: str | None = Header(default=None)) -> JSONResponse:
    if not current_chat_user(chat_session, x_chat_page_token):
        return JSONResponse({"detail": "Google 로그인 또는 팀 코드 인증 후 사용할 수 있습니다."}, status_code=401)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse({"detail": "OPENAI_API_KEY가 설정되지 않았습니다."}, status_code=503)
    context = json.dumps(payload.context, ensure_ascii=False)[:12_000]
    try:
        result = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_CHAT_MODEL", "gpt-5-nano"),
                "reasoning": {"effort": "low"},
                "instructions": "현재 화면 데이터만 보고 사용자가 물어볼 만한 한국어 질문 3개를 만든다. 각 질문은 18자 이내, 질문만 한 줄에 하나씩 출력한다. 마크다운·번호·설명은 금지한다.",
                "input": f"[현재 화면 데이터]\n{context}",
                "max_output_tokens": 400,
            },
            timeout=30,
        )
        result.raise_for_status()
        body = result.json()
        text = "".join(content.get("text", "") for item in body.get("output", []) for content in item.get("content", []) if content.get("type") == "output_text")
        suggestions = [line.strip(" -•0123456789. ") for line in text.splitlines() if line.strip()]
        return JSONResponse({"suggestions": suggestions[:3]})
    except requests.RequestException:
        return JSONResponse({"detail": "질문 제안을 불러오지 못했습니다."}, status_code=502)


@app.post("/api/chat")
def chat(payload: ChatRequest, chat_session: str | None = Cookie(default=None), x_chat_page_token: str | None = Header(default=None)) -> JSONResponse:
    """OpenAI 키는 서버에만 두고, 화면용 요약 데이터만 모델에 전달한다."""
    if not current_chat_user(chat_session, x_chat_page_token):
        return JSONResponse({"detail": "Google 로그인 또는 팀 코드 인증 후 사용할 수 있습니다."}, status_code=401)
    if not is_relevant_chat_question(payload.message):
        return JSONResponse(
            {"detail": "동네·시설·추천 결과와 관련된 질문을 입력해주세요."},
            status_code=422,
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse({"detail": "OPENAI_API_KEY가 설정되지 않았습니다."}, status_code=503)

    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-nano")
    context = json.dumps(payload.context, ensure_ascii=False)[:12_000]
    instructions = """너는 '나혼자 산다' 시흥 생활 인프라 지도 챗봇이다.
사용자에게 한국어로 친근하고 짧게(2~4문장) 답한다.
제공된 데이터 요약에 있는 사실만 사용하고, 없는 시설·거리·통계는 만들지 않는다.
도보 5·10·15분은 실제 길찾기가 아니라 법정동 중심에서 시설 좌표까지의 직선거리 반경(400m·800m·1,200m)임을, 관련 질문이 나오면 분명히 말한다.
의료·부동산·안전의 확정적 조언 대신, 지도와 현장 확인을 권한다.
현재 화면 데이터를 해석하고 추천 이유를 설명하는 데 집중한다."""
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "reasoning": {"effort": "low"},
                "instructions": instructions,
                "input": f"[현재 화면 데이터]\n{context}\n\n[사용자 질문]\n{payload.message}",
                "max_output_tokens": 600,
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        answer = result.get("output_text", "").strip()
        if not answer:
            answer = "".join(
                content.get("text", "")
                for item in result.get("output", [])
                for content in item.get("content", [])
                if content.get("type") == "output_text"
            ).strip()
        if not answer:
            return JSONResponse({"detail": "모델 응답을 읽지 못했습니다."}, status_code=502)
        return JSONResponse({"answer": answer, "model": model})
    except requests.RequestException:
        return JSONResponse({"detail": "AI 응답을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."}, status_code=502)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
