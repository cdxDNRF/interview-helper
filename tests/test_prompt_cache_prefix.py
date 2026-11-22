import re

from app.graph.interview_graph import (
    build_interviewer_messages,
    compute_next_ladder_state,
    initialize_state_snapshot,
)
from app.llm.mock_adapter import mock_prep_plan
from app.llm.prompts import INTERVIEW_TOOLS_DEFINITION, build_static_interview_prefix


def test_static_prefix_order_and_forbidden_dynamic_tokens():
    resume = "# 张三\n- 后端工程师，熟悉 FastAPI 与 Redis"
    jd = "招聘高级 Python 后端工程师，要求高并发与可观测性经验"
    repo_digest = "## File: backend/ws_manager.py\nclass ConnectionManager: pass"

    prep = mock_prep_plan(resume, jd, repo_digest, "pressure")
    prefix, sha1 = build_static_interview_prefix(
        interviewer_style="pressure",
        resume_markdown=resume,
        job_description=jd,
        repo_digest_markdown=repo_digest,
        prep_plan=prep,
        tools=INTERVIEW_TOOLS_DEFINITION,
    )
    _, sha2 = build_static_interview_prefix(
        interviewer_style="pressure",
        resume_markdown=resume,
        job_description=jd,
        repo_digest_markdown=repo_digest,
        prep_plan=prep,
        tools=INTERVIEW_TOOLS_DEFINITION,
    )

    assert sha1 == sha2
    # Order check: persona -> tools -> resume -> JD/prep -> Repomix repo
    idx_persona = prefix.index("=== 1. 面试官系统人设 ===")
    idx_tools = prefix.index("=== 2. 固定工具定义（Canonical JSON） ===")
    idx_resume = prefix.index("=== 3. 候选人简历（Markdown） ===")
    idx_jd = prefix.index("=== 4. 目标岗位 JD 与固定 Prep 题纲 ===")
    idx_repo = prefix.index("=== 5. Repomix AST 压缩源码骨架 ===")
    assert idx_persona < idx_tools < idx_resume < idx_jd < idx_repo

    # Forbidden dynamic fields in static prefix
    assert not re.search(r"202\d-\d{2}-\d{2}", prefix)
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", prefix, re.I
    )
    assert "轮次" not in prefix[:idx_resume]


def test_multi_turn_prefix_byte_identical_and_append_only():
    resume = "# 李四\n熟悉 SQLite WAL 与 LangGraph"
    jd = "AI Agent 研发工程师"
    repo_digest = "## File: app/graph/interview_graph.py\ndef advance(): pass"
    prep = mock_prep_plan(resume, jd, repo_digest, "gentle")

    state = initialize_state_snapshot(prep)
    history: list[dict[str, str]] = [
        {"role": "assistant", "content": prep.topics[0].l1_seed_question}
    ]
    seen_system_hashes: list[str] = []

    for turn_no in range(4):
        user_msg = f"第 {turn_no + 1} 轮回答：我们通过 asyncio.Lock 和 Redis Pub/Sub 解决并发同步，P99 15ms。"
        eval_res = {"score": 0.78, "brief_diagnosis": "达标"}
        next_state, action = compute_next_ladder_state(state, prep, eval_res)

        messages, prefix_sha = build_interviewer_messages(
            interviewer_style="gentle",
            resume_markdown=resume,
            job_description=jd,
            repo_digest_markdown=repo_digest,
            prep_plan=prep,
            history_messages=history,
            latest_user_message=user_msg,
            next_state=next_state,
            eval_action=action,
            eval_result=eval_res,
        )
        seen_system_hashes.append(prefix_sha)
        assert messages[0]["role"] == "system"
        # History messages remain untouched before the new trailing user turn
        assert messages[1 : 1 + len(history)] == history

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": f"追问 L{next_state.ladder_level}"})
        state = next_state

    assert len(set(seen_system_hashes)) == 1
