from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from app.packs.schemas import InterviewType
from app.schemas.prep import PrepPlan


InterviewerStyle = Literal["gentle", "pressure"]
InteractionMode = Literal["voice", "text"]
LadderLevel = Literal[1, 2, 3, 4]


class TopicRecord(BaseModel):
    topic_id: str
    title: str
    status: Literal["pending", "in_progress", "mastered", "failed_moved_on"] = "pending"
    max_level_reached: int = 1
    turns_spent: int = 0


class InterviewStateSnapshot(BaseModel):
    current_topic_idx: int = 0
    ladder_level: LadderLevel = 1
    consecutive_fail_count: int = 0
    turns_on_current_topic: int = 0
    phase: Literal["opening", "questioning", "closing", "completed"] = "questioning"
    topic_records: list[TopicRecord] = Field(default_factory=list)
    last_eval_score: float | None = None
    last_eval_action: str = ""


class CreateSessionRequest(BaseModel):
    context_id: str
    interviewer_style: InterviewerStyle = "gentle"
    interaction_mode: InteractionMode = "voice"


class CodeSnapshotPayload(BaseModel):
    language: str = "python"
    source_code: str = ""
    tests_passed: bool = False
    passed_count: int = 0
    total_count: int = 0
    test_output: str = ""
    exec_time_ms: int = 0


class CodeSubmissionItem(CodeSnapshotPayload):
    id: int
    turn_index: int
    topic_index: int
    created_at: datetime


class SubmitTurnRequest(BaseModel):
    content: str = Field(min_length=1)
    timestamp_start_ms: int = 0
    timestamp_end_ms: int = 0
    pause_before_ms: int = 0
    word_timestamps: list[dict] | None = None
    stt_provider_used: str = "text"
    code_snapshot: CodeSnapshotPayload | None = None


class TurnResponse(BaseModel):
    id: int
    turn_index: int
    topic_index: int
    ladder_level: int
    speaker: Literal["ai", "user", "system"]
    content: str
    timestamp_start_ms: int
    timestamp_end_ms: int
    pause_before_ms: int
    turn_eval: dict | None = None
    tts_provider_used: str | None = None
    stt_provider_used: str | None = None
    created_at: datetime


class TelemetrySummary(BaseModel):
    total_prompt_tokens: int
    total_cached_tokens: int
    total_completion_tokens: int
    cache_hit_rate: float
    estimated_cost_cny: float
    estimated_cost_usd: float
    static_prefix_sha256: str


class SessionDetailResponse(BaseModel):
    id: str
    context_id: str
    context_title: str
    interview_type: InterviewType = "project_deep_dive"
    role_track_id: str | None = None
    knowledge_pack_ids: list[str] = Field(default_factory=list)
    interviewer_style: InterviewerStyle
    interaction_mode: InteractionMode
    status: str
    prep_plan: PrepPlan
    state: InterviewStateSnapshot
    telemetry: TelemetrySummary
    turns: list[TurnResponse]
    code_submissions: list[CodeSubmissionItem] = Field(default_factory=list)
    has_report: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime


class SessionListItem(BaseModel):
    id: str
    context_id: str
    context_title: str
    interview_type: InterviewType = "project_deep_dive"
    role_track_id: str | None = None
    interviewer_style: InterviewerStyle
    interaction_mode: InteractionMode
    status: str
    total_turns: int
    cache_hit_rate: float
    estimated_cost_cny: float
    overall_score: float | None = None
    created_at: datetime
