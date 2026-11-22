from pydantic import BaseModel, Field


class GapPoint(BaseModel):
    area: str = Field(description="差距或存疑点领域")
    observation: str = Field(description="简历/源码与JD的具体落差分析")
    risk_level: str = Field(default="medium", description="high | medium | low")


class CodingChallenge(BaseModel):
    title: str = Field(description="浏览器 Pyodide 编程实操题目")
    starter_code: str = Field(description="Python 起始代码模板")
    test_cases_code: str = Field(description="使用 assert 或 unittest 的独立校验测试代码")


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
    coding_challenge: CodingChallenge | None = Field(
        default=None, description="可选的浏览器 Pyodide Python 实战编程题"
    )


class PrepPlan(BaseModel):
    candidate_summary: str
    resume_jd_gaps: list[GapPoint] = Field(default_factory=list)
    topics: list[PrepTopic] = Field(min_length=1, max_length=6)
    hotwords: list[str] = Field(default_factory=list, description="ASR 技术热词表")
