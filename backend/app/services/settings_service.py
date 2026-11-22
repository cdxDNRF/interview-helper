from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppRuntimeConfig, StageLLMSettings, VoiceSettings, env_settings
from app.db.models import AppSetting
from app.schemas.settings import (
    MaskedStageLLMSettings,
    SettingsReadResponse,
    SettingsUpdateRequest,
)


def mask_api_key(key: str) -> str:
    clean = (key or "").strip()
    if not clean:
        return ""
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:3]}***{clean[-4:]}"


async def get_runtime_config(db: AsyncSession) -> AppRuntimeConfig:
    base = env_settings.to_runtime_config()
    row = await db.scalar(select(AppSetting).where(AppSetting.id == "default"))
    if row is None:
        return base

    prep = StageLLMSettings(**(row.prep_llm_json or base.prep_llm.model_dump()))
    live = StageLLMSettings(**(row.live_llm_json or base.live_llm.model_dump()))
    judge = StageLLMSettings(**(row.judge_llm_json or base.judge_llm.model_dump()))
    voice = VoiceSettings(**(row.voice_config_json or base.voice.model_dump()))
    pricing = base.pricing.copy()
    if row.pricing_config_json:
        for k, v in row.pricing_config_json.items():
            pricing[k] = base.pricing.get(k, base.pricing["default"]).model_validate(v)

    return AppRuntimeConfig(
        mock_mode=bool(row.mock_mode),
        prep_llm=prep,
        live_llm=live,
        judge_llm=judge,
        voice=voice,
        pricing=pricing,
    )


def to_masked_response(cfg: AppRuntimeConfig) -> SettingsReadResponse:
    def _mask(s: StageLLMSettings) -> MaskedStageLLMSettings:
        return MaskedStageLLMSettings(
            base_url=s.base_url,
            api_key_masked=mask_api_key(s.api_key),
            has_api_key=bool(s.api_key.strip()),
            model=s.model,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
        )

    return SettingsReadResponse(
        mock_mode=cfg.mock_mode,
        prep_llm=_mask(cfg.prep_llm),
        live_llm=_mask(cfg.live_llm),
        judge_llm=_mask(cfg.judge_llm),
        voice=cfg.voice,
        pricing=cfg.pricing,
    )


async def update_runtime_config(
    db: AsyncSession, payload: SettingsUpdateRequest
) -> AppRuntimeConfig:
    current = await get_runtime_config(db)

    def _merge_stage(old: StageLLMSettings, upd) -> dict:
        new_key = upd.api_key.strip() if upd.api_key is not None and upd.api_key.strip() else old.api_key
        return StageLLMSettings(
            base_url=upd.base_url.strip(),
            api_key=new_key,
            model=upd.model.strip(),
            temperature=upd.temperature,
            max_tokens=upd.max_tokens,
        ).model_dump()

    row = await db.scalar(select(AppSetting).where(AppSetting.id == "default"))
    if row is None:
        row = AppSetting(id="default")
        db.add(row)

    row.mock_mode = payload.mock_mode
    row.prep_llm_json = _merge_stage(current.prep_llm, payload.prep_llm)
    row.live_llm_json = _merge_stage(current.live_llm, payload.live_llm)
    row.judge_llm_json = _merge_stage(current.judge_llm, payload.judge_llm)
    row.voice_config_json = payload.voice.model_dump()
    if payload.pricing is not None:
        row.pricing_config_json = {k: v.model_dump() for k, v in payload.pricing.items()}

    await db.commit()
    return await get_runtime_config(db)
