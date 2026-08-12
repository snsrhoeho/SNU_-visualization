from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

import requests
from fastapi import Cookie, FastAPI
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

# 로컬 .env는 개발 편의를 위해 읽고, Cloudtype에서는 환경변수를 그대로 사용한다.
load_dotenv(ROOT / ".env")

app = FastAPI(title="시흥 청년 주거 지도", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
chat_sessions: dict[str, str] = {}


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
    return JSONResponse(payload, headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/config")
def client_config() -> dict[str, str]:
    # Key ID는 지도 JavaScript를 불러오기 위한 공개 식별자다. Key Secret은 절대 반환하지 않는다.
    return {
        "naver_maps_key_id": os.getenv("NAVER_MAPS_KEY_ID", ""),
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    }


def allowed_chat_emails() -> set[str]:
    return {email.strip().lower() for email in os.getenv("ALLOWED_CHAT_EMAILS", "").split(",") if email.strip()}


def current_chat_user(chat_session: str | None) -> str | None:
    return chat_sessions.get(chat_session or "")


def create_chat_session(user: str) -> JSONResponse:
    session_id = secrets.token_urlsafe(32)
    chat_sessions[session_id] = user
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
def auth_status(chat_session: str | None = Cookie(default=None)) -> dict[str, str | bool]:
    email = current_chat_user(chat_session)
    return {"authenticated": bool(email), "email": email or ""}


@app.post("/api/auth/google")
def google_login(payload: GoogleLoginRequest) -> JSONResponse:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        return JSONResponse({"detail": "GOOGLE_CLIENT_ID가 설정되지 않았습니다."}, status_code=503)
    try:
        token = id_token.verify_oauth2_token(payload.credential, google_requests.Request(), client_id)
        email = str(token.get("email", "")).lower()
        if not token.get("email_verified") or email not in allowed_chat_emails():
            return JSONResponse({"detail": "이 Google 계정은 AI 챗봇 사용 권한이 없습니다."}, status_code=403)
        return create_chat_session(email)
    except ValueError:
        return JSONResponse({"detail": "Google 로그인 토큰을 확인하지 못했습니다."}, status_code=401)


@app.post("/api/auth/team-code")
def team_code_login(payload: TeamCodeLoginRequest) -> JSONResponse:
    expected_code = os.getenv("CHAT_ACCESS_CODE", "").strip()
    if not expected_code:
        return JSONResponse({"detail": "CHAT_ACCESS_CODE가 설정되지 않았습니다."}, status_code=503)
    if not secrets.compare_digest(payload.code.strip(), expected_code):
        return JSONResponse({"detail": "팀 코드가 일치하지 않습니다."}, status_code=401)
    return create_chat_session("team-code-user")


@app.post("/api/auth/logout")
def logout(chat_session: str | None = Cookie(default=None)) -> JSONResponse:
    if chat_session:
        chat_sessions.pop(chat_session, None)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie("chat_session")
    return response


@app.post("/api/chat/suggestions")
def chat_suggestions(payload: ChatRequest, chat_session: str | None = Cookie(default=None)) -> JSONResponse:
    if not current_chat_user(chat_session):
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
def chat(payload: ChatRequest, chat_session: str | None = Cookie(default=None)) -> JSONResponse:
    """OpenAI 키는 서버에만 두고, 화면용 요약 데이터만 모델에 전달한다."""
    if not current_chat_user(chat_session):
        return JSONResponse({"detail": "Google 로그인 또는 팀 코드 인증 후 사용할 수 있습니다."}, status_code=401)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse({"detail": "OPENAI_API_KEY가 설정되지 않았습니다."}, status_code=503)

    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-nano")
    context = json.dumps(payload.context, ensure_ascii=False)[:12_000]
    instructions = """너는 '나혼자 산다' 시흥 생활 인프라 지도 챗봇이다.
사용자에게 한국어로 친근하고 짧게(2~4문장) 답한다.
제공된 데이터 요약에 있는 사실만 사용하고, 없는 시설·거리·통계는 만들지 않는다.
도보 5·10·15분은 실제 길찾기가 아니라 시설 수 환산 추정값임을, 관련 질문이 나오면 분명히 말한다.
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
