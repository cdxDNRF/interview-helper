import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.engine import _make_engine, get_db, init_db
from app.db.models import Base
from app.main import app
from app.packs.registry import load_presets_catalog


def test_presets_catalog_integrity():
    catalog = load_presets_catalog()
    assert len(catalog.roles) == 8
    assert len(catalog.fundamentals) == 7
    assert len(catalog.general_packs) == 3

    for r in catalog.roles:
        assert len(r.core_topics) >= 4
        assert r.default_jd.strip()
        assert len(r.hotwords) >= 5
    for f in catalog.fundamentals:
        assert len(f.core_topics) >= 2
        assert len(f.hotwords) >= 5
    for g in catalog.general_packs:
        assert len(g.core_topics) >= 1


@pytest.mark.asyncio
async def test_legacy_sqlite_table_idempotent_migration(tmp_path):
    db_file = tmp_path / "legacy.db"
    eng = _make_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    try:
        async with eng.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE interview_contexts (
                        id VARCHAR(36) PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        resume_filename VARCHAR(255) NOT NULL,
                        resume_markdown TEXT NOT NULL,
                        job_description TEXT NOT NULL,
                        github_repo_url VARCHAR(500),
                        repo_digest_markdown TEXT,
                        repo_token_count INTEGER NOT NULL DEFAULT 0,
                        repo_warnings_json JSON NOT NULL DEFAULT '[]',
                        created_at DATETIME
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO interview_contexts (id, title, resume_filename, resume_markdown, job_description) "
                    "VALUES ('old-1', '旧场次', 'cv.md', '# CV', 'JD')"
                )
            )

        await init_db(eng)
        await init_db(eng)  # Second call must stay idempotent

        async with eng.connect() as conn:
            cols = {
                r[1]
                for r in (await conn.execute(text("PRAGMA table_info(interview_contexts);"))).all()
            }
            assert {"interview_type", "role_track_id", "knowledge_pack_ids_json"} <= cols
            row = (
                await conn.execute(
                    text("SELECT interview_type FROM interview_contexts WHERE id='old-1'")
                )
            ).first()
            assert row[0] == "project_deep_dive"
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_zero_resume_general_bagu_and_role_tracks_e2e(tmp_path):
    db_file = tmp_path / "modes_e2e.db"
    test_eng = _make_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    test_factory = async_sessionmaker(test_eng, expire_on_commit=False)

    async def override_get_db():
        async with test_factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db
    try:
        await init_db(test_eng)

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Fetch presets endpoint
            r_pre = await client.get("/api/presets")
            assert r_pre.status_code == 200
            assert len(r_pre.json()["roles"]) == 8
            assert len(r_pre.json()["fundamentals"]) == 7

            # Enable Mock Mode
            s_cur = (await client.get("/api/settings")).json()
            s_cur["mock_mode"] = True
            for st in ("prep_llm", "live_llm", "judge_llm"):
                s_cur[st]["api_key"] = ""
            await client.put("/api/settings", json=s_cur)

            # 2. General Behavioral (zero resume, zero JD)
            ctx_gen = await client.post(
                "/api/contexts",
                data={
                    "interview_type": "general_behavioral",
                    "knowledge_pack_ids": "general_behavioral,incident_ownership",
                },
            )
            assert ctx_gen.status_code == 200
            c_gen = ctx_gen.json()
            assert c_gen["interview_type"] == "general_behavioral"
            assert c_gen["resume_filename"] == "preset-no-resume"

            s_gen = (
                await client.post(
                    "/api/sessions",
                    json={
                        "context_id": c_gen["id"],
                        "interviewer_style": "gentle",
                        "interaction_mode": "text",
                    },
                )
            ).json()
            assert s_gen["interview_type"] == "general_behavioral"

            # Strong STAR answer -> advances ladder & keeps code_and_testing N/A
            r_turn = await client.post(
                f"/api/sessions/{s_gen['id']}/turns/stream",
                json={
                    "content": "背景是线上缓存异常导致延迟飙升，我负责推动止血和跨部门对齐，经过权衡我决定先降级非核心接口，P99 恢复到 20ms 并做了机制复盘。",
                    "stt_provider_used": "text",
                },
            )
            assert r_turn.status_code == 200
            assert "Action" in r_turn.text or "行动" in r_turn.text

            await client.post(f"/api/sessions/{s_gen['id']}/finish")
            rep_gen = (await client.post(f"/api/sessions/{s_gen['id']}/evaluate")).json()
            assert rep_gen["dimensions"]["code_and_testing"]["score"] is None

            # 3. CS Fundamentals / 八股突击 (zero resume, multi-pack mysql + redis_mq)
            ctx_bagu = (
                await client.post(
                    "/api/contexts",
                    data={
                        "interview_type": "bagu_fundamentals",
                        "knowledge_pack_ids": "mysql,redis_mq",
                    },
                )
            ).json()
            s_bagu = (
                await client.post(
                    "/api/sessions",
                    json={
                        "context_id": ctx_bagu["id"],
                        "interviewer_style": "pressure",
                        "interaction_mode": "text",
                    },
                )
            ).json()
            assert s_bagu["interview_type"] == "bagu_fundamentals"
            assert len(s_bagu["prep_plan"]["topics"]) >= 4

            # 4. CS Role Track (backend_engineer) includes coding challenge
            ctx_role = (
                await client.post(
                    "/api/contexts",
                    data={
                        "interview_type": "cs_role_track",
                        "role_track_id": "backend_engineer",
                    },
                )
            ).json()
            s_role = (
                await client.post(
                    "/api/sessions",
                    json={
                        "context_id": ctx_role["id"],
                        "interviewer_style": "pressure",
                        "interaction_mode": "text",
                    },
                )
            ).json()
            assert s_role["role_track_id"] == "backend_engineer"
            assert s_role["prep_plan"]["topics"][0]["coding_challenge"] is not None
    finally:
        app.dependency_overrides.clear()
        await test_eng.dispose()
