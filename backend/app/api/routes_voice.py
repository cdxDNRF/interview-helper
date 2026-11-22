from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import InterviewSession
from app.schemas.prep import PrepPlan
from app.services.settings_service import get_runtime_config
from app.voice.interfaces import BaseTTSProvider
from app.voice.stt_openai import OpenAICompatSTTProvider
from app.voice.tts_edge import EdgeTTSProvider
from app.voice.tts_stubs import (
    KokoroTTSProvider,
    NullTTSProvider,
    OpenAICompatTTSProvider,
    WebSpeechFallbackProvider,
)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    rate: str | None = None


def resolve_tts_provider(provider_name: str, voice: str, rate: str) -> BaseTTSProvider:
    if provider_name == "edge_tts":
        return EdgeTTSProvider(default_voice=voice, default_rate=rate)
    if provider_name == "web_speech":
        return WebSpeechFallbackProvider()
    if provider_name == "kokoro":
        return KokoroTTSProvider()
    if provider_name == "openai_tts":
        return OpenAICompatTTSProvider()
    return NullTTSProvider()


@router.post("/tts")
async def synthesize_tts(payload: TTSRequest, db: AsyncSession = Depends(get_db)):
    cfg = await get_runtime_config(db)
    provider = resolve_tts_provider(
        cfg.voice.tts_provider, cfg.voice.edge_tts_voice, cfg.voice.edge_tts_rate
    )
    res = await provider.synthesize(
        payload.text,
        voice=payload.voice or cfg.voice.edge_tts_voice,
        rate=payload.rate or cfg.voice.edge_tts_rate,
    )

    if res.fallback_to_browser or len(res.audio_bytes) == 0:
        return JSONResponse(
            status_code=200,
            headers={"X-TTS-Fallback": "web_speech", "X-TTS-Provider": res.provider_used},
            content={
                "fallback": True,
                "provider": res.provider_used,
                "reason": res.fallback_reason,
            },
        )

    return Response(
        content=res.audio_bytes,
        media_type=res.content_type,
        headers={"X-TTS-Provider": res.provider_used},
    )


@router.post("/stt")
async def transcribe_audio(
    audio: UploadFile = File(...),
    session_id: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    cfg = await get_runtime_config(db)
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传的录音文件为空 (0 字节)")

    hotwords: list[str] = []
    if session_id:
        sess = await db.get(InterviewSession, session_id)
        if sess and sess.prep_plan_json:
            hotwords = PrepPlan.model_validate(sess.prep_plan_json).hotwords

    if cfg.mock_mode:
        return {
            "text": "（Mock 模式录音转写）我在项目中通过异步状态机和 Redis Pub/Sub 解决了多实例 WebSocket 状态同步问题，P99 延迟控制在 18ms 内。",
            "provider_used": "mock_stt",
            "word_timestamps": [],
            "duration_ms": 4200,
        }

    if cfg.voice.stt_provider != "openai_stt":
        raise HTTPException(
            status_code=400,
            detail=f"当前 STT 模式为 {cfg.voice.stt_provider}，请在设置页切换为 openai_stt 后调用服务端转写。",
        )

    provider = OpenAICompatSTTProvider(
        base_url=cfg.voice.stt_base_url,
        api_key=cfg.voice.stt_api_key,
        model=cfg.voice.stt_model,
    )
    try:
        res = await provider.transcribe(raw, audio.filename or "recording.webm", hotwords=hotwords)
        return {
            "text": res.text,
            "provider_used": res.provider_used,
            "word_timestamps": res.word_timestamps,
            "duration_ms": res.duration_ms,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"STT 转写失败: {exc}") from exc
