import json
from contextlib import asynccontextmanager

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import AppRuntimeConfig, StageLLMSettings
from app.db.engine import _make_engine, get_db
from app.db.models import Base, InterviewContext, InterviewSession, InterviewTurn
from app.graph.interview_graph import initialize_state_snapshot
from app.llm import client as llm_client
from app.llm.mock_adapter import mock_prep_plan
from app.main import app


class _FakeSSEResponse:
    def __init__(self, status_code: int, lines: list[str]):
        self.status_code = status_code
        self._lines = lines
        self.request = httpx.Request("POST", "http://fake-llm/v1/chat/completions")

    async def aread(self) -> bytes:
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


@pytest.mark.asyncio
async def test_stream_chat_completion_recovers_from_tool_calls(monkeypatch):
    captured_bodies: list[dict] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        @asynccontextmanager
        async def stream(self, method, url, headers=None, json=None):
            captured_bodies.append(json)
            if len(captured_bodies) == 1:
                lines = [
                    'data: {"model":"gemini/gemini-3.8-flash","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"record_observation","arguments":"{\\"signal\\":\\"strong\\"}"}}]},"finish_reason":null}]}',
                    'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":100,"cached_tokens":0,"completion_tokens":36}}',
                    "data: [DONE]",
                ]
            else:
                lines = [
                    'data: {"model":"gemini/gemini-3.8-flash","choices":[{"delta":{"content":"你在限流降级时如何避免"},"finish_reason":null}]}',
                    'data: {"choices":[{"delta":{"content":"本地桶瞬间放行过载？"},"finish_reason":"stop"}],"usage":{"prompt_tokens":140,"cached_tokens":90,"completion_tokens":24}}',
                    "data: [DONE]",
                ]
            yield _FakeSSEResponse(200, lines)

    monkeypatch.setattr(llm_client, "_build_httpx_client", lambda *a, **kw: _FakeAsyncClient())

    cfg = AppRuntimeConfig()
    stage = StageLLMSettings(base_url="http://fake-llm/v1", model="gemini/gemini-3.8-flash")
    messages = [
        {"role": "system", "content": "STATIC_PREFIX"},
        {"role": "user", "content": "candidate answer"},
    ]

    deltas: list[str] = []
    done_res = None
    async for ev in llm_client.stream_chat_completion(
        stage, cfg, messages, tools=[{"type": "function", "function": {"name": "record_observation"}}]
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "done":
            done_res = ev["result"]

    assert "".join(deltas) == "你在限流降级时如何避免本地桶瞬间放行过载？"
    assert done_res is not None
    assert done_res.prompt_tokens == 240
    assert done_res.cached_tokens == 90
    assert done_res.completion_tokens == 60
    assert len(captured_bodies) == 2
    # Static prefix messages[0] stayed intact across the tool round-trip
    assert captured_bodies[1]["messages"][0] == {"role": "system", "content": "STATIC_PREFIX"}
    assert "tools" not in captured_bodies[1]


@pytest.mark.asyncio
async def test_submit_turn_non_mock_guards_empty_ai_reply_and_sanitizes_history(tmp_path, monkeypatch):
    db_file = tmp_path / "empty_guard.db"
    test_eng = _make_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    test_factory = async_sessionmaker(test_eng, expire_on_commit=False)

    async def override_get_db():
        async with test_factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db

    seen_stream_messages: list[list[dict]] = []

    async def _fake_chat_completion(stage_cfg, runtime_cfg, messages, **kwargs):
        # Differentiate live_eval vs fallback live_reply
        if kwargs.get("response_format"):
            return llm_client.LLMCallResult(
                content=json.dumps(
                    {
                        "score": 0.85,
                        "is_rote_memorization": False,
                        "is_off_topic": False,
                        "covered_points": ["预取配额"],
                        "missing_points": [],
                        "brief_diagnosis": "思路清晰，进 L2",
                    },
                    ensure_ascii=False,
                ),
                model="fake-live-eval",
                prompt_tokens=100,
                cached_tokens=0,
                completion_tokens=40,
                latency_ms=50,
                estimated_cost_cny=0.001,
                raw_usage={},
            )
        # Non-streaming fallback also returns empty to verify deterministic non-empty floor
        return llm_client.LLMCallResult(
            content="",
            model="fake-live-reply",
            prompt_tokens=120,
            cached_tokens=80,
            completion_tokens=10,
            latency_ms=30,
            estimated_cost_cny=0.001,
            raw_usage={},
        )

    async def _fake_stream_chat_completion(stage_cfg, runtime_cfg, messages, *, tools=None):
        seen_stream_messages.append(messages)
        # Verify route_sessions omitted active tools for live_reply
        assert tools is None
        yield {
            "type": "done",
            "result": llm_client.LLMCallResult(
                content="",
                model="fake-live-reply",
                prompt_tokens=200,
                cached_tokens=0,
                completion_tokens=5,
                latency_ms=40,
                estimated_cost_cny=0.001,
                raw_usage={},
            ),
        }

    from app.api import routes_sessions
    from app.graph import interview_graph

    monkeypatch.setattr(interview_graph, "chat_completion", _fake_chat_completion)
    monkeypatch.setattr(routes_sessions, "stream_chat_completion", _fake_stream_chat_completion)
    monkeypatch.setattr(routes_sessions, "chat_completion", _fake_chat_completion)

    try:
        async with test_eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Seed a session that already has a corrupted empty AI turn at turn_index=2
        prep = mock_prep_plan("后端开发", "高并发", "", "pressure", interview_type="cs_role_track", role_track_id="backend_engineer")
        snap = initialize_state_snapshot(prep)
        async with test_factory() as db:
            ctx = InterviewContext(
                title="后端空回复自愈测试",
                interview_type="cs_role_track",
                role_track_id="backend_engineer",
                knowledge_pack_ids_json=[],
                resume_filename="preset.md",
                resume_markdown="preset",
                job_description="backend",
                repo_digest_markdown="",
                repo_token_count=0,
            )
            db.add(ctx)
            await db.flush()
            sess = InterviewSession(
                context_id=ctx.id,
                interviewer_style="pressure",
                interaction_mode="text",
                status="in_progress",
                prep_plan_json=prep.model_dump(mode="json"),
                state_snapshot_json=snap.model_dump(mode="json"),
                static_prefix_sha256="abc",
            )
            db.add(sess)
            await db.flush()
            db.add_all(
                [
                    InterviewTurn(session_id=sess.id, turn_index=0, topic_index=0, ladder_level=1, speaker="ai", content="开场题"),
                    InterviewTurn(session_id=sess.id, turn_index=1, topic_index=0, ladder_level=1, speaker="user", content="候选人第一轮回答"),
                    InterviewTurn(session_id=sess.id, turn_index=2, topic_index=0, ladder_level=2, speaker="ai", content=""),
                ]
            )
            await db.commit()
            sess_id = sess.id

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r_sse = await client.post(
                f"/api/sessions/{sess_id}/turns/stream",
                json={
                    "content": "我继续补充 Redis 抖动时采用预取配额 + Fail-Open 半开探测。",
                    "timestamp_start_ms": 2000,
                    "timestamp_end_ms": 12000,
                    "pause_before_ms": 500,
                    "stt_provider_used": "text",
                },
            )
            assert r_sse.status_code == 200
            assert "event: delta" in r_sse.text
            assert "event: done" in r_sse.text

            r_detail = await client.get(f"/api/sessions/{sess_id}")
            assert r_detail.status_code == 200
            turns = r_detail.json()["turns"]
            assert len(turns[-1]["content"].strip()) > 10

            # Sanitized history ensured turn 2 wasn't sent as an empty assistant message
            assert len(seen_stream_messages) == 1
            hist_assistant = [m for m in seen_stream_messages[0][1:-1] if m["role"] == "assistant"]
            assert all(m["content"].strip() for m in hist_assistant)
    finally:
        app.dependency_overrides.clear()
        await test_eng.dispose()
