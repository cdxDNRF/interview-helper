from typing import Literal
from pydantic import BaseModel, Field

from app.config import ModelPriceRule, StageLLMSettings, VoiceSettings


class MaskedStageLLMSettings(BaseModel):
    base_url: str
    api_key_masked: str
    has_api_key: bool
    model: str
    temperature: float
    max_tokens: int


class SettingsReadResponse(BaseModel):
    mock_mode: bool
    prep_llm: MaskedStageLLMSettings
    live_llm: MaskedStageLLMSettings
    judge_llm: MaskedStageLLMSettings
    voice: VoiceSettings
    pricing: dict[str, ModelPriceRule]


class StageLLMUpdate(BaseModel):
    base_url: str
    api_key: str | None = None  # None/empty keeps existing stored key unless explicit
    model: str
    temperature: float = 0.4
    max_tokens: int = 2048


class SettingsUpdateRequest(BaseModel):
    mock_mode: bool
    prep_llm: StageLLMUpdate
    live_llm: StageLLMUpdate
    judge_llm: StageLLMUpdate
    voice: VoiceSettings
    pricing: dict[str, ModelPriceRule] | None = None


class FetchModelsRequest(BaseModel):
    base_url: str
    api_key: str = ""


class TestConnectionRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str
    stage: Literal["prep", "live", "judge"] = "live"


class TestConnectionResponse(BaseModel):
    ok: bool
    latency_ms: int
    model: str
    reply_preview: str = ""
    error: str = ""
