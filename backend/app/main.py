"""한장해결AI API 서버.

POST   /api/analyses        사진 1장 → 202 {id} (판독은 백그라운드)
GET    /api/analyses/{id}   진행 단계·결과 (프론트가 1.5초 간격으로 폴링)
DELETE /api/analyses/{id}   결과 즉시 삭제
GET    /api/health          상태 확인
그 밖의 경로는 frontend/ 정적 파일을 그대로 내보낸다 (같은 도메인이라 CORS 걱정이 없다).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import UnidentifiedImageError

from .config import ROOT, settings
from .imaging import to_jpeg
from .llm import get_provider
from .pipeline.run import PipelineError, analyze
from .schemas import Analysis
from .store import get_store
from .push_api import router as push_router

log = logging.getLogger("hanjang")

app = FastAPI(title="한장해결AI API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins) or ["*"],
                   allow_methods=["*"], allow_headers=["*"])

store = get_store(settings)
provider = get_provider(settings)


def _fail(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def _process(aid: str, jpeg: bytes) -> None:
    """백그라운드 판독. 사진(jpeg)은 이 함수가 끝나면 메모리에서 사라진다."""
    try:
        result = analyze(jpeg, provider, today=settings.today(),
                         on_stage=lambda s: store.update(aid, stage=s), polish=settings.agent_polish)
        store.update(aid, status="done", stage="done", result=result)
    except PipelineError as e:
        store.update(aid, status="failed", error_code=e.code, error_reason=e.reason, error_message=e.message)
    except Exception:  # 로그에는 항목 값을 남기지 않는다
        log.exception("analysis %s failed", aid)
        store.update(aid, status="failed", error_code="LLM_ERROR",
                     error_message="판독 중 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요.")


@app.post("/api/analyses", status_code=202)
async def create_analysis(background: BackgroundTasks, image: UploadFile = File(...)):
    data = await image.read()
    if not data:
        _fail(400, "EMPTY", "사진이 비어 있어요.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        _fail(413, "TOO_LARGE", f"사진이 너무 커요. {settings.max_upload_mb}MB 이하로 올려 주세요.")
    try:
        jpeg = to_jpeg(data)
    except (UnidentifiedImageError, OSError, ValueError):
        _fail(415, "BAD_IMAGE", "이 사진 형식은 읽을 수 없어요. 카메라로 다시 찍어 주세요.")

    now = datetime.now(timezone.utc)
    row = {"id": str(uuid.uuid4()), "status": "processing", "stage": "reading", "result": None,
           "error_code": None, "error_reason": None, "error_message": None,
           "created_at": now.isoformat(), "expires_at": (now + timedelta(hours=settings.result_ttl_hours)).isoformat()}
    store.create(row)
    background.add_task(_process, row["id"], jpeg)
    return {"id": row["id"], "status": "processing", "stage": "reading"}


@app.get("/api/analyses/{aid}", response_model=Analysis)
def get_analysis(aid: str):
    try:
        uuid.UUID(aid)
    except ValueError:
        _fail(404, "NOT_FOUND", "결과가 없거나 지워졌어요.")
    row = store.get(aid)
    if not row:
        _fail(404, "NOT_FOUND", "결과가 없거나 지워졌어요.")
    return row


@app.delete("/api/analyses/{aid}", status_code=204)
def delete_analysis(aid: str):
    try:
        uuid.UUID(aid)
    except ValueError:
        return Response(status_code=204)
    store.delete(aid)
    return Response(status_code=204)


@app.get("/api/health")
def health():
    return {"ok": True, "provider": provider.name, "store": store.name, "today": settings.today().isoformat()}

app.include_router(push_router)

FRONTEND = ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
