import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.db.models import (
    CodeSubmission,
    InterviewContext,
    InterviewSession,
    InterviewTurn,
    LLMUsageLog,
)
from app.graph.interview_graph import (
    build_interview_turn_graph,
    initialize_state_snapshot,
)
from app.graph.prep_graph import run_prep_pipeline
from app.llm.client import LLMCallResult, chat_completion, stream_chat_completion
from app.llm.mock_adapter import mock_interviewer_reply, mock_stream_text
from app.llm.prompts import INTERVIEW_TOOLS_DEFINITION, build_static_interview_prefix
from app.schemas.interview import (
    CodeSubmissionItem,
    CreateSessionRequest,
    InterviewStateSnapshot,
    SessionDetailResponse,
    SessionListItem,
    SubmitTurnRequest,
    TelemetrySummary,
    TurnResponse,
)
from app.schemas.prep import PrepPlan
from app.services.pricing import cny_to_usd, compute_cache_hit_rate
from app.services.settings_service import get_runtime_config

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _session_telemetry(row: InterviewSession) -> TelemetrySummary:
    return TelemetrySummary(
        total_prompt_tokens=row.total_prompt_tokens,
        total_cached_tokens=row.total_cached_tokens,
        total_completion_tokens=row.total_completion_tokens,
        cache_hit_rate=compute_cache_hit_rate(
            row.total_prompt_tokens, row.total_cached_tokens
        ),
        estimated_cost_cny=round(row.estimated_cost_cny, 6),
        estimated_cost_usd=cny_to_usd(row.estimated_cost_cny),
        static_prefix_sha256=row.static_prefix_sha256,
    )


def _turn_to_dto(t: InterviewTurn) -> TurnResponse:
    return TurnResponse(
        id=t.id,
        turn_index=t.turn_index,
        topic_index=t.topic_index,
        ladder_level=t.ladder_level,
        speaker=t.speaker,  # type: ignore[arg-type]
        content=t.content,
        timestamp_start_ms=t.timestamp_start_ms,
        timestamp_end_ms=t.timestamp_end_ms,
        pause_before_ms=t.pause_before_ms,
        turn_eval=t.turn_eval_json,
        tts_provider_used=t.tts_provider_used,
        stt_provider_used=t.stt_provider_used,
        created_at=t.created_at,
    )


def _code_to_dto(c: CodeSubmission) -> CodeSubmissionItem:
    return CodeSubmissionItem(
        id=c.id,
        turn_index=c.turn_index,
        topic_index=c.topic_index,
        language=c.language,
        source_code=c.source_code,
        tests_passed=c.tests_passed,
        passed_count=c.passed_count,
        total_count=c.total_count,
        test_output=c.test_output,
        exec_time_ms=c.exec_time_ms,
        created_at=c.created_at,
    )


def _session_to_detail(row: InterviewSession) -> SessionDetailResponse:
    prep = PrepPlan.model_validate(row.prep_plan_json)
    state = InterviewStateSnapshot.model_validate(row.state_snapshot_json)
    return SessionDetailResponse(
        id=row.id,
        context_id=row.context_id,
        context_title=row.context.title if row.context else "",
        interview_type=(
            row.context.interview_type if row.context and row.context.interview_type else "project_deep_dive"
        ),  # type: ignore[arg-type]
        role_track_id=row.context.role_track_id if row.context else None,
        knowledge_pack_ids=(
            list(row.context.knowledge_pack_ids_json or []) if row.context else []
        ),
        interviewer_style=row.interviewer_style,  # type: ignore[arg-type]
        interaction_mode=row.interaction_mode,  # type: ignore[arg-type]
        status=row.status,
        prep_plan=prep,
        state=state,
        telemetry=_session_telemetry(row),
        turns=[_turn_to_dto(t) for t in row.turns],
        code_submissions=[_code_to_dto(c) for c in (row.code_submissions or [])],
        has_report=row.report is not None,
        started_at=row.started_at,
        ended_at=row.ended_at,
        created_at=row.created_at,
    )


async def _load_session_with_relations(
    db: AsyncSession, session_id: str
) -> InterviewSession | None:
    return await db.scalar(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.context),
            selectinload(InterviewSession.turns),
            selectinload(InterviewSession.report),
            selectinload(InterviewSession.code_submissions),
        )
        .where(InterviewSession.id == session_id)
    )


def _record_usage(
    db: AsyncSession,
    session: InterviewSession,
    stage: str,
    base_url: str,
    res: LLMCallResult,
    prefix_sha: str = "",
) -> None:
    db.add(
        LLMUsageLog(
            session_id=session.id,
            stage=stage,
            model_name=res.model,
            base_url=base_url,
            prompt_tokens=res.prompt_tokens,
            cached_tokens=res.cached_tokens,
            completion_tokens=res.completion_tokens,
            latency_ms=res.latency_ms,
            estimated_cost_cny=res.estimated_cost_cny,
            static_prefix_sha256=prefix_sha,
        )
    )
    session.total_prompt_tokens += res.prompt_tokens
    session.total_cached_tokens += res.cached_tokens
    session.total_completion_tokens += res.completion_tokens
    session.estimated_cost_cny = round(
        session.estimated_cost_cny + res.estimated_cost_cny, 6
    )


@router.post("", response_model=SessionDetailResponse)
async def create_session(payload: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    ctx = await db.get(InterviewContext, payload.context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="指定的准备上下文不存在")

    cfg = await get_runtime_config(db)
    ctx_type = ctx.interview_type or "project_deep_dive"
    ctx_packs = list(ctx.knowledge_pack_ids_json or [])
    try:
        prep_outcome = await run_prep_pipeline(
            cfg,
            resume_markdown=ctx.resume_markdown,
            job_description=ctx.job_description,
            repo_digest_markdown=ctx.repo_digest_markdown or "",
            interviewer_style=payload.interviewer_style,
            interview_type=ctx_type,
            role_track_id=ctx.role_track_id,
            knowledge_pack_ids=ctx_packs,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Prep 预规划生成失败: {exc}") from exc

    init_state = initialize_state_snapshot(prep_outcome.plan)
    _, prefix_sha = build_static_interview_prefix(
        interviewer_style=payload.interviewer_style,
        resume_markdown=ctx.resume_markdown,
        job_description=ctx.job_description,
        repo_digest_markdown=ctx.repo_digest_markdown or "",
        prep_plan=prep_outcome.plan,
        tools=INTERVIEW_TOOLS_DEFINITION,
        interview_type=ctx_type,
    )

    now = _utcnow()
    session = InterviewSession(
        context_id=ctx.id,
        interviewer_style=payload.interviewer_style,
        interaction_mode=payload.interaction_mode,
        status="in_progress",
        prep_plan_json=prep_outcome.plan.model_dump(mode="json"),
        state_snapshot_json=init_state.model_dump(mode="json"),
        static_prefix_sha256=prefix_sha,
        started_at=now,
    )
    db.add(session)
    await db.flush()

    for u in prep_outcome.usage_records:
        _record_usage(db, session, "prep", cfg.prep_llm.base_url, u, prefix_sha)

    first_topic = prep_outcome.plan.topics[0]
    opening_question = first_topic.l1_seed_question
    db.add(
        InterviewTurn(
            session_id=session.id,
            turn_index=0,
            topic_index=0,
            ladder_level=1,
            speaker="ai",
            content=opening_question,
            timestamp_start_ms=0,
            timestamp_end_ms=0,
            pause_before_ms=0,
            tts_provider_used=cfg.voice.tts_provider,
        )
    )
    await db.commit()

    loaded = await _load_session_with_relations(db, session.id)
    return _session_to_detail(loaded)


@router.get("", response_model=list[SessionListItem])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(InterviewSession)
            .options(
                selectinload(InterviewSession.context),
                selectinload(InterviewSession.turns),
                selectinload(InterviewSession.report),
            )
            .order_by(desc(InterviewSession.created_at))
            .limit(50)
        )
    ).all()
    items: list[SessionListItem] = []
    for r in rows:
        items.append(
            SessionListItem(
                id=r.id,
                context_id=r.context_id,
                context_title=r.context.title if r.context else "",
                interview_type=(
                    r.context.interview_type if r.context and r.context.interview_type else "project_deep_dive"
                ),  # type: ignore[arg-type]
                role_track_id=r.context.role_track_id if r.context else None,
                interviewer_style=r.interviewer_style,  # type: ignore[arg-type]
                interaction_mode=r.interaction_mode,  # type: ignore[arg-type]
                status=r.status,
                total_turns=len(r.turns),
                cache_hit_rate=compute_cache_hit_rate(
                    r.total_prompt_tokens, r.total_cached_tokens
                ),
                estimated_cost_cny=round(r.estimated_cost_cny, 6),
                overall_score=r.report.overall_score if r.report else None,
                created_at=r.created_at,
            )
        )
    return items


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    row = await _load_session_with_relations(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="面试场次不存在")
    return _session_to_detail(row)


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(InterviewSession, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="面试场次不存在")
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "session_id": session_id}


@router.post("/{session_id}/finish", response_model=SessionDetailResponse)
async def finish_session(session_id: str, db: AsyncSession = Depends(get_db)):
    row = await _load_session_with_relations(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="面试场次不存在")
    snap = InterviewStateSnapshot.model_validate(row.state_snapshot_json)
    snap.phase = "completed"
    row.state_snapshot_json = snap.model_dump(mode="json")
    if row.status not in {"evaluated", "completed"}:
        row.status = "completed"
    if not row.ended_at:
        row.ended_at = _utcnow()
    await db.commit()
    await db.refresh(row)
    return _session_to_detail(row)


@router.post("/{session_id}/turns/stream")
async def submit_turn_stream(
    session_id: str, payload: SubmitTurnRequest, db: AsyncSession = Depends(get_db)
):
    session = await db.scalar(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.context),
            selectinload(InterviewSession.turns),
        )
        .where(InterviewSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="面试场次不存在")
    if session.status in {"completed", "evaluated"}:
        raise HTTPException(status_code=400, detail="当前面试场次已结束")

    cfg = await get_runtime_config(db)
    prep_plan = PrepPlan.model_validate(session.prep_plan_json)
    curr_state = InterviewStateSnapshot.model_validate(session.state_snapshot_json)

    next_turn_idx = (session.turns[-1].turn_index + 1) if session.turns else 0
    history_messages = [
        {
            "role": "assistant" if t.speaker == "ai" else "user",
            "content": (
                t.content.strip()
                or (
                    "（请继续围绕当前考点深入展开具体实现细节与边界权衡。）"
                    if t.speaker == "ai"
                    else "（空）"
                )
            ),
        }
        for t in session.turns
        if t.speaker in {"ai", "user"}
    ]

    user_turn = InterviewTurn(
        session_id=session.id,
        turn_index=next_turn_idx,
        topic_index=curr_state.current_topic_idx,
        ladder_level=curr_state.ladder_level,
        speaker="user",
        content=payload.content.strip(),
        timestamp_start_ms=payload.timestamp_start_ms,
        timestamp_end_ms=payload.timestamp_end_ms,
        pause_before_ms=payload.pause_before_ms,
        word_timestamps_json=payload.word_timestamps,
        stt_provider_used=payload.stt_provider_used,
    )
    db.add(user_turn)
    await db.flush()

    effective_user_message = payload.content.strip()
    if payload.code_snapshot is not None and payload.code_snapshot.source_code.strip():
        cs = payload.code_snapshot
        db.add(
            CodeSubmission(
                session_id=session.id,
                turn_index=next_turn_idx,
                topic_index=curr_state.current_topic_idx,
                language=cs.language,
                source_code=cs.source_code,
                tests_passed=cs.tests_passed,
                passed_count=cs.passed_count,
                total_count=cs.total_count,
                test_output=cs.test_output,
                exec_time_ms=cs.exec_time_ms,
            )
        )
        effective_user_message = (
            f"{effective_user_message}\n\n"
            f"[候选人同步提交的代码快照 ({cs.language}) 与 Pyodide 单测结果]\n"
            f"单测结果: passed={cs.tests_passed} ({cs.passed_count}/{cs.total_count}, {cs.exec_time_ms}ms)\n"
            f"```python\n{cs.source_code[:3000]}\n```\n"
            f"输出/报错: {cs.test_output[:600]}"
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        ctx_type = (
            session.context.interview_type
            if session.context and session.context.interview_type
            else "project_deep_dive"
        )
        try:
            graph = build_interview_turn_graph(cfg)
            graph_out = await graph.ainvoke(
                {
                    "session_id": session.id,
                    "interview_type": ctx_type,
                    "interviewer_style": session.interviewer_style,
                    "resume_markdown": session.context.resume_markdown,
                    "job_description": session.context.job_description,
                    "repo_digest_markdown": session.context.repo_digest_markdown or "",
                    "prep_plan": prep_plan,
                    "state_snapshot": curr_state,
                    "history_messages": history_messages,
                    "latest_user_message": effective_user_message,
                    "mock_mode": cfg.mock_mode,
                }
            )

            eval_result: dict = graph_out["eval_result"]
            next_state: InterviewStateSnapshot = graph_out["next_state"]
            eval_action: str = graph_out["eval_action"]
            prefix_sha: str = graph_out["static_prefix_sha256"]
            eval_usage: LLMCallResult | None = graph_out.get("eval_usage")

            user_turn.turn_eval_json = {**eval_result, "action": eval_action}
            if eval_usage is not None:
                _record_usage(
                    db, session, "live_eval", cfg.live_llm.base_url, eval_usage, prefix_sha
                )

            yield _format_sse(
                "state",
                {
                    "eval_result": eval_result,
                    "eval_action": eval_action,
                    "state": next_state.model_dump(mode="json"),
                    "static_prefix_sha256": prefix_sha,
                },
            )

            full_reply_chunks: list[str] = []
            reply_usage: LLMCallResult | None = None

            if cfg.mock_mode:
                topic = prep_plan.topics[
                    min(next_state.current_topic_idx, len(prep_plan.topics) - 1)
                ]
                mock_text = mock_interviewer_reply(
                    interviewer_style=session.interviewer_style,
                    action=eval_action,
                    topic_title=topic.title,
                    source_entrypoint=topic.source_entrypoint,
                    next_ladder_level=next_state.ladder_level,
                    next_seed_question=topic.l1_seed_question,
                    eval_result=eval_result,
                    interview_type=ctx_type,
                )
                async for piece in mock_stream_text(mock_text):
                    full_reply_chunks.append(piece)
                    yield _format_sse("delta", {"text": piece})
            else:
                # Note: INTERVIEW_TOOLS_DEFINITION is already frozen canonically in messages[0]
                # and structured turn evaluation ran in live_eval; omit active function-calling
                # tools here so Gemini/OpenAI streams spoken interview prose in a single RTT.
                async for chunk_ev in stream_chat_completion(
                    cfg.live_llm,
                    cfg,
                    graph_out["interviewer_messages"],
                    tools=None,
                ):
                    if chunk_ev["type"] == "delta":
                        full_reply_chunks.append(chunk_ev["text"])
                        yield _format_sse("delta", {"text": chunk_ev["text"]})
                    elif chunk_ev["type"] == "done":
                        reply_usage = chunk_ev["result"]

                # Non-streaming real-LLM retry if upstream stream ended without visible text
                if not "".join(full_reply_chunks).strip():
                    retry_msgs = list(graph_out["interviewer_messages"]) + [
                        {
                            "role": "user",
                            "content": "请直接用中文向候选人说出你本轮要追问的具体问题，不要输出空白或调用任何工具。",
                        }
                    ]
                    fallback_res = await chat_completion(
                        cfg.live_llm,
                        cfg,
                        retry_msgs,
                        tools=None,
                        max_tokens=max(2048, cfg.live_llm.max_tokens),
                    )
                    if fallback_res.content:
                        full_reply_chunks.append(fallback_res.content)
                        yield _format_sse("delta", {"text": fallback_res.content})
                        reply_usage = fallback_res

            ai_text = "".join(full_reply_chunks).strip()
            if not ai_text:
                # Absolute non-empty guard so no blank interviewer bubble is ever stored
                topic = prep_plan.topics[
                    min(next_state.current_topic_idx, len(prep_plan.topics) - 1)
                ]
                ai_text = mock_interviewer_reply(
                    interviewer_style=session.interviewer_style,
                    action=eval_action,
                    topic_title=topic.title,
                    source_entrypoint=topic.source_entrypoint,
                    next_ladder_level=next_state.ladder_level,
                    next_seed_question=topic.l1_seed_question,
                    eval_result=eval_result,
                    interview_type=ctx_type,
                )
                yield _format_sse("delta", {"text": ai_text})
            if reply_usage is not None:
                _record_usage(
                    db, session, "live_reply", cfg.live_llm.base_url, reply_usage, prefix_sha
                )

            if eval_action == "end_interview":
                next_state.phase = "completed"
                session.status = "completed"
                session.ended_at = _utcnow()

            session.state_snapshot_json = next_state.model_dump(mode="json")

            ai_turn = InterviewTurn(
                session_id=session.id,
                turn_index=next_turn_idx + 1,
                topic_index=next_state.current_topic_idx,
                ladder_level=next_state.ladder_level,
                speaker="ai",
                content=ai_text,
                timestamp_start_ms=payload.timestamp_end_ms,
                timestamp_end_ms=payload.timestamp_end_ms,
                pause_before_ms=0,
                tts_provider_used=cfg.voice.tts_provider,
            )
            db.add(ai_turn)
            await db.commit()
            await db.refresh(ai_turn)

            yield _format_sse(
                "done",
                {
                    "ai_turn": _turn_to_dto(ai_turn).model_dump(mode="json"),
                    "user_turn": _turn_to_dto(user_turn).model_dump(mode="json"),
                    "state": next_state.model_dump(mode="json"),
                    "session_status": session.status,
                    "telemetry": _session_telemetry(session).model_dump(mode="json"),
                },
            )
        except Exception as exc:
            await db.rollback()
            yield _format_sse("error", {"message": str(exc)[:400]})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
