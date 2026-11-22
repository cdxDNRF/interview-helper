import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import AppRuntimeConfig
from app.db.engine import _make_engine
from app.graph.interview_graph import (
    build_interview_turn_graph,
    compute_next_ladder_state,
    initialize_state_snapshot,
)
from app.llm.mock_adapter import mock_prep_plan


def test_deterministic_ladder_progression_and_two_fail_switch():
    prep = mock_prep_plan("resume", "jd", "src/main.py", "pressure")
    state = initialize_state_snapshot(prep)
    assert state.current_topic_idx == 0
    assert state.ladder_level == 1

    # L1 -> L2 -> L3 -> L4 on score >= 0.65
    for expected_level in (2, 3, 4):
        state, action = compute_next_ladder_state(state, prep, {"score": 0.72})
        assert action == "upgrade_level"
        assert state.ladder_level == expected_level
        assert state.consecutive_fail_count == 0

    # L4 pass -> switches to topic 1 at L1
    state, action = compute_next_ladder_state(state, prep, {"score": 0.85})
    assert action == "next_topic"
    assert state.current_topic_idx == 1
    assert state.ladder_level == 1
    assert state.topic_records[0].status == "mastered"

    # Topic 1: 1st fail -> reprobe at same level
    state, action = compute_next_ladder_state(state, prep, {"score": 0.40})
    assert action == "reprobe_same_level"
    assert state.current_topic_idx == 1
    assert state.ladder_level == 1
    assert state.consecutive_fail_count == 1

    # Topic 1: 2nd consecutive fail -> mark failed_moved_on & switch to topic 2
    state, action = compute_next_ladder_state(state, prep, {"score": 0.30})
    assert action == "next_topic"
    assert state.current_topic_idx == 2
    assert state.ladder_level == 1
    assert state.consecutive_fail_count == 0
    assert state.topic_records[1].status == "failed_moved_on"


@pytest.mark.asyncio
async def test_langgraph_mock_turn_invocation():
    cfg = AppRuntimeConfig(mock_mode=True)
    prep = mock_prep_plan("Python FastAPI Redis", "Backend Engineer", "## File: api.py", "gentle")
    state = initialize_state_snapshot(prep)
    graph = build_interview_turn_graph(cfg)

    out = await graph.ainvoke(
        {
            "session_id": "test-sess",
            "interviewer_style": "gentle",
            "resume_markdown": "Python FastAPI",
            "job_description": "Backend Engineer",
            "repo_digest_markdown": "## File: api.py",
            "prep_plan": prep,
            "state_snapshot": state,
            "history_messages": [{"role": "assistant", "content": prep.topics[0].l1_seed_question}],
            "latest_user_message": "我们在 api.py 用异步队列、Redis 分布式锁和 CAS 保证幂等，P99 控制在 15ms 内，并发 3000 QPS 压测通过。",
            "mock_mode": True,
        }
    )

    assert out["eval_result"]["score"] >= 0.65
    assert out["eval_action"] == "upgrade_level"
    assert out["next_state"].ladder_level == 2
    assert out["static_prefix_sha256"]


@pytest.mark.asyncio
async def test_sqlite_wal_mode_enabled(tmp_path):
    db_path = tmp_path / "wal_check.db"
    eng = _make_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with eng.connect() as conn:
        mode = (await conn.execute(text("PRAGMA journal_mode;"))).scalar()
        fk = (await conn.execute(text("PRAGMA foreign_keys;"))).scalar()
    await eng.dispose()
    assert str(mode).lower() == "wal"
    assert int(fk) == 1
