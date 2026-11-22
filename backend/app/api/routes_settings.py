import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import StageLLMSettings
from app.db import get_db
from app.llm.client import chat_completion, fetch_available_models
from app.schemas.settings import (
    FetchModelsRequest,
    SettingsReadResponse,
    SettingsUpdateRequest,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services.settings_service import (
    get_runtime_config,
    to_masked_response,
    update_runtime_config,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsReadResponse)
async def read_settings(db: AsyncSession = Depends(get_db)):
    cfg = await get_runtime_config(db)
    return to_masked_response(cfg)


@router.put("", response_model=SettingsReadResponse)
async def save_settings(payload: SettingsUpdateRequest, db: AsyncSession = Depends(get_db)):
    updated = await update_runtime_config(db, payload)
    return to_masked_response(updated)


@router.post("/models")
async def list_remote_models(payload: FetchModelsRequest, db: AsyncSession = Depends(get_db)):
    cfg = await get_runtime_config(db)
    key = payload.api_key.strip()
    if not key or "***" in key:
        # Reuse configured key for matching base_url if user didn't retype masked key
        for stage in (cfg.prep_llm, cfg.live_llm, cfg.judge_llm):
            if stage.base_url.rstrip("/") == payload.base_url.rstrip("/"):
                key = stage.api_key
                break
    try:
        models = await fetch_available_models(payload.base_url, key or "sk-local")
        return {"models": models}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"拉取模型列表失败: {exc}") from exc


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(payload: TestConnectionRequest, db: AsyncSession = Depends(get_db)):
    cfg = await get_runtime_config(db)
    key = payload.api_key.strip()
    if not key or "***" in key:
        stage_map = {
            "prep": cfg.prep_llm,
            "live": cfg.live_llm,
            "judge": cfg.judge_llm,
        }
        key = stage_map[payload.stage].api_key or "sk-local"

    t0 = time.perf_counter()
    try:
        res = await chat_completion(
            StageLLMSettings(
                base_url=payload.base_url.strip(),
                api_key=key,
                model=payload.model.strip(),
                temperature=0.0,
                max_tokens=32,
            ),
            cfg,
            [{"role": "user", "content": "Reply with exactly: OK"}],
        )
        return TestConnectionResponse(
            ok=True,
            latency_ms=res.latency_ms,
            model=res.model,
            reply_preview=res.content[:120],
        )
    except Exception as exc:
        return TestConnectionResponse(
            ok=False,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            model=payload.model,
            error=str(exc)[:300],
        )
