import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppRuntimeConfig
from app.db.models import EvaluationReport, InterviewSession, MistakeItem, MistakeRetry
from app.llm.client import chat_completion, strip_json_fences
from app.llm.mock_adapter import mock_mistake_retry_eval
from app.schemas.evaluation import JudgeLLMOutput
from app.schemas.prep import PrepPlan


async def sync_mistakes_from_evaluation(
    db: AsyncSession,
    session: InterviewSession,
    prep_plan: PrepPlan,
    judge_output: JudgeLLMOutput,
    turns: list[dict],
) -> list[MistakeItem]:
    """
    将本场表现低于阈值（< 70 分或单轮 < 0.65 或连续失败切题）的考点沉淀至错题本。
    按 (session_id, topic_index) 去重，支持重复评判时幂等更新。
    """
    state_snap = session.state_snapshot_json or {}
    topic_records = {
        str(r.get("topic_id")): r for r in (state_snap.get("topic_records") or [])
    }

    existing_rows = (
        await db.scalars(
            select(MistakeItem).where(MistakeItem.session_id == session.id)
        )
    ).all()
    existing_by_topic = {row.topic_index: row for row in existing_rows}

    annotations_by_turn = {
        a.turn_index: a for a in judge_output.transcript_annotations
    }
    user_turns = [t for t in turns if t.get("speaker") == "user"]
    ai_turns = [t for t in turns if t.get("speaker") == "ai"]

    candidate_topics: list[tuple[int, float, dict]] = []
    for idx, topic in enumerate(prep_plan.topics):
        t_user = [t for t in user_turns if int(t.get("topic_index", -1)) == idx]
        if not t_user:
            continue
        scores = [float((t.get("turn_eval") or {}).get("score", 0.5)) for t in t_user]
        avg_score_100 = round((sum(scores) / len(scores)) * 100.0, 1)
        min_turn = min(t_user, key=lambda x: float((x.get("turn_eval") or {}).get("score", 0.5)))
        rec = topic_records.get(topic.topic_id, {})
        failed_topic = rec.get("status") == "failed_moved_on"
        has_low_turn = any(s < 0.65 for s in scores)
        if failed_topic or has_low_turn or avg_score_100 < 70.0:
            candidate_topics.append((idx, avg_score_100, min_turn))

    if (
        not candidate_topics
        and judge_output.overall_score is not None
        and judge_output.overall_score < 70.0
        and user_turns
    ):
        worst = min(
            user_turns, key=lambda x: float((x.get("turn_eval") or {}).get("score", 0.5))
        )
        t_idx = int(worst.get("topic_index", 0))
        candidate_topics.append((t_idx, float(judge_output.overall_score), worst))

    saved: list[MistakeItem] = []
    for t_idx, orig_score, target_turn in candidate_topics:
        topic = prep_plan.topics[min(t_idx, len(prep_plan.topics) - 1)]
        turn_idx = int(target_turn.get("turn_index", 0))
        matching_ai = [
            a for a in ai_turns if int(a.get("turn_index", 0)) < turn_idx
        ]
        question_prompt = (
            str(matching_ai[-1].get("content", ""))
            if matching_ai
            else topic.l1_seed_question
        )
        ann = annotations_by_turn.get(turn_idx)
        ideal_rewrite = (
            ann.ideal_rewrite
            if ann
            else (
                f"针对「{topic.title}」（{topic.source_entrypoint}），建议从核心原理、项目落地参数、"
                "并发锁/一致性控制及极端故障降级四个层次作结构化回答。"
            )
        )

        row = existing_by_topic.get(t_idx)
        if row is None:
            row = MistakeItem(
                session_id=session.id,
                topic_index=t_idx,
                topic_title=topic.title,
                source_entrypoint=topic.source_entrypoint,
                question_prompt=question_prompt,
                original_answer=str(target_turn.get("content", "")),
                original_score=orig_score,
                atomic_checklist_json=list(topic.atomic_checklist),
                ideal_rewrite=ideal_rewrite,
                status="open",
            )
            db.add(row)
        else:
            row.question_prompt = question_prompt
            row.original_answer = str(target_turn.get("content", ""))
            row.original_score = orig_score
            row.ideal_rewrite = ideal_rewrite
        saved.append(row)

    return saved


async def evaluate_mistake_retry(
    runtime_cfg: AppRuntimeConfig,
    mistake: MistakeItem,
    retry_answer: str,
) -> dict:
    checklist = list(mistake.atomic_checklist_json or [])
    if runtime_cfg.mock_mode:
        return mock_mistake_retry_eval(mistake.topic_title, checklist, retry_answer)

    prompt = (
        "你是一位严苛的技术面试单题重录裁判。\n"
        f"考点：{mistake.topic_title}（切入点：{mistake.source_entrypoint}）\n"
        f"面试问题：{mistake.question_prompt}\n"
        f"原子核查清单：{json.dumps(checklist, ensure_ascii=False)}\n"
        f"历史原回答（原分 {mistake.original_score}）：{mistake.original_answer}\n"
        f"本次重录新回答：{retry_answer}\n\n"
        "请只返回合法 JSON：\n"
        '{"retry_score": 0-100浮点数, "newly_passed_checklist": ["新达标的核查项原文"], "feedback": "不超过120字的具体对比评语"}'
    )
    call_res = await chat_completion(
        runtime_cfg.judge_llm,
        runtime_cfg,
        [
            {"role": "system", "content": "只输出合法 JSON，不输出多余说明。"},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1024,
    )
    parsed = json.loads(strip_json_fences(call_res.content))
    score_val = round(min(100.0, max(0.0, float(parsed.get("retry_score", 60.0)))), 1)
    return {
        "retry_score": score_val,
        "newly_passed_checklist": list(parsed.get("newly_passed_checklist") or []),
        "feedback": str(parsed.get("feedback") or "已完成重录评分。"),
    }
