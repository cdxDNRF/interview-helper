import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator
from urllib.parse import urlparse

import httpx

from app.config import AppRuntimeConfig, StageLLMSettings
from app.services.pricing import estimate_cost_cny


@dataclass
class LLMCallResult:
    content: str
    model: str
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    latency_ms: int
    estimated_cost_cny: float
    raw_usage: dict[str, Any]


def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _build_httpx_client(base_url: str, timeout: float = 90.0) -> httpx.AsyncClient:
    """Bypass system HTTP(S)_PROXY for local loopback relays like 127.0.0.1:8790."""
    use_env_proxy = not _is_loopback_url(base_url)
    return httpx.AsyncClient(timeout=timeout, trust_env=use_env_proxy)


def extract_cached_tokens(usage: dict[str, Any]) -> int:
    if not usage:
        return 0
    if isinstance(usage.get("prompt_cache_hit_tokens"), int):
        return int(usage["prompt_cache_hit_tokens"])
    details = usage.get("prompt_tokens_details") or {}
    if isinstance(details, dict) and isinstance(details.get("cached_tokens"), int):
        return int(details["cached_tokens"])
    if isinstance(usage.get("cached_tokens"), int):
        return int(usage["cached_tokens"])
    return 0


def strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def fetch_available_models(base_url: str, api_key: str = "") -> list[str]:
    clean_base = base_url.rstrip("/")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with _build_httpx_client(clean_base, timeout=15.0) as client:
        resp = await client.get(f"{clean_base}/models", headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    items = payload.get("data") or []
    return [str(item["id"]) for item in items if isinstance(item, dict) and "id" in item]


async def chat_completion(
    stage_cfg: StageLLMSettings,
    runtime_cfg: AppRuntimeConfig,
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMCallResult:
    clean_base = stage_cfg.base_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {stage_cfg.api_key or 'sk-local'}",
    }

    body: dict[str, Any] = {
        "model": stage_cfg.model,
        "messages": messages,
        "temperature": stage_cfg.temperature if temperature is None else temperature,
        "max_tokens": stage_cfg.max_tokens if max_tokens is None else max_tokens,
    }
    if response_format is not None:
        body["response_format"] = response_format
    if tools is not None:
        body["tools"] = tools

    t0 = time.perf_counter()
    last_error: Exception | None = None

    async with _build_httpx_client(clean_base, timeout=120.0) as client:
        for attempt in range(3):
            resp = await client.post(f"{clean_base}/chat/completions", headers=headers, json=body)
            # Downgrade json_schema -> json_object automatically for relays/models that reject strict schema
            if resp.status_code == 400 and body.get("response_format", {}).get("type") == "json_schema":
                body["response_format"] = {"type": "json_object"}
                resp = await client.post(f"{clean_base}/chat/completions", headers=headers, json=body)
            if resp.status_code == 400 and body.get("response_format", {}).get("type") == "json_object":
                body.pop("response_format", None)
                resp = await client.post(f"{clean_base}/chat/completions", headers=headers, json=body)

            if resp.status_code == 429 and attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code >= 400:
                last_error = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}: {resp.text[:400]}",
                    request=resp.request,
                    response=resp,
                )
                if attempt < 2 and resp.status_code >= 500:
                    await asyncio.sleep(1.0)
                    continue
                raise last_error

            data = resp.json()
            latency_ms = int((time.perf_counter() - t0) * 1000)
            choice = (data.get("choices") or [{}])[0]
            finish_reason = choice.get("finish_reason")
            if (
                finish_reason == "length"
                and attempt < 2
                and body["max_tokens"] < 12288
                and (response_format is not None or body.get("response_format") is not None)
            ):
                body["max_tokens"] = min(16384, int(body["max_tokens"]) * 2)
                continue

            msg = choice.get("message") or {}
            content = (msg.get("content") or "").strip()
            usage = data.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            cached_tokens = extract_cached_tokens(usage)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            cost_cny = estimate_cost_cny(
                stage_cfg.model, prompt_tokens, cached_tokens, completion_tokens, runtime_cfg
            )
            return LLMCallResult(
                content=content,
                model=str(data.get("model") or stage_cfg.model),
                prompt_tokens=prompt_tokens,
                cached_tokens=cached_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                estimated_cost_cny=cost_cny,
                raw_usage=usage,
            )

    if last_error:
        raise last_error
    raise RuntimeError("Unexpected chat_completion failure")


async def stream_chat_completion(
    stage_cfg: StageLLMSettings,
    runtime_cfg: AppRuntimeConfig,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Streams deltas and yields final usage event:
    - {"type": "delta", "text": "..."}
    - {"type": "done", "result": LLMCallResult}
    """
    clean_base = stage_cfg.base_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {stage_cfg.api_key or 'sk-local'}",
    }
    body: dict[str, Any] = {
        "model": stage_cfg.model,
        "messages": messages,
        "temperature": stage_cfg.temperature,
        "max_tokens": stage_cfg.max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools is not None:
        body["tools"] = tools

    t0 = time.perf_counter()
    full_chunks: list[str] = []
    usage: dict[str, Any] = {}
    model_used = stage_cfg.model

    async with _build_httpx_client(clean_base, timeout=120.0) as client:
        async with client.stream(
            "POST", f"{clean_base}/chat/completions", headers=headers, json=body
        ) as resp:
            if resp.status_code == 400 and "stream_options" in body:
                await resp.aread()
                body.pop("stream_options", None)
                async with client.stream(
                    "POST", f"{clean_base}/chat/completions", headers=headers, json=body
                ) as resp2:
                    resp2.raise_for_status()
                    async for event in _parse_sse_stream(resp2, full_chunks):
                        if event["type"] == "delta":
                            yield event
                        elif event["type"] == "meta":
                            usage = event.get("usage") or usage
                            model_used = event.get("model") or model_used
            else:
                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:400]}",
                        request=resp.request,
                        response=resp,
                    )
                async for event in _parse_sse_stream(resp, full_chunks):
                    if event["type"] == "delta":
                        yield event
                    elif event["type"] == "meta":
                        usage = event.get("usage") or usage
                        model_used = event.get("model") or model_used

    latency_ms = int((time.perf_counter() - t0) * 1000)
    full_text = "".join(full_chunks).strip()
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    cached_tokens = extract_cached_tokens(usage)
    completion_tokens = int(usage.get("completion_tokens") or max(1, len(full_text) // 2))
    cost_cny = estimate_cost_cny(
        model_used, prompt_tokens, cached_tokens, completion_tokens, runtime_cfg
    )
    yield {
        "type": "done",
        "result": LLMCallResult(
            content=full_text,
            model=model_used,
            prompt_tokens=prompt_tokens,
            cached_tokens=cached_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_cny=cost_cny,
            raw_usage=usage,
        ),
    }


async def _parse_sse_stream(
    resp: httpx.Response, full_chunks: list[str]
) -> AsyncGenerator[dict[str, Any], None]:
    async for line in resp.aiter_lines():
        if not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if not data_str or data_str == "[DONE]":
            continue
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        meta_usage = chunk.get("usage")
        meta_model = chunk.get("model")
        if meta_usage or meta_model:
            yield {"type": "meta", "usage": meta_usage, "model": meta_model}
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        text_part = delta.get("content")
        if text_part:
            full_chunks.append(text_part)
            yield {"type": "delta", "text": text_part}
