from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.db.models import EvaluationReport, InterviewSession, LLMUsageLog
from app.schemas.evaluation import (
    ChecklistOutcome,
    EvaluationReportResponse,
    FourDimensionsSchema,
    SpeechMetrics,
    TranscriptAnnotation,
)
from app.schemas.prep import PrepPlan
from app.services.judge_service import run_post_interview_judge
from app.services.settings_service import get_runtime_config
from app.services.speech_metrics import compute_speech_metrics

router = APIRouter(prefix="/api/sessions", tags=["reports"])


def _report_to_dto(row: EvaluationReport) -> EvaluationReportResponse:
    return EvaluationReportResponse(
        id=row.id,
        session_id=row.session_id,
        judge_model=row.judge_model,
        overall_score=row.overall_score,
        dimensions=FourDimensionsSchema.model_validate(row.dimensions_json),
        checklist_results=[
            ChecklistOutcome.model_validate(item) for item in (row.checklist_results_json or [])
        ],
        transcript_annotations=[
            TranscriptAnnotation.model_validate(item)
            for item in (row.transcript_annotations_json or [])
        ],
        speech_metrics=SpeechMetrics.model_validate(row.speech_metrics_json),
        summary_markdown=row.summary_markdown,
        raw_retry_count=row.raw_retry_count,
        created_at=row.created_at,
    )


@router.post("/{session_id}/evaluate", response_model=EvaluationReportResponse)
async def evaluate_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.scalar(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.context),
            selectinload(InterviewSession.turns),
            selectinload(InterviewSession.report),
        )
        .where(InterviewSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="面试场次不存在")

    cfg = await get_runtime_config(db)
    prep_plan = PrepPlan.model_validate(session.prep_plan_json)
    turns_dicts = [
        {
            "turn_index": t.turn_index,
            "topic_index": t.topic_index,
            "ladder_level": t.ladder_level,
            "speaker": t.speaker,
            "content": t.content,
            "timestamp_start_ms": t.timestamp_start_ms,
            "timestamp_end_ms": t.timestamp_end_ms,
            "pause_before_ms": t.pause_before_ms,
            "word_timestamps": t.word_timestamps_json,
            "turn_eval": t.turn_eval_json,
        }
        for t in session.turns
    ]

    speech_metrics = compute_speech_metrics(turns_dicts)

    try:
        outcome = await run_post_interview_judge(
            cfg,
            prep_plan=prep_plan,
            turns=turns_dicts,
            state_snapshot=session.state_snapshot_json or {},
            resume_markdown=session.context.resume_markdown,
            job_description=session.context.job_description,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"赛后裁判评估失败: {exc}") from exc

    for u in outcome.usage_records:
        db.add(
            LLMUsageLog(
                session_id=session.id,
                stage="judge",
                model_name=u.model,
                base_url=cfg.judge_llm.base_url,
                prompt_tokens=u.prompt_tokens,
                cached_tokens=u.cached_tokens,
                completion_tokens=u.completion_tokens,
                latency_ms=u.latency_ms,
                estimated_cost_cny=u.estimated_cost_cny,
                static_prefix_sha256=session.static_prefix_sha256,
            )
        )
        session.total_prompt_tokens += u.prompt_tokens
        session.total_cached_tokens += u.cached_tokens
        session.total_completion_tokens += u.completion_tokens
        session.estimated_cost_cny = round(
            session.estimated_cost_cny + u.estimated_cost_cny, 6
        )

    rep = session.report
    if rep is None:
        rep = EvaluationReport(session_id=session.id)
        db.add(rep)

    rep.judge_model = outcome.model_used
    rep.overall_score = outcome.report.overall_score
    rep.dimensions_json = outcome.report.dimensions.model_dump(mode="json")
    rep.checklist_results_json = [
        c.model_dump(mode="json") for c in outcome.report.checklist_results
    ]
    rep.transcript_annotations_json = [
        a.model_dump(mode="json") for a in outcome.report.transcript_annotations
    ]
    rep.speech_metrics_json = speech_metrics.model_dump(mode="json")
    rep.summary_markdown = outcome.report.summary_markdown
    rep.raw_retry_count = outcome.retry_count
    session.status = "evaluated"

    await db.commit()
    await db.refresh(rep)
    return _report_to_dto(rep)


@router.get("/{session_id}/report", response_model=EvaluationReportResponse)
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    rep = await db.scalar(
        select(EvaluationReport).where(EvaluationReport.session_id == session_id)
    )
    if not rep:
        raise HTTPException(status_code=404, detail="该场次尚未生成复盘报告")
    return _report_to_dto(rep)


@router.get("/{session_id}/report/export", response_class=PlainTextResponse)
async def export_report_markdown(session_id: str, db: AsyncSession = Depends(get_db)):
    rep = await db.scalar(
        select(EvaluationReport).where(EvaluationReport.session_id == session_id)
    )
    if not rep:
        raise HTTPException(status_code=404, detail="该场次尚未生成复盘报告")
    dto = _report_to_dto(rep)

    dim_labels = [
        ("技术原理深度", dto.dimensions.technical_depth),
        ("工程权衡与边界意识", dto.dimensions.engineering_tradeoffs),
        ("问题拆解与表达结构", dto.dimensions.problem_structuring),
        ("代码实现与自测意识", dto.dimensions.code_and_testing),
    ]

    lines = [
        f"# AI 模拟面试复盘报告 ({dto.session_id})",
        f"- 裁判模型：`{dto.judge_model}`（校验重试 {dto.raw_retry_count} 次）",
        f"- 综合得分：**{dto.overall_score if dto.overall_score is not None else 'N/A'}**",
        "",
        "## 一、确定性语音表达指标",
        f"- 语速：**{dto.speech_metrics.chars_per_min}** 字(词)/分钟",
        f"- 最长冷场停顿：**{dto.speech_metrics.longest_silence_sec}** 秒",
        f"- 填充词总频次：**{dto.speech_metrics.total_filler_count}** 次",
        "",
        "## 二、四维评估（先证据后分数）",
    ]
    for title, d in dim_labels:
        score_str = str(d.score) if d.score is not None else "N/A (未充分考察)"
        lines.append(f"### {title}：{score_str}")
        lines.append(f"- 推理：{d.reasoning}")
        for q in d.evidence_quotes:
            lines.append(f"  - 原句 [Turn {q.turn_index}]: “{q.quote}” — {q.relevance}")
    lines.append("")
    lines.append("## 三、原话 vs 满分重构对比")
    for ann in dto.transcript_annotations:
        lines.append(f"### Turn {ann.turn_index} · {ann.topic_title} (L{ann.ladder_level})")
        lines.append(f"- 批注：{ann.critique}")
        lines.append(f"- 原话：{ann.original_utterance}")
        lines.append(f"- 满分重构版：{ann.ideal_rewrite}")
    lines.append("")
    lines.append("## 四、总结建议")
    lines.append(dto.summary_markdown)
    return "\n".join(lines)
