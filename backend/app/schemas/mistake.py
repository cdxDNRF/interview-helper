from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class MistakeRetryRequest(BaseModel):
    retry_answer: str = Field(min_length=1)
    duration_sec: int = Field(default=0, ge=0)


class MistakeRetryRecord(BaseModel):
    id: int
    retry_answer: str
    duration_sec: int
    retry_score: float
    newly_passed_checklist: list[str] = Field(default_factory=list)
    feedback: str
    created_at: datetime


class MistakeItemResponse(BaseModel):
    id: str
    session_id: str
    context_title: str = ""
    topic_index: int
    topic_title: str
    source_entrypoint: str
    question_prompt: str
    original_answer: str
    original_score: float
    best_retry_score: float | None = None
    score_delta: float | None = None
    atomic_checklist: list[str] = Field(default_factory=list)
    ideal_rewrite: str
    status: Literal["open", "mastered"]
    retry_count: int = 0
    retries: list[MistakeRetryRecord] = Field(default_factory=list)
    created_at: datetime
