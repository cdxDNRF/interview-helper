from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.db.models import InterviewSession, LLMUsageLog
from app.schemas.observability import (
    ObservabilityOverviewResponse,
    SessionObservabilityResponse,
    SessionTrendPoint,
    StageBreakdownItem,
    UsageLogEntry,
)
from app.services.pricing import compute_cache_hit_rate

router = APIRouter(prefix="/api/observability", tags=["observability"])


def _aggregate_stages(logs: list[LLMUsageLog]) -> list[StageBreakdownItem]:
    grouped: dict[str, list[LLMUsageLog]] = defaultdict(list)
    for log in logs:
        grouped[log.stage].append(log)

    items: list[StageBreakdownItem] = []
    for stage, group in sorted(grouped.items()):
        latencies = sorted(g.latency_ms for g in group)
        p95_idx = min(len(latencies) - 1, max(0, int(len(latencies) * 0.95) - 1))
        items.append(
            StageBreakdownItem(
                stage=stage,
                call_count=len(group),
                prompt_tokens=sum(g.prompt_tokens for g in group),
                cached_tokens=sum(g.cached_tokens for g in group),
                completion_tokens=sum(g.completion_tokens for g in group),
                avg_latency_ms=round(sum(latencies) / len(latencies), 1),
                p95_latency_ms=latencies[p95_idx],
                estimated_cost_cny=round(sum(g.estimated_cost_cny for g in group), 6),
            )
        )
    return items


@router.get("/overview", response_model=ObservabilityOverviewResponse)
async def get_observability_overview(db: AsyncSession = Depends(get_db)):
    sessions = (
        await db.scalars(
            select(InterviewSession)
            .options(
                selectinload(InterviewSession.context),
                selectinload(InterviewSession.usage_logs),
                selectinload(InterviewSession.report),
            )
            .order_by(asc(InterviewSession.created_at))
            .limit(50)
        )
    ).all()
    all_logs = (
        await db.scalars(select(LLMUsageLog).order_by(desc(LLMUsageLog.id)).limit(500))
    ).all()

    total_prompt = sum(l.prompt_tokens for l in all_logs)
    total_cached = sum(l.cached_tokens for l in all_logs)
    total_cost = round(sum(l.estimated_cost_cny for l in all_logs), 6)
    avg_lat = (
        round(sum(l.latency_ms for l in all_logs) / len(all_logs), 1)
        if all_logs
        else 0.0
    )

    trends: list[SessionTrendPoint] = []
    for s in sessions:
        s_lat = (
            round(sum(l.latency_ms for l in s.usage_logs) / len(s.usage_logs), 1)
            if s.usage_logs
            else 0.0
        )
        s_prompt = s.total_prompt_tokens or sum(l.prompt_tokens for l in s.usage_logs)
        s_cached = s.total_cached_tokens or sum(l.cached_tokens for l in s.usage_logs)
        s_cost = s.estimated_cost_cny or sum(l.estimated_cost_cny for l in s.usage_logs)
        trends.append(
            SessionTrendPoint(
                session_id=s.id,
                context_title=s.context.title if s.context else s.id[:8],
                cache_hit_rate=compute_cache_hit_rate(s_prompt, s_cached),
                estimated_cost_cny=round(s_cost, 6),
                avg_latency_ms=s_lat,
                overall_score=s.report.overall_score if s.report else None,
                created_at=s.created_at,
            )
        )

    return ObservabilityOverviewResponse(
        total_sessions=len(sessions),
        total_llm_calls=len(all_logs),
        avg_cache_hit_rate=compute_cache_hit_rate(total_prompt, total_cached),
        total_cost_cny=total_cost,
        avg_latency_ms=avg_lat,
        stage_breakdown=_aggregate_stages(all_logs),
        session_trends=trends,
    )


@router.get("/sessions/{session_id}", response_model=SessionObservabilityResponse)
async def get_session_observability(session_id: str, db: AsyncSession = Depends(get_db)):
    sess = await db.scalar(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.context),
            selectinload(InterviewSession.usage_logs),
        )
        .where(InterviewSession.id == session_id)
    )
    if not sess:
        raise HTTPException(status_code=404, detail="面试场次不存在")

    logs = list(sess.usage_logs)
    seen_hashes = {l.static_prefix_sha256 for l in logs if l.static_prefix_sha256}
    prefix_consistent = len(seen_hashes) <= 1

    return SessionObservabilityResponse(
        session_id=sess.id,
        context_title=sess.context.title if sess.context else "",
        static_prefix_sha256=sess.static_prefix_sha256,
        prefix_consistent=prefix_consistent,
        cache_hit_rate=compute_cache_hit_rate(
            sess.total_prompt_tokens, sess.total_cached_tokens
        ),
        total_cost_cny=round(sess.estimated_cost_cny, 6),
        stage_breakdown=_aggregate_stages(logs),
        logs=[
            UsageLogEntry(
                id=l.id,
                stage=l.stage,
                model_name=l.model_name,
                prompt_tokens=l.prompt_tokens,
                cached_tokens=l.cached_tokens,
                completion_tokens=l.completion_tokens,
                cache_hit_rate=compute_cache_hit_rate(l.prompt_tokens, l.cached_tokens),
                latency_ms=l.latency_ms,
                estimated_cost_cny=round(l.estimated_cost_cny, 6),
                static_prefix_sha256=l.static_prefix_sha256,
                created_at=l.created_at,
            )
            for l in logs
        ],
    )
