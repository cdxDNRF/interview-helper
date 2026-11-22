from datetime import datetime
from pydantic import BaseModel, Field

from app.packs.schemas import InterviewType


class ContextResponse(BaseModel):
    id: str
    title: str
    interview_type: InterviewType = "project_deep_dive"
    role_track_id: str | None = None
    knowledge_pack_ids: list[str] = Field(default_factory=list)
    resume_filename: str
    resume_markdown: str
    job_description: str
    github_repo_url: str | None = None
    repo_digest_markdown: str | None = None
    repo_token_count: int = 0
    repo_warnings: list[str] = Field(default_factory=list)
    created_at: datetime


class ContextSummary(BaseModel):
    id: str
    title: str
    interview_type: InterviewType = "project_deep_dive"
    role_track_id: str | None = None
    knowledge_pack_ids: list[str] = Field(default_factory=list)
    resume_filename: str
    github_repo_url: str | None = None
    repo_token_count: int = 0
    created_at: datetime
