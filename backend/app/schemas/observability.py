from datetime import datetime
from pydantic import BaseModel, Field


class StageBreakdownItem(BaseModel):
    stage: str
    call_count: int
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    avg_latency_ms: float
    p95_latency_ms: int
    estimated_cost_cny: float


class UsageLogEntry(BaseModel):
    id: int
    stage: str
    model_name: str
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    cache_hit_rate: float
    latency_ms: int
    estimated_cost_cny: float
    static_prefix_sha256: str
    created_at: datetime


class SessionTrendPoint(BaseModel):
    session_id: str
    context_title: str
    cache_hit_rate: float
    estimated_cost_cny: float
    avg_latency_ms: float
    overall_score: float | None = None
    created_at: datetime


class ObservabilityOverviewResponse(BaseModel):
    total_sessions: int
    total_llm_calls: int
    avg_cache_hit_rate: float
    total_cost_cny: float
    avg_latency_ms: float
    stage_breakdown: list[StageBreakdownItem] = Field(default_factory=list)
    session_trends: list[SessionTrendPoint] = Field(default_factory=list)


class SessionObservabilityResponse(BaseModel):
    session_id: str
    context_title: str
    static_prefix_sha256: str
    prefix_consistent: bool
    cache_hit_rate: float
    total_cost_cny: float
    stage_breakdown: list[StageBreakdownItem] = Field(default_factory=list)
    logs: list[UsageLogEntry] = Field(default_factory=list)
