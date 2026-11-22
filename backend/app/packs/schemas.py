from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.prep import CodingChallenge


InterviewType = Literal[
    "project_deep_dive",
    "general_behavioral",
    "cs_role_track",
    "bagu_fundamentals",
]


class PresetTopicSeed(BaseModel):
    topic_id: str
    title: str
    source_entrypoint: str
    target_dimensions: list[str] = Field(default_factory=list)
    atomic_checklist: list[str] = Field(default_factory=list)
    l1_seed_question: str
    coding_challenge: CodingChallenge | None = None


class RoleTrackPreset(BaseModel):
    id: str
    name: str
    tagline: str
    icon: str = "code"
    default_jd: str
    recommended_dimensions: list[str] = Field(default_factory=list)
    hotwords: list[str] = Field(default_factory=list)
    core_topics: list[PresetTopicSeed] = Field(default_factory=list)


class KnowledgePackPreset(BaseModel):
    id: str
    name: str
    category: str
    summary: str
    hotwords: list[str] = Field(default_factory=list)
    core_topics: list[PresetTopicSeed] = Field(default_factory=list)


class GeneralPackPreset(BaseModel):
    id: str
    name: str
    summary: str
    core_topics: list[PresetTopicSeed] = Field(default_factory=list)


class PresetsCatalogResponse(BaseModel):
    roles: list[RoleTrackPreset]
    fundamentals: list[KnowledgePackPreset]
    general_packs: list[GeneralPackPreset]
