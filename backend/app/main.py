from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_contexts import router as contexts_router
from app.api.routes_reports import router as reports_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_settings import router as settings_router
from app.api.routes_voice import router as voice_router
from app.db.engine import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="interview-helper API",
    version="0.1.0",
    description="AI 模拟面试 P0 后端服务 (FastAPI + LangGraph + SQLite WAL)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-TTS-Fallback", "X-TTS-Provider"],
)

app.include_router(settings_router)
app.include_router(contexts_router)
app.include_router(sessions_router)
app.include_router(voice_router)
app.include_router(reports_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
