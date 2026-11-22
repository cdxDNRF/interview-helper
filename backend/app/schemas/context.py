from datetime import datetime
from pydantic import BaseModel, Field


class ContextResponse(BaseModel):
    id: str
    title: str
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
    resume_filename: str
    github_repo_url: str | None = None
    repo_token_count: int = 0
    created_at: datetime
