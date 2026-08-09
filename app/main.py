from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_PATH = ROOT / "data" / "processed" / "life_fit.json"

app = FastAPI(title="나혼자산다", description="시흥시 1인 가구 도시선정 의사결정지원 웹사이트", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def load_data() -> dict:
    with DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nahonja-sanda"}


@app.get("/api/life-fit")
def life_fit() -> JSONResponse:
    return JSONResponse(load_data(), headers={"Cache-Control": "public, max-age=300"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
