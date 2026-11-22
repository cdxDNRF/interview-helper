import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import InterviewContext
from app.packs.registry import collect_seed_topics_and_hotwords, get_role_track
from app.schemas.context import ContextResponse, ContextSummary
from app.services.context_builder import (
    pack_github_repo_with_repomix,
    parse_resume_bytes,
)

router = APIRouter(prefix="/api/contexts", tags=["contexts"])

_VALID_TYPES = {
    "project_deep_dive",
    "general_behavioral",
    "cs_role_track",
    "bagu_fundamentals",
}


def _parse_pack_ids(raw: str) -> list[str]:
    clean = (raw or "").strip()
    if not clean:
        return []
    if clean.startswith("["):
        try:
            loaded = json.loads(clean)
            if isinstance(loaded, list):
                return [str(x).strip() for x in loaded if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in clean.split(",") if part.strip()]


def _to_response(row: InterviewContext) -> ContextResponse:
    return ContextResponse(
        id=row.id,
        title=row.title,
        interview_type=row.interview_type or "project_deep_dive",  # type: ignore[arg-type]
        role_track_id=row.role_track_id,
        knowledge_pack_ids=list(row.knowledge_pack_ids_json or []),
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
    interview_type: str = Form(default="project_deep_dive"),
    role_track_id: str = Form(default=""),
    knowledge_pack_ids: str = Form(default=""),
    job_description: str = Form(default=""),
    resume_text: str = Form(default=""),
    github_repo_url: str = Form(default=""),
    resume_file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    if interview_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的面试模式: {interview_type}")

    parsed_pack_ids = _parse_pack_ids(knowledge_pack_ids)
    clean_role_id = role_track_id.strip() or None

    warnings: list[str] = []
    resume_filename = "pasted-resume.md" if resume_text.strip() else ""
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

    jd_text = job_description.strip()
    if interview_type == "project_deep_dive":
        if not resume_md:
            raise HTTPException(status_code=400, detail="项目深挖模式请上传简历文件或粘贴简历文本")
        if not jd_text:
            raise HTTPException(status_code=400, detail="项目深挖模式请填写目标岗位 JD")
    else:
        preset_desc, _, _ = collect_seed_topics_and_hotwords(
            interview_type, clean_role_id, parsed_pack_ids
        )
        if not resume_md:
            resume_filename = "preset-no-resume"
            resume_md = "（免简历专项模式：候选人未附加个人简历，请直接聚焦选定的面试方向与核心考点进行 L1–L4 深挖考察。）"
        if not jd_text:
            jd_text = preset_desc
        elif preset_desc:
            jd_text = f"{preset_desc}\n\n[补充目标 JD]\n{jd_text}"

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

    if title.strip():
        auto_title = title.strip()
    elif interview_type == "cs_role_track":
        role = get_role_track(clean_role_id)
        auto_title = f"职业专项 · {role.name if role else '计算机工程'}"
    elif interview_type == "bagu_fundamentals":
        auto_title = f"八股突击 · {', '.join(parsed_pack_ids) or 'CS 核心基础'}"
    elif interview_type == "general_behavioral":
        auto_title = "通用综合面试 (STAR)"
    elif repo_url:
        auto_title = f"面试准备 - {repo_url.split('/')[-1]}"
    else:
        auto_title = f"面试准备 - {resume_filename}"

    row = InterviewContext(
        title=auto_title[:200],
        interview_type=interview_type,
        role_track_id=clean_role_id,
        knowledge_pack_ids_json=parsed_pack_ids,
        resume_filename=resume_filename,
        resume_markdown=resume_md,
        job_description=jd_text,
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
            interview_type=r.interview_type or "project_deep_dive",  # type: ignore[arg-type]
            role_track_id=r.role_track_id,
            knowledge_pack_ids=list(r.knowledge_pack_ids_json or []),
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
