import json

import httpx
import pytest
from httpx import ASGITransport

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.engine import _make_engine, get_db
from app.db.models import Base
from app.main import app


@pytest.mark.asyncio
async def test_api_end_to_end_mock_flow(tmp_path):
    db_file = tmp_path / "e2e_mock.db"
    test_eng = _make_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    test_factory = async_sessionmaker(test_eng, expire_on_commit=False)

    async def override_get_db():
        async with test_factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with test_eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Read & toggle Mock Mode
            r_set = await client.get("/api/settings")
            assert r_set.status_code == 200
            settings_data = r_set.json()
            settings_data["mock_mode"] = True
            for stage in ("prep_llm", "live_llm", "judge_llm"):
                settings_data[stage]["api_key"] = ""
            r_put = await client.put("/api/settings", json=settings_data)
            assert r_put.status_code == 200
            assert r_put.json()["mock_mode"] is True

            # 2. Create Context with Markdown resume + JD
            r_ctx = await client.post(
                "/api/contexts",
                data={
                    "title": "后端工程师Mock模拟",
                    "job_description": "负责高并发 FastAPI/WebSocket 服务与 SQLite/Redis 存储。",
                    "resume_text": "# 候选人简历\n- 实现 FastAPI ws_manager 连接管理器，支持心跳与重连。",
                    "github_repo_url": "",
                },
            )
            assert r_ctx.status_code == 200
            ctx = r_ctx.json()

            # 3. Create Session -> triggers Prep
            r_sess = await client.post(
                "/api/sessions",
                json={
                    "context_id": ctx["id"],
                    "interviewer_style": "pressure",
                    "interaction_mode": "text",
                },
            )
            assert r_sess.status_code == 200
            sess = r_sess.json()
            assert len(sess["prep_plan"]["topics"]) >= 4
            assert len(sess["turns"]) == 1  # Opening L1 question
            assert sess["telemetry"]["static_prefix_sha256"]

            # 4. Submit 2 turns via SSE stream
            for ans in [
                "我们在 ws_manager.py 里用 Redis Pub/Sub 和分布式锁同步连接状态，5000 并发下 P99 12ms。",
                "高并发实战中每个连接绑定 asyncio.Queue(256) 做背压，加单调递增 seq_id CAS 去重。",
            ]:
                r_sse = await client.post(
                    f"/api/sessions/{sess['id']}/turns/stream",
                    json={
                        "content": ans,
                        "timestamp_start_ms": 1000,
                        "timestamp_end_ms": 11000,
                        "pause_before_ms": 1500,
                        "stt_provider_used": "text",
                    },
                )
                assert r_sse.status_code == 200
                body = r_sse.text
                assert "event: state" in body
                assert "event: delta" in body
                assert "event: done" in body

            # 5. Finish & Evaluate
            r_fin = await client.post(f"/api/sessions/{sess['id']}/finish")
            assert r_fin.status_code == 200
            assert r_fin.json()["status"] == "completed"

            r_eval = await client.post(f"/api/sessions/{sess['id']}/evaluate")
            assert r_eval.status_code == 200
            rep = r_eval.json()
            assert rep["overall_score"] is not None
            assert rep["speech_metrics"]["longest_silence_sec"] == 1.5
            assert len(rep["transcript_annotations"]) >= 1

            # 6. Export Markdown & List History
            r_exp = await client.get(f"/api/sessions/{sess['id']}/report/export")
            assert r_exp.status_code == 200
            assert "AI 模拟面试复盘报告" in r_exp.text

            r_list = await client.get("/api/sessions")
            assert r_list.status_code == 200
            assert any(item["id"] == sess["id"] for item in r_list.json())
    finally:
        app.dependency_overrides.clear()
        await test_eng.dispose()
