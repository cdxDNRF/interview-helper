from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.db.models import InterviewSession, MistakeItem, MistakeRetry
from app.schemas.mistake import (
    MistakeItemResponse,
    MistakeRetryRecord,
    MistakeRetryRequest,
)
from app.services.mistake_service import evaluate_mistake_retry
from app.services.settings_service import get_runtime_config

router = APIRouter(prefix="/api/mistakes", tags=["mistakes"])


def _to_dto(item: MistakeItem) -> MistakeItemResponse:
    best = item.best_retry_score
    delta = round(best - item.original_score, 1) if best is not None else None
    return MistakeItemResponse(
        id=item.id,
        session_id=item.session_id,
        context_title=(
            item.session.context.title
            if item.session and item.session.context
            else ""
        ),
        topic_index=item.topic_index,
        topic_title=item.topic_title,
        source_entrypoint=item.source_entrypoint,
        question_prompt=item.question_prompt,
        original_answer=item.original_answer,
        original_score=item.original_score,
        best_retry_score=best,
        score_delta=delta,
        atomic_checklist=list(item.atomic_checklist_json or []),
        ideal_rewrite=item.ideal_rewrite,
        status=item.status,  # type: ignore[arg-type]
        retry_count=len(item.retries),
        retries=[
            MistakeRetryRecord(
                id=r.id,
                retry_answer=r.retry_answer,
                duration_sec=r.duration_sec,
                retry_score=r.retry_score,
                newly_passed_checklist=list(r.newly_passed_checklist_json or []),
                feedback=r.feedback,
                created_at=r.created_at,
            )
            for r in item.retries
        ],
        created_at=item.created_at,
    )


@router.get("", response_model=list[MistakeItemResponse])
async def list_mistakes(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MistakeItem)
        .options(
            selectinload(MistakeItem.retries),
            selectinload(MistakeItem.session).selectinload(InterviewSession.context),
        )
        .order_by(desc(MistakeItem.created_at))
    )
    if status in {"open", "mastered"}:
        stmt = stmt.where(MistakeItem.status == status)
    rows = (await db.scalars(stmt.limit(100))).all()
    return [_to_dto(r) for r in rows]


@router.get("/{mistake_id}", response_model=MistakeItemResponse)
async def get_mistake(mistake_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.scalar(
        select(MistakeItem)
        .options(
            selectinload(MistakeItem.retries),
            selectinload(MistakeItem.session).selectinload(InterviewSession.context),
        )
        .where(MistakeItem.id == mistake_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    return _to_dto(row)


@router.post("/{mistake_id}/retry", response_model=MistakeItemResponse)
async def retry_mistake(
    mistake_id: str, payload: MistakeRetryRequest, db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(
        select(MistakeItem)
        .options(
            selectinload(MistakeItem.retries),
            selectinload(MistakeItem.session).selectinload(InterviewSession.context),
        )
        .where(MistakeItem.id == mistake_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    cfg = await get_runtime_config(db)
    try:
        eval_out = await evaluate_mistake_retry(cfg, row, payload.retry_answer.strip())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"重录评分失败: {exc}") from exc

    retry_score = float(eval_out["retry_score"])
    db.add(
        MistakeRetry(
            mistake_id=row.id,
            retry_answer=payload.retry_answer.strip(),
            duration_sec=payload.duration_sec,
            retry_score=retry_score,
            newly_passed_checklist_json=list(eval_out.get("newly_passed_checklist") or []),
            feedback=str(eval_out.get("feedback") or ""),
        )
    )

    if row.best_retry_score is None or retry_score > row.best_retry_score:
        row.best_retry_score = retry_score
    if retry_score >= 75.0:
        row.status = "mastered"

    await db.commit()
    refreshed = await db.scalar(
        select(MistakeItem)
        .options(
            selectinload(MistakeItem.retries),
            selectinload(MistakeItem.session).selectinload(InterviewSession.context),
        )
        .execution_options(populate_existing=True)
        .where(MistakeItem.id == mistake_id)
    )
    return _to_dto(refreshed)
