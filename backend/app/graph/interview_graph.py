import json
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.config import AppRuntimeConfig
from app.graph.state import LiveTurnGraphState
from app.llm.client import chat_completion, strip_json_fences
from app.llm.mock_adapter import (
    mock_evaluate_turn,
    mock_interviewer_reply,
)
from app.llm.prompts import (
    INTERVIEW_TOOLS_DEFINITION,
    LIVE_EVAL_SYSTEM_PROMPT,
    build_static_interview_prefix,
)
from app.schemas.interview import InterviewStateSnapshot, TopicRecord
from app.schemas.prep import PrepPlan

PASS_THRESHOLD = 0.65
MAX_CONSECUTIVE_FAILS = 2
MAX_TURNS_PER_TOPIC = 6

LADDER_LABELS = {
    1: "L1 概念原理",
    2: "L2 个人实战",
    3: "L3 底层细节/代码实现",
    4: "L4 极端边界与故障排查",
}


def initialize_state_snapshot(prep_plan: PrepPlan) -> InterviewStateSnapshot:
    records = [
        TopicRecord(
            topic_id=t.topic_id,
            title=t.title,
            status="in_progress" if idx == 0 else "pending",
            max_level_reached=1,
            turns_spent=0,
        )
        for idx, t in enumerate(prep_plan.topics)
    ]
    return InterviewStateSnapshot(
        current_topic_idx=0,
        ladder_level=1,
        consecutive_fail_count=0,
        turns_on_current_topic=0,
        phase="questioning",
        topic_records=records,
    )


def compute_next_ladder_state(
    snapshot: InterviewStateSnapshot,
    prep_plan: PrepPlan,
    eval_result: dict[str, Any],
) -> tuple[InterviewStateSnapshot, str]:
    """
    100% 确定性四级追问状态机转移函数：
    - L1 -> L2 -> L3 -> L4，score >= 0.65 自动升级施压；
    - L4 达标后标记本考点 mastered 并切下一题；
    - score < 0.65 首次保持同层换角度反问，连续两轮答不出（或单题超上限）才记错切题。
    """
    state = snapshot.model_copy(deep=True)
    total_topics = len(prep_plan.topics)
    idx = min(state.current_topic_idx, max(0, total_topics - 1))

    if not state.topic_records:
        state.topic_records = initialize_state_snapshot(prep_plan).topic_records

    current_rec = state.topic_records[idx]
    current_rec.turns_spent += 1
    current_rec.max_level_reached = max(current_rec.max_level_reached, state.ladder_level)
    state.turns_on_current_topic += 1

    score = float(eval_result.get("score", 0.0))
    state.last_eval_score = round(score, 2)

    if score >= PASS_THRESHOLD:
        state.consecutive_fail_count = 0
        if state.ladder_level < 4:
            state.ladder_level = state.ladder_level + 1  # type: ignore[assignment]
            current_rec.max_level_reached = max(
                current_rec.max_level_reached, state.ladder_level
            )
            action = "upgrade_level"
        else:
            current_rec.status = "mastered"
            next_idx = idx + 1
            if next_idx >= total_topics:
                state.phase = "closing"
                action = "end_interview"
            else:
                state.current_topic_idx = next_idx
                state.ladder_level = 1
                state.turns_on_current_topic = 0
                state.topic_records[next_idx].status = "in_progress"
                action = "next_topic"
    else:
        state.consecutive_fail_count += 1
        should_switch = (
            state.consecutive_fail_count >= MAX_CONSECUTIVE_FAILS
            or state.turns_on_current_topic >= MAX_TURNS_PER_TOPIC
        )
        if should_switch:
            current_rec.status = "failed_moved_on"
            next_idx = idx + 1
            if next_idx >= total_topics:
                state.phase = "closing"
                action = "end_interview"
            else:
                state.current_topic_idx = next_idx
                state.ladder_level = 1
                state.consecutive_fail_count = 0
                state.turns_on_current_topic = 0
                state.topic_records[next_idx].status = "in_progress"
                action = "next_topic"
        else:
            action = "reprobe_same_level"

    state.last_eval_action = action
    return state, action


def build_interviewer_messages(
    interviewer_style: str,
    resume_markdown: str,
    job_description: str,
    repo_digest_markdown: str,
    prep_plan: PrepPlan,
    history_messages: list[dict[str, str]],
    latest_user_message: str,
    next_state: InterviewStateSnapshot,
    eval_action: str,
    eval_result: dict[str, Any],
    interview_type: str = "project_deep_dive",
) -> tuple[list[dict[str, str]], str]:
    """
    构造严格遵守静态前缀缓存铁律的完整 messages 列表：
    - messages[0]: 不可变静态前缀（人设 + 序列化工具 + 简历 + JD/Prep + Repomix）
    - messages[1..-1]: 严格追加式历史消息
    - 最后一条 user 消息尾部附加瞬态状态机指令（不修改前缀与历史消息）
    """
    static_prefix, prefix_sha = build_static_interview_prefix(
        interviewer_style=interviewer_style,
        resume_markdown=resume_markdown,
        job_description=job_description,
        repo_digest_markdown=repo_digest_markdown,
        prep_plan=prep_plan,
        tools=INTERVIEW_TOOLS_DEFINITION,
        interview_type=interview_type,
    )

    topic_idx = min(next_state.current_topic_idx, len(prep_plan.topics) - 1)
    topic = prep_plan.topics[topic_idx]
    level_label = LADDER_LABELS[next_state.ladder_level]

    action_guidance = {
        "upgrade_level": f"候选人已通过上一层级门槛，请立即升级施压进入「{level_label}」，结合切入点 `{topic.source_entrypoint}` 提出更深的单个追问。",
        "reprobe_same_level": f"候选人回答未达标（{eval_result.get('brief_diagnosis', '')}），请保持在「{level_label}」换角度追问或直接指出空洞处，不要放水切题。",
        "next_topic": f"已切换到新考点「{topic.title}」（切入点 `{topic.source_entrypoint}`），请从 {level_label} 切入提出问题：{topic.l1_seed_question}",
        "end_interview": "全部预设考点已完成或已触达收敛条件，请用面试官身份作简短专业的收尾结束语（不要给出打分）。",
    }[eval_action]

    tail_user_content = (
        f"{latest_user_message}\n\n"
        f"[状态机内部指令 — 仅本轮有效，勿复述本段]\n"
        f"动作: {eval_action} | 当前考点: {topic.title} ({topic.source_entrypoint}) | "
        f"追问层级: {level_label} | 内部诊断: {eval_result.get('brief_diagnosis', '')}\n"
        f"要求: {action_guidance}"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": static_prefix}]
    messages.extend(history_messages)
    messages.append({"role": "user", "content": tail_user_content})
    return messages, prefix_sha


def build_interview_turn_graph(runtime_cfg: AppRuntimeConfig):
    """Build LangGraph StateGraph for Slow-Loop evaluation + deterministic ladder transition."""

    async def evaluate_answer_node(state: LiveTurnGraphState) -> dict[str, Any]:
        prep_plan = state["prep_plan"]
        snap = state["state_snapshot"]
        topic = prep_plan.topics[min(snap.current_topic_idx, len(prep_plan.topics) - 1)]
        user_msg = state["latest_user_message"]

        if state.get("mock_mode") or runtime_cfg.mock_mode:
            eval_res = mock_evaluate_turn(
                topic.title,
                snap.ladder_level,
                user_msg,
                interview_type=state.get("interview_type", "project_deep_dive"),
            )
            return {"eval_result": eval_res, "eval_usage": None}

        last_ai_q = ""
        for m in reversed(state.get("history_messages") or []):
            if m.get("role") == "assistant":
                last_ai_q = m.get("content", "")
                break

        eval_prompt = (
            f"当前考点：{topic.title}（源码/项目切入点：{topic.source_entrypoint}）\n"
            f"当前追问阶梯：{LADDER_LABELS[snap.ladder_level]}\n"
            f"原子核查清单：{json.dumps(topic.atomic_checklist, ensure_ascii=False)}\n"
            f"面试官上一轮问题：{last_ai_q}\n"
            f"候选人最新回答：{user_msg}"
        )
        call_res = await chat_completion(
            runtime_cfg.live_llm,
            runtime_cfg,
            [
                {"role": "system", "content": LIVE_EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": eval_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1536,
        )
        try:
            parsed = json.loads(strip_json_fences(call_res.content))
            score = float(parsed.get("score", 0.5))
            parsed["score"] = min(1.0, max(0.0, score))
        except Exception:
            parsed = {
                "score": 0.5,
                "is_rote_memorization": False,
                "is_off_topic": False,
                "covered_points": [],
                "missing_points": ["评估解析降级"],
                "brief_diagnosis": "JSON解析回退默认分 0.5，建议追问核实。",
            }
        return {"eval_result": parsed, "eval_usage": call_res}

    def advance_ladder_node(state: LiveTurnGraphState) -> dict[str, Any]:
        next_state, action = compute_next_ladder_state(
            state["state_snapshot"], state["prep_plan"], state["eval_result"]
        )
        return {"next_state": next_state, "eval_action": action}

    def route_after_ladder(state: LiveTurnGraphState) -> Literal["closing", "questioning"]:
        return "closing" if state["eval_action"] == "end_interview" else "questioning"

    def prepare_prompt_node(state: LiveTurnGraphState) -> dict[str, Any]:
        messages, sha = build_interviewer_messages(
            interviewer_style=state["interviewer_style"],
            resume_markdown=state["resume_markdown"],
            job_description=state["job_description"],
            repo_digest_markdown=state.get("repo_digest_markdown", ""),
            prep_plan=state["prep_plan"],
            history_messages=state.get("history_messages") or [],
            latest_user_message=state["latest_user_message"],
            next_state=state["next_state"],
            eval_action=state["eval_action"],
            eval_result=state["eval_result"],
            interview_type=state.get("interview_type", "project_deep_dive"),
        )
        return {"interviewer_messages": messages, "static_prefix_sha256": sha}

    async def generate_sync_reply_node(state: LiveTurnGraphState) -> dict[str, Any]:
        next_state = state["next_state"]
        prep_plan = state["prep_plan"]
        topic = prep_plan.topics[min(next_state.current_topic_idx, len(prep_plan.topics) - 1)]
        if state.get("mock_mode") or runtime_cfg.mock_mode:
            reply = mock_interviewer_reply(
                interviewer_style=state["interviewer_style"],
                action=state["eval_action"],
                topic_title=topic.title,
                source_entrypoint=topic.source_entrypoint,
                next_ladder_level=next_state.ladder_level,
                next_seed_question=topic.l1_seed_question,
                eval_result=state["eval_result"],
                interview_type=state.get("interview_type", "project_deep_dive"),
            )
            return {"interviewer_reply": reply, "reply_usage": None}

        call_res = await chat_completion(
            runtime_cfg.live_llm,
            runtime_cfg,
            state["interviewer_messages"],
        )
        return {"interviewer_reply": call_res.content, "reply_usage": call_res}

    graph = StateGraph(LiveTurnGraphState)
    graph.add_node("evaluate_answer", evaluate_answer_node)
    graph.add_node("advance_ladder", advance_ladder_node)
    graph.add_node("prepare_questioning_prompt", prepare_prompt_node)
    graph.add_node("prepare_closing_prompt", prepare_prompt_node)
    graph.add_node("generate_sync_reply", generate_sync_reply_node)

    graph.add_edge(START, "evaluate_answer")
    graph.add_edge("evaluate_answer", "advance_ladder")
    graph.add_conditional_edges(
        "advance_ladder",
        route_after_ladder,
        {
            "questioning": "prepare_questioning_prompt",
            "closing": "prepare_closing_prompt",
        },
    )
    graph.add_edge("prepare_questioning_prompt", END)
    graph.add_edge("prepare_closing_prompt", END)

    return graph.compile()
