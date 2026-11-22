from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class EvidenceQuote(BaseModel):
    """原句证据引用（强制排在推理和打分之前）。"""
    quote: str = Field(description="逐字稿中候选人的原话精确片段")
    turn_index: int = Field(description="对应轮次索引")
    timestamp_ms: int = Field(default=0, description="毫秒时间戳")
    relevance: str = Field(description="该引用证明的能力或缺陷")


class DimensionEvaluation(BaseModel):
    """单个正交维度评分：严格顺序为 evidence_quotes -> reasoning -> score(可为 null)。"""
    evidence_quotes: list[EvidenceQuote] = Field(
        default_factory=list,
        description="必须先列出逐字稿原句引用作为证据；若未考核到则为空列表",
    )
    reasoning: str = Field(
        description="基于以上原句与原子核查清单的推理分析；若未考到请说明原因",
    )
    score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="0-100分；若该维度在本场未被考到或证据不足，必须填 null 而非猜测分数",
    )


class FourDimensionsSchema(BaseModel):
    technical_depth: DimensionEvaluation = Field(description="技术原理深度")
    engineering_tradeoffs: DimensionEvaluation = Field(description="工程权衡与边界意识")
    problem_structuring: DimensionEvaluation = Field(description="问题拆解与表达结构")
    code_and_testing: DimensionEvaluation = Field(description="代码实现细节与自测/容错意识")


class ChecklistOutcome(BaseModel):
    topic_title: str
    criterion: str
    status: Literal["passed", "missed", "not_tested"]
    evidence_quote: str = ""
    turn_index: int | None = None


class TranscriptAnnotation(BaseModel):
    turn_index: int
    topic_title: str
    ladder_level: int
    critique: str = Field(description="针对该轮回答的具体批注（非空泛套话）")
    original_utterance: str = Field(description="候选人原话")
    ideal_rewrite: str = Field(description="对标目标职级满分重构版话术")


class JudgeLLMOutput(BaseModel):
    """
    赛后独立裁判结构化输出 Schema。
    字段顺序铁律：evidence_quotes -> reasoning -> dimensions(内含先证据后分数) -> checklist -> annotations -> overall_score。
    """
    evidence_quotes: list[EvidenceQuote] = Field(
        default_factory=list,
        description="全局核心证据原句（必须最先输出）",
    )
    reasoning: str = Field(description="整体评价推理过程（必须先于最终分数输出）")
    dimensions: FourDimensionsSchema
    checklist_results: list[ChecklistOutcome] = Field(default_factory=list)
    transcript_annotations: list[TranscriptAnnotation] = Field(default_factory=list)
    summary_markdown: str = Field(description="针对性改进建议总结")
    overall_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="综合加权得分；若几乎未有效作答则可为 null",
    )


class FillerWordDetail(BaseModel):
    word: str
    count: int


class SpeechMetrics(BaseModel):
    total_user_turns: int
    total_chars_and_words: int
    total_speaking_duration_sec: float
    chars_per_min: float
    longest_silence_sec: float
    total_filler_count: int
    filler_breakdown: list[FillerWordDetail] = Field(default_factory=list)
    detected_fillers_by_turn: dict[str, list[str]] = Field(default_factory=dict)
    estimation_note: str = ""


class EvaluationReportResponse(BaseModel):
    id: str
    session_id: str
    judge_model: str
    overall_score: float | None
    dimensions: FourDimensionsSchema
    checklist_results: list[ChecklistOutcome]
    transcript_annotations: list[TranscriptAnnotation]
    speech_metrics: SpeechMetrics
    summary_markdown: str
    raw_retry_count: int
    created_at: datetime
