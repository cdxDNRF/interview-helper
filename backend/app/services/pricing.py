from app.config import AppRuntimeConfig, ModelPriceRule

CNY_PER_USD = 7.20


def resolve_price_rule(model_name: str, config: AppRuntimeConfig) -> ModelPriceRule:
    if model_name in config.pricing:
        return config.pricing[model_name]
    lower = model_name.lower()
    for key, rule in config.pricing.items():
        if key != "default" and key.lower() in lower:
            return rule
    return config.pricing.get("default", ModelPriceRule())


def estimate_cost_cny(
    model_name: str,
    prompt_tokens: int,
    cached_tokens: int,
    completion_tokens: int,
    config: AppRuntimeConfig,
) -> float:
    rule = resolve_price_rule(model_name, config)
    uncached_prompt = max(0, prompt_tokens - cached_tokens)
    cost = (
        (uncached_prompt / 1_000_000) * rule.input_per_1m_cny
        + (cached_tokens / 1_000_000) * rule.cached_input_per_1m_cny
        + (completion_tokens / 1_000_000) * rule.output_per_1m_cny
    )
    return round(cost, 6)


def compute_cache_hit_rate(prompt_tokens: int, cached_tokens: int) -> float:
    if prompt_tokens <= 0:
        return 0.0
    return round(min(1.0, max(0.0, cached_tokens / prompt_tokens)), 4)


def cny_to_usd(cny: float) -> float:
    return round(cny / CNY_PER_USD, 6)
