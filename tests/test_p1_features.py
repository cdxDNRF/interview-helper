import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.engine import _make_engine, get_db
from app.db.models import Base, LLMUsageLog
from app.graph.interview_graph import (
    build_interviewer_messages,
    compute_next_ladder_state,
    initialize_state_snapshot,
)
from app.llm.mock_adapter import mock_prep_plan
from app.main import app


def test_code_snapshot_preserves_static_prefix():
    resume = "# Candidate\nFastAPI + asyncio engineer"
    jd = "Backend Engineer"
    repo_digest = "## File: ws_manager.py\nclass ConnectionManager: pass"
    prep = mock_prep_plan(resume, jd, repo_digest, "pressure")
    state = initialize_state_snapshot(prep)
    next_state, action = compute_next_ladder_state(state, prep, {"score": 0.78})

    msgs_plain, sha_plain = build_interviewer_messages(
        interviewer_style="pressure",
        resume_markdown=resume,
        job_description=jd,
        repo_digest_markdown=repo_digest,
        prep_plan=prep,
        history_messages=[{"role": "assistant", "content": prep.topics[0].l1_seed_question}],
        latest_user_message="这是我的文字回答。",
        next_state=next_state,
        eval_action=action,
        eval_result={"score": 0.78, "brief_diagnosis": "ok"},
    )
    msgs_code, sha_code = build_interviewer_messages(
        interviewer_style="pressure",
        resume_markdown=resume,
        job_description=jd,
        repo_digest_markdown=repo_digest,
        prep_plan=prep,
        history_messages=[{"role": "assistant", "content": prep.topics[0].l1_seed_question}],
        latest_user_message="这是我的文字回答。\n\n[候选人同步提交的代码快照]\ndef put(): pass",
        next_state=next_state,
        eval_action=action,
        eval_result={"score": 0.78, "brief_diagnosis": "ok"},
    )

    assert sha_plain == sha_code
    assert msgs_plain[0]["content"] == msgs_code[0]["content"]
    assert "def put(): pass" in msgs_code[-1]["content"]


@pytest.mark.asyncio
async def test_p1_code_mistake_retry_and_observability_e2e(tmp_path):
    db_file = tmp_path / "p1_e2e.db"
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
            # Enable Mock Mode
            s_cur = (await client.get("/api/settings")).json()
            s_cur["mock_mode"] = True
            for st in ("prep_llm", "live_llm", "judge_llm"):
                s_cur[st]["api_key"] = ""
            await client.put("/api/settings", json=s_cur)

            ctx = (
                await client.post(
                    "/api/contexts",
                    data={
                        "title": "P1 综合测试场次",
                        "job_description": "高级 Python 后端工程师",
                        "resume_text": "# 简历\n熟悉 FastAPI, Redis, SQLite WAL",
                    },
                )
            ).json()

            sess = (
                await client.post(
                    "/api/sessions",
                    json={
                        "context_id": ctx["id"],
                        "interviewer_style": "pressure",
                        "interaction_mode": "text",
                    },
                )
            ).json()
            assert sess["prep_plan"]["topics"][0]["coding_challenge"] is not None

            # Turn 1: shallow rote answer -> triggers mistake capture (< 0.65)
            r1 = await client.post(
                f"/api/sessions/{sess['id']}/turns/stream",
                json={
                    "content": "大概就是这样吧，网上说一般用封装好的装饰器，具体没看过实现。",
                    "stt_provider_used": "text",
                },
            )
            assert r1.status_code == 200

            # Turn 2: submits Pyodide passing code snapshot
            r2 = await client.post(
                f"/api/sessions/{sess['id']}/turns/stream",
                json={
                    "content": "我实现了 BoundedRegistry，用字典加惰性 TTL 清理，O(1) 读写，同时加了容量拦截。",
                    "stt_provider_used": "text",
                    "code_snapshot": {
                        "language": "python",
                        "source_code": "class BoundedRegistry:\n    def put(self, k, v): return True",
                        "tests_passed": True,
                        "passed_count": 6,
                        "total_count": 6,
                        "test_output": "ALL_TESTS_PASSED: 6/6",
                        "exec_time_ms": 14,
                    },
                },
            )
            assert r2.status_code == 200

            # Verify code submission persisted on session detail
            detail = (await client.get(f"/api/sessions/{sess['id']}")).json()
            assert len(detail["code_submissions"]) == 1
            assert detail["code_submissions"][0]["tests_passed"] is True

            # Seed one usage log row to verify observability aggregation
            async with test_factory() as db_sess:
                db_sess.add(
                    LLMUsageLog(
                        session_id=sess["id"],
                        stage="live_reply",
                        model_name="buddy/deepseek-v4.1-flash",
                        prompt_tokens=20000,
                        cached_tokens=16000,
                        completion_tokens=300,
                        latency_ms=420,
                        estimated_cost_cny=0.012,
                        static_prefix_sha256=detail["telemetry"]["static_prefix_sha256"],
                    )
                )
                await db_sess.commit()

            await client.post(f"/api/sessions/{sess['id']}/finish")
            rep = (await client.post(f"/api/sessions/{sess['id']}/evaluate")).json()
            assert rep["dimensions"]["code_and_testing"]["score"] is not None
            assert "Pyodide" in rep["dimensions"]["code_and_testing"]["evidence_quotes"][0]["quote"]

            # Mistakes auto-synced
            mistakes = (await client.get("/api/mistakes")).json()
            assert len(mistakes) >= 1
            m0 = mistakes[0]
            assert m0["status"] == "open"

            # Retry with solid technical answer -> score jump & mastered
            retried = (
                await client.post(
                    f"/api/mistakes/{m0['id']}/retry",
                    json={
                        "retry_answer": "我们在 ws_manager.py 中通过 Redis Pub/Sub 同步跨 worker 连接，异步锁只锁 session_id 粒度，加 CAS 版本号与背压队列 asyncio.Queue(256)，5000 并发下 P99 12ms，并在 Redis 超时 200ms 时触发熔断降级。",
                        "duration_sec": 45,
                    },
                )
            ).json()
            assert retried["best_retry_score"] >= 75.0
            assert retried["score_delta"] > 0
            assert retried["status"] == "mastered"
            assert retried["retry_count"] == 1

            # Observability endpoints
            obs_over = (await client.get("/api/observability/overview")).json()
            assert obs_over["total_sessions"] == 1
            assert obs_over["total_llm_calls"] == 1
            assert obs_over["avg_cache_hit_rate"] == 0.8

            obs_sess = (await client.get(f"/api/observability/sessions/{sess['id']}")).json()
            assert obs_sess["prefix_consistent"] is True
            assert obs_sess["logs"][0]["latency_ms"] == 420
    finally:
        app.dependency_overrides.clear()
        await test_eng.dispose()
