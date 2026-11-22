import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 and _HERE.parents[1].name == "backend" else _HERE.parents[1]
DATA_DIR = Path(os.getenv("INTERVIEW_DATA_DIR", str(REPO_ROOT / "data")))


class StageLLMSettings(BaseModel):
    base_url: str = "http://127.0.0.1:8790/v1"
    api_key: str = "sk-local"
    model: str = "gemini/gemini-3.8-flash"
    temperature: float = 0.4
    max_tokens: int = 4096


class VoiceSettings(BaseModel):
    tts_provider: Literal["edge_tts", "web_speech", "kokoro", "openai_tts", "none"] = "edge_tts"
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_tts_rate: str = "+0%"
    stt_provider: Literal["web_speech", "openai_stt", "text_only"] = "web_speech"
    stt_base_url: str = "http://127.0.0.1:8790/v1"
    stt_api_key: str = "sk-local"
    stt_model: str = "whisper-1"


class ModelPriceRule(BaseModel):
    """Per-1M token pricing in CNY."""
    input_per_1m_cny: float = 1.0
    cached_input_per_1m_cny: float = 0.1
    output_per_1m_cny: float = 4.0


class AppRuntimeConfig(BaseModel):
    mock_mode: bool = False
    prep_llm: StageLLMSettings = Field(default_factory=StageLLMSettings)
    live_llm: StageLLMSettings = Field(default_factory=StageLLMSettings)
    judge_llm: StageLLMSettings = Field(
        default_factory=lambda: StageLLMSettings(temperature=0.2, max_tokens=4096)
    )
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    pricing: dict[str, ModelPriceRule] = Field(
        default_factory=lambda: {
            "default": ModelPriceRule(
                input_per_1m_cny=1.0,
                cached_input_per_1m_cny=0.1,
                output_per_1m_cny=4.0,
            ),
            "gemini/gemini-3.8-flash": ModelPriceRule(
                input_per_1m_cny=1.08,
                cached_input_per_1m_cny=0.11,
                output_per_1m_cny=4.32,
            ),
            "buddy/deepseek-v4.1-flash": ModelPriceRule(
                input_per_1m_cny=1.08,
                cached_input_per_1m_cny=0.022,
                output_per_1m_cny=4.32,
            ),
            "buddy/deepseek-v4-pro": ModelPriceRule(
                input_per_1m_cny=2.0,
                cached_input_per_1m_cny=0.2,
                output_per_1m_cny=8.0,
            ),
        }
    )


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(REPO_ROOT / "backend" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mock_mode: bool = False

    prep_llm_base_url: str = "http://127.0.0.1:8790/v1"
    prep_llm_api_key: str = "sk-local"
    prep_llm_model: str = "gemini/gemini-3.8-flash"

    live_llm_base_url: str = "http://127.0.0.1:8790/v1"
    live_llm_api_key: str = "sk-local"
    live_llm_model: str = "gemini/gemini-3.8-flash"

    judge_llm_base_url: str = "http://127.0.0.1:8790/v1"
    judge_llm_api_key: str = "sk-local"
    judge_llm_model: str = "gemini/gemini-3.8-flash"

    tts_provider: Literal["edge_tts", "web_speech", "kokoro", "openai_tts", "none"] = "edge_tts"
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_tts_rate: str = "+0%"

    stt_provider: Literal["web_speech", "openai_stt", "text_only"] = "web_speech"
    stt_base_url: str = "http://127.0.0.1:8790/v1"
    stt_api_key: str = "sk-local"
    stt_model: str = "whisper-1"

    database_url: str = ""
    github_proxy: str = "http://127.0.0.1:7897"
    repomix_max_tokens: int = 20000

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        db_file = (DATA_DIR / "interview.db").as_posix()
        return f"sqlite+aiosqlite:///{db_file}"

    def to_runtime_config(self) -> AppRuntimeConfig:
        return AppRuntimeConfig(
            mock_mode=self.mock_mode,
            prep_llm=StageLLMSettings(
                base_url=self.prep_llm_base_url,
                api_key=self.prep_llm_api_key,
                model=self.prep_llm_model,
                temperature=0.3,
                max_tokens=8192,
            ),
            live_llm=StageLLMSettings(
                base_url=self.live_llm_base_url,
                api_key=self.live_llm_api_key,
                model=self.live_llm_model,
                temperature=0.45,
                max_tokens=4096,
            ),
            judge_llm=StageLLMSettings(
                base_url=self.judge_llm_base_url,
                api_key=self.judge_llm_api_key,
                model=self.judge_llm_model,
                temperature=0.2,
                max_tokens=8192,
            ),
            voice=VoiceSettings(
                tts_provider=self.tts_provider,
                edge_tts_voice=self.edge_tts_voice,
                edge_tts_rate=self.edge_tts_rate,
                stt_provider=self.stt_provider,
                stt_base_url=self.stt_base_url,
                stt_api_key=self.stt_api_key,
                stt_model=self.stt_model,
            ),
        )


env_settings = EnvSettings()
