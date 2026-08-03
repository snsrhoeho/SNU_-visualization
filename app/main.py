from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_PATH = ROOT / "data" / "processed" / "dashboard.json"

app = FastAPI(title="시흥 청년 주거 지도", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def load_dashboard() -> dict:
    with DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


@app.get("/health")
def health() -> dict[str, str]:
    data_mode = load_dashboard().get("meta", {}).get("data_mode", "unknown")
    return {"status": "ok", "data_mode": data_mode}


@app.get("/api/dashboard")
def dashboard() -> JSONResponse:
    # 브라우저가 매번 최신 정제본을 읽도록 캐시를 짧게 설정합니다.
    return JSONResponse(load_dashboard(), headers={"Cache-Control": "public, max-age=300"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
