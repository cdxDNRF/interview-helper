from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import InterviewContext
from app.schemas.context import ContextResponse, ContextSummary
from app.services.context_builder import (
    pack_github_repo_with_repomix,
    parse_resume_bytes,
)

router = APIRouter(prefix="/api/contexts", tags=["contexts"])


def _to_response(row: InterviewContext) -> ContextResponse:
    return ContextResponse(
        id=row.id,
        title=row.title,
        resume_filename=row.resume_filename,
        resume_markdown=row.resume_markdown,
        job_description=row.job_description,
        github_repo_url=row.github_repo_url,
        repo_digest_markdown=row.repo_digest_markdown,
        repo_token_count=row.repo_token_count,
        repo_warnings=list(row.repo_warnings_json or []),
        created_at=row.created_at,
    )


@router.post("", response_model=ContextResponse)
async def create_context(
    title: str = Form(default=""),
    job_description: str = Form(...),
    resume_text: str = Form(default=""),
    github_repo_url: str = Form(default=""),
    resume_file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    warnings: list[str] = []
    resume_filename = "pasted-resume.md"
    resume_md = resume_text.strip()

    if resume_file is not None and resume_file.filename:
        raw_bytes = await resume_file.read()
        if len(raw_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="简历文件大小不能超过 10MB")
        try:
            parsed_md, parse_warnings = parse_resume_bytes(resume_file.filename, raw_bytes)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"简历解析失败: {exc}") from exc
        resume_filename = resume_file.filename
        if parsed_md:
            resume_md = parsed_md
        warnings.extend(parse_warnings)

    if not resume_md:
        raise HTTPException(status_code=400, detail="请上传简历文件或直接粘贴简历 Markdown 文本")
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="请填写目标岗位 JD")

    repo_url = github_repo_url.strip() or None
    repo_digest: str | None = None
    repo_tokens = 0
    if repo_url:
        try:
            repo_digest, repo_tokens, repo_warnings = await pack_github_repo_with_repomix(repo_url)
            warnings.extend(repo_warnings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"GitHub 仓库处理失败: {exc}") from exc

    auto_title = title.strip() or (
        f"面试准备 - {repo_url.split('/')[-1]}" if repo_url else f"面试准备 - {resume_filename}"
    )

    row = InterviewContext(
        title=auto_title[:200],
        resume_filename=resume_filename,
        resume_markdown=resume_md,
        job_description=job_description.strip(),
        github_repo_url=repo_url,
        repo_digest_markdown=repo_digest,
        repo_token_count=repo_tokens,
        repo_warnings_json=warnings,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.get("", response_model=list[ContextSummary])
async def list_contexts(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(InterviewContext).order_by(desc(InterviewContext.created_at)).limit(30)
        )
    ).all()
    return [
        ContextSummary(
            id=r.id,
            title=r.title,
            resume_filename=r.resume_filename,
            github_repo_url=r.github_repo_url,
            repo_token_count=r.repo_token_count,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{context_id}", response_model=ContextResponse)
async def get_context(context_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(InterviewContext, context_id)
    if not row:
        raise HTTPException(status_code=404, detail="准备上下文不存在")
    return _to_response(row)
