from pydantic import BaseModel, Field


class GapPoint(BaseModel):
    area: str = Field(description="差距或存疑点领域")
    observation: str = Field(description="简历/源码与JD的具体落差分析")
    risk_level: str = Field(default="medium", description="high | medium | low")


class PrepTopic(BaseModel):
    topic_id: str
    title: str
    source_entrypoint: str = Field(
        default="", description="命中的简历项目或 Repomix 源码文件路径/模块切入点"
    )
    target_dimensions: list[str] = Field(default_factory=list)
    atomic_checklist: list[str] = Field(
        default_factory=list, description="3-5条二元(是/否)原子核查点"
    )
    l1_seed_question: str = Field(description="L1 概念原理层初始发问")


class PrepPlan(BaseModel):
    candidate_summary: str
    resume_jd_gaps: list[GapPoint] = Field(default_factory=list)
    topics: list[PrepTopic] = Field(min_length=1, max_length=6)
    hotwords: list[str] = Field(default_factory=list, description="ASR 技术热词表")
