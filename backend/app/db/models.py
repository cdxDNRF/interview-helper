from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    mock_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    prep_llm_json: Mapped[dict] = mapped_column(JSON, default=dict)
    live_llm_json: Mapped[dict] = mapped_column(JSON, default=dict)
    judge_llm_json: Mapped[dict] = mapped_column(JSON, default=dict)
    voice_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    pricing_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class InterviewContext(Base):
    __tablename__ = "interview_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), default="未命名面试准备")
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    resume_markdown: Mapped[str] = mapped_column(Text, default="")
    job_description: Mapped[str] = mapped_column(Text, default="")
    github_repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repo_digest_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_token_count: Mapped[int] = mapped_column(Integer, default=0)
    repo_warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="context", cascade="all, delete-orphan"
    )


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    context_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_contexts.id", ondelete="CASCADE"), index=True
    )
    interviewer_style: Mapped[str] = mapped_column(String(32), default="gentle")
    interaction_mode: Mapped[str] = mapped_column(String(32), default="voice")
    status: Mapped[str] = mapped_column(String(32), default="preparing", index=True)
    prep_plan_json: Mapped[dict] = mapped_column(JSON, default=dict)
    state_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    static_prefix_sha256: Mapped[str] = mapped_column(String(64), default="")
    total_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_cny: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    context: Mapped["InterviewContext"] = relationship(back_populates="sessions")
    turns: Mapped[list["InterviewTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.turn_index",
    )
    usage_logs: Mapped[list["LLMUsageLog"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LLMUsageLog.id",
    )
    report: Mapped["EvaluationReport | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    code_submissions: Mapped[list["CodeSubmission"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CodeSubmission.id",
    )
    mistake_items: Mapped[list["MistakeItem"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="MistakeItem.topic_index",
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer)
    topic_index: Mapped[int] = mapped_column(Integer, default=0)
    ladder_level: Mapped[int] = mapped_column(Integer, default=1)
    speaker: Mapped[str] = mapped_column(String(16))  # ai | user | system
    content: Mapped[str] = mapped_column(Text)
    timestamp_start_ms: Mapped[int] = mapped_column(Integer, default=0)
    timestamp_end_ms: Mapped[int] = mapped_column(Integer, default=0)
    pause_before_ms: Mapped[int] = mapped_column(Integer, default=0)
    word_timestamps_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    turn_eval_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tts_provider_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stt_provider_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="turns")


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))  # prep | live_eval | live_reply | judge
    model_name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str] = mapped_column(String(255), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_cny: Mapped[float] = mapped_column(Float, default=0.0)
    static_prefix_sha256: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="usage_logs")


class EvaluationReport(Base):
    __tablename__ = "evaluation_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    judge_model: Mapped[str] = mapped_column(String(128), default="")
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimensions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    checklist_results_json: Mapped[list] = mapped_column(JSON, default=list)
    transcript_annotations_json: Mapped[list] = mapped_column(JSON, default=list)
    speech_metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_markdown: Mapped[str] = mapped_column(Text, default="")
    raw_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="report")


class CodeSubmission(Base):
    __tablename__ = "code_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    topic_index: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(32), default="python")
    source_code: Mapped[str] = mapped_column(Text, default="")
    tests_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    test_output: Mapped[str] = mapped_column(Text, default="")
    exec_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="code_submissions")


class MistakeItem(Base):
    __tablename__ = "mistake_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    topic_index: Mapped[int] = mapped_column(Integer, default=0)
    topic_title: Mapped[str] = mapped_column(String(255), default="")
    source_entrypoint: Mapped[str] = mapped_column(String(255), default="")
    question_prompt: Mapped[str] = mapped_column(Text, default="")
    original_answer: Mapped[str] = mapped_column(Text, default="")
    original_score: Mapped[float] = mapped_column(Float, default=0.0)
    best_retry_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    atomic_checklist_json: Mapped[list] = mapped_column(JSON, default=list)
    ideal_rewrite: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="mistake_items")
    retries: Mapped[list["MistakeRetry"]] = relationship(
        back_populates="mistake",
        cascade="all, delete-orphan",
        order_by="MistakeRetry.id",
    )


class MistakeRetry(Base):
    __tablename__ = "mistake_retries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mistake_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mistake_items.id", ondelete="CASCADE"), index=True
    )
    retry_answer: Mapped[str] = mapped_column(Text, default="")
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    retry_score: Mapped[float] = mapped_column(Float, default=0.0)
    newly_passed_checklist_json: Mapped[list] = mapped_column(JSON, default=list)
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    mistake: Mapped["MistakeItem"] = relationship(back_populates="retries")
